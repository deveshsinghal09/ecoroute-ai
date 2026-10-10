"""Optional SQL sink for existing anonymized route reports, never raw location/health data."""
import hashlib
import json
import os
import sqlite3
from datetime import date, datetime, timedelta, UTC
from typing import Literal
from urllib.parse import unquote_plus

import boto3
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CandidateMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    duration_s: float = Field(gt=0, le=604800)
    distance_m: float = Field(ge=0, le=10000000)
    pm25_exposure_ug_h_m3: float | None = Field(default=None, ge=0)
    coverage_fraction: float = Field(ge=0, le=1)


class AggregateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: Literal["Delhi"]
    date: date
    mode: Literal["walking", "cycling", "driving"]
    provider: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    candidate_count: int = Field(ge=1, le=6)
    engine_version: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    metrics: list[CandidateMetric] = Field(min_length=1, max_length=6)

    @field_validator("provider")
    @classmethod
    def no_google_retention(cls, value):
        if "google" in value.lower():
            raise ValueError("Google results are request-only and must not enter SQL analytics")
        return value


INSERT = """INSERT INTO route_reports (report_id, report_date, mode, provider, candidate_count, report_json)
VALUES (:id, :day, :mode, :provider, :count, :payload) ON CONFLICT (report_id) DO NOTHING"""
DDL = """CREATE TABLE IF NOT EXISTS route_reports (
report_id TEXT PRIMARY KEY, report_date DATE NOT NULL, mode TEXT NOT NULL,
provider TEXT NOT NULL, candidate_count INTEGER NOT NULL, report_json TEXT NOT NULL)"""


class SqliteAnalytics:
    """Local real SQL execution of the same aggregate report contract."""
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.execute(DDL)

    def insert(self, values):
        self.connection.execute(INSERT, values)
        self.connection.commit()

    def prune(self, cutoff):
        self.connection.execute("DELETE FROM route_reports WHERE report_date < :cutoff", {"cutoff": cutoff})
        self.connection.commit()

    def close(self):
        self.connection.close()


class AuroraAnalytics:
    def __init__(self, client, cluster_arn, secret_arn):
        self.client, self.cluster, self.secret = client, cluster_arn, secret_arn

    def execute(self, sql, values):
        parameters = []
        for key, value in values.items():
            parameter = {"name": key, "value": {"longValue": value} if isinstance(value, int) else {"stringValue": value}}
            if key in ("day", "cutoff"):
                parameter["typeHint"] = "DATE"
            parameters.append(parameter)
        self.client.execute_statement(resourceArn=self.cluster, secretArn=self.secret, database="ecoroute",
            sql=sql, parameters=parameters)

    def insert(self, values):
        self.execute(INSERT, values)

    def prune(self, cutoff):
        self.execute("DELETE FROM route_reports WHERE report_date < CAST(:cutoff AS date)", {"cutoff": cutoff})

    def close(self):
        pass


class PostgresAnalytics:
    def __init__(self, secrets, secret_arn, host, ca_bundle):
        import psycopg
        secret = json.loads(secrets.get_secret_value(SecretId=secret_arn)["SecretString"])
        # Host/database are trusted deployment configuration, never overridden by a secret payload.
        self.connection = psycopg.connect(host=host, port=5432, dbname="ecoroute",
            user=secret["username"], password=secret["password"], sslmode="verify-full",
            sslrootcert=ca_bundle, connect_timeout=5, options="-c statement_timeout=10000")

    def insert(self, values):
        # DB-API bound parameters; report values are never SQL fragments.
        statement = INSERT
        for key in values:
            statement = statement.replace(":" + key, f"%({key})s")
        self.connection.execute(statement, values)
        self.connection.commit()

    def prune(self, cutoff):
        self.connection.execute("DELETE FROM route_reports WHERE report_date < %s::date", (cutoff,))
        self.connection.commit()

    def close(self):
        self.connection.close()


def ingest_report(raw, key, sink, now=None):
    if len(raw) > 65536:
        raise ValueError("oversized_report")
    report = AggregateReport.model_validate_json(raw)
    if report.candidate_count != len(report.metrics):
        raise ValueError("candidate_count_mismatch")
    expected_prefix = f"reports/routes/date={report.date.isoformat()}/"
    if not key.startswith(expected_prefix) or not key.endswith(".json"):
        raise ValueError("invalid_report_key")
    today = (now or datetime.now(UTC)).date()
    # Retention is based on route departure date; forecasts may be up to 7 days ahead.
    if report.date < today - timedelta(days=30) or report.date > today + timedelta(days=7):
        raise ValueError("report_outside_retention_window")
    payload = report.model_dump_json()
    report_id = hashlib.sha256((key + "\n" + payload).encode()).hexdigest()
    sink.insert({"id": report_id, "day": report.date.isoformat(), "mode": report.mode,
                 "provider": report.provider, "count": report.candidate_count, "payload": payload})
    sink.prune((today - timedelta(days=30)).isoformat())
    return report_id


def process_records(event, s3, sink, bucket):
    failures = []
    for item in event.get("Records", []):
        try:
            message = json.loads(item["body"])
            if message.get("Event") == "s3:TestEvent":
                continue
            for record in message["Records"]:
                actual_bucket = record["s3"]["bucket"]["name"]
                key = unquote_plus(record["s3"]["object"]["key"])
                if actual_bucket != bucket or not key.startswith("reports/routes/") or not key.endswith(".json"):
                    raise ValueError("untrusted_s3_event")
                response = s3.get_object(Bucket=bucket, Key=key)
                stream = response["Body"]
                try:
                    ingest_report(stream.read(65537), key, sink)
                finally:
                    stream.close()
            print(json.dumps({"event": "route_analytics_processed", "status": "ok"}))
        except Exception:
            # Do not log report body, secret, database exception/connection string or location.
            failures.append({"itemIdentifier": item["messageId"]})
            print(json.dumps({"event": "route_analytics_failed", "status": "retry", "error": "processing_failed"}))
    return {"batchItemFailures": failures}


def handler(event, context):
    mode = os.environ["SQL_ANALYTICS_ENGINE"]
    region = os.environ["AWS_REGION"]
    sink = None
    try:
        if mode == "aurora":
            sink = AuroraAnalytics(boto3.client("rds-data", region_name=region), os.environ["SQL_CLUSTER_ARN"], os.environ["SQL_WRITER_SECRET_ARN"])
        elif mode == "rds":
            sink = PostgresAnalytics(boto3.client("secretsmanager", region_name=region), os.environ["SQL_WRITER_SECRET_ARN"], os.environ["SQL_HOST"], os.environ["SQL_CA_BUNDLE"])
        else:
            raise ValueError("unsupported_sql_engine")
        return process_records(event, boto3.client("s3", region_name=region), sink, os.environ["S3_DATA_BUCKET"])
    except Exception:
        print(json.dumps({"event": "route_analytics_failed", "status": "retry", "error": "database_unavailable"}))
        return {"batchItemFailures": [{"itemIdentifier": i["messageId"]} for i in event.get("Records", [])]}
    finally:
        if sink:
            sink.close()
