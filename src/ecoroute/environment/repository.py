"""Object storage, bounded metadata index and request budgets. No AWS client in local mode."""
import io
import json
import sqlite3
import time
from functools import wraps
from threading import RLock
from datetime import UTC, datetime, timedelta
import math
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import ClientError

from ecoroute.environment.schema import digest


class BudgetExceeded(Exception):
    def __init__(self, message, *, window=None, retry_after=None):
        super().__init__(message)
        self.window, self.retry_after = window, retry_after


def budget_windows(stamp, daily, hourly):
    return (
        (stamp.strftime("%Y-%m-%d"), daily, "day", stamp.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)),
        (stamp.strftime("%Y-%m-%dT%H"), hourly, "hour", stamp.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)),
    )


def exhausted(stamp, window, reset):
    return BudgetExceeded("provider_request_budget_exhausted", window=window,
                          retry_after=max(1, math.ceil((reset - stamp).total_seconds())))


def pack(rows):
    # Stable schema across null-only pollutants and differing provider fields.
    fields = []
    sample = rows[0]
    floats = {"value", "original_value", "latitude", "longitude", "resolution_km", "native_interval_hours"}
    for key in sample:
        fields.append(pa.field(key, pa.list_(pa.string()) if key == "quality_flags"
                               else pa.float64() if key in floats else pa.string()))
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=pa.schema(fields)), buffer, compression="snappy")
    return buffer.getvalue()


def locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return call


class LocalRepository:
    def __init__(self, root="work/environment"):
        self.lock = RLock()
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "index.sqlite3", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS entries(pk TEXT, sk TEXT, payload TEXT, expires INTEGER, PRIMARY KEY(pk,sk))")
        self.db.execute("CREATE TABLE IF NOT EXISTS budget(key TEXT PRIMARY KEY, count INTEGER)")

    @locked
    def put_bytes(self, key, data, content_type):
        path = self.root / key
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("invalid object key")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    @locked
    def get_bytes(self, key):
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("invalid object key")
        return path.read_bytes()

    @locked
    def put(self, pk, sk, payload, ttl=90 * 86400):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO entries VALUES(?,?,?,?)",
                            (pk, sk, json.dumps(payload), int(time.time()) + ttl))

    @locked
    def get(self, pk, sk):
        row = self.db.execute("SELECT payload FROM entries WHERE pk=? AND sk=? AND expires>?",
                              (pk, sk, int(time.time()))).fetchone()
        return json.loads(row[0]) if row else None

    @locked
    def query(self, pk, start="", end="~", limit=100):
        rows = self.db.execute("SELECT payload FROM entries WHERE pk=? AND sk>=? AND sk<=? AND expires>? ORDER BY sk DESC LIMIT ?",
                               (pk, start, end, int(time.time()), limit + 1)).fetchall()
        return [json.loads(r[0]) for r in rows[:limit]], len(rows) > limit

    @locked
    def reserve(self, source, daily=100, hourly=30):
        stamp = datetime.now(UTC)
        with self.db:
            for window, maximum, label, reset in budget_windows(stamp, daily, hourly):
                key = source + ":" + window
                row = self.db.execute("SELECT count FROM budget WHERE key=?", (key,)).fetchone()
                if row and row[0] >= maximum:
                    raise exhausted(stamp, label, reset)
                self.db.execute("INSERT INTO budget VALUES(?,1) ON CONFLICT(key) DO UPDATE SET count=count+1", (key,))


class AwsRepository:
    def __init__(self, s3, dynamo, bucket, table):
        self.s3, self.dynamo, self.bucket, self.table = s3, dynamo, bucket, table

    def put_bytes(self, key, data, content_type):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data,
                           ContentType=content_type, ServerSideEncryption="AES256")

    def get_bytes(self, key):
        if not key.startswith(("raw/source=", "curated/source=", "routes/")) or ".." in key:
            raise ValueError("invalid object key")
        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        if response["ContentLength"] > 6 * 1024 * 1024:
            raise ValueError("oversized object")
        return response["Body"].read()

    def put(self, pk, sk, payload, ttl=90 * 86400):
        self.dynamo.put_item(TableName=self.table, Item={"pk": {"S": pk}, "sk": {"S": sk},
            "payload": {"S": json.dumps(payload)}, "expires_at": {"N": str(int(time.time()) + ttl)}})

    def get(self, pk, sk):
        item = self.dynamo.get_item(TableName=self.table, Key={"pk": {"S": pk}, "sk": {"S": sk}},
                                   ConsistentRead=True).get("Item")
        if item and int(item["expires_at"]["N"]) > time.time():
            return json.loads(item["payload"]["S"])
        return None

    def query(self, pk, start="", end="~", limit=100):
        response = self.dynamo.query(TableName=self.table, KeyConditionExpression="pk = :pk AND sk BETWEEN :a AND :b",
            ExpressionAttributeValues={":pk": {"S": pk}, ":a": {"S": start}, ":b": {"S": end}},
            ScanIndexForward=False, Limit=limit, ConsistentRead=True)
        return [json.loads(i["payload"]["S"]) for i in response.get("Items", [])
                if int(i["expires_at"]["N"]) > time.time()], bool(response.get("LastEvaluatedKey"))

    def reserve(self, source, daily=100, hourly=30):
        stamp = datetime.now(UTC)
        windows = budget_windows(stamp, daily, hourly)
        updates = []
        for window, maximum, _, _ in windows:
            updates.append({"Update": {"TableName": self.table,
                    "Key": {"pk": {"S": "BUDGET#" + source}, "sk": {"S": window}},
                    "UpdateExpression": "SET expires_at = :ttl ADD requests :one",
                    "ConditionExpression": "attribute_not_exists(requests) OR requests < :maximum",
                    "ExpressionAttributeValues": {":ttl": {"N": str(int(time.time()) + 172800)},
                        ":one": {"N": "1"}, ":maximum": {"N": str(maximum)}}}})
        try:
            # Both counters commit together, so an hourly rejection cannot consume a daily slot.
            self.dynamo.transact_write_items(TransactItems=updates)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "TransactionCanceledException":
                for i, reason in enumerate(exc.response.get("CancellationReasons", [])[:2]):
                    if reason.get("Code") == "ConditionalCheckFailed":
                        _, _, label, reset = windows[i]
                        raise exhausted(stamp, label, reset) from None
            raise


def save_raw(repository, envelope):
    source = envelope["source"]
    day = envelope["collected_at"][:10]
    identifier = digest(envelope)
    key = f"raw/source={source}/date={day}/{identifier}.json"
    repository.put_bytes(key, json.dumps(envelope, allow_nan=False).encode(), "application/json")
    return key


def curate(repository, key):
    from ecoroute.environment.providers import cleaner
    envelope = json.loads(repository.get_bytes(key))
    rows = cleaner(envelope)
    grouped = {}
    unique = {r.record_id: r for r in rows}
    for record in unique.values():
        record.raw_key = key
        grouped.setdefault(record.reported_at.date().isoformat(), []).append(record.model_dump(mode="json"))
    outputs = []
    for day, values in grouped.items():
        object_key = f"curated/source={envelope['source']}/date={day}/{digest(key)}.parquet"
        repository.put_bytes(object_key, pack(values), "application/vnd.apache.parquet")
        outputs.append(object_key)
        # Index one bounded file per raw page/date; queries never scan all observations in DynamoDB.
        repository.put("FILES#" + envelope["source"], day + "#" + digest(key),
                       {"key": object_key, "count": len(values), "collected_at": envelope["collected_at"]})
    if envelope["source"] == "openaq":
        station = envelope["station"]
        repository.put("STATIONS#openaq", str(station["id"]), station)
    report = {"source": envelope["source"], "raw_key": key, "curated_keys": outputs,
              "records": len(unique), "missing_or_rejected": sum(r.value is None for r in unique.values()),
              "flagged": sum(bool(r.quality_flags) for r in unique.values()),
              "collected_at": envelope["collected_at"], "status": "cleaned"}
    repository.put("QUALITY#" + envelope["source"], envelope["collected_at"] + "#" + digest(key), report)
    return report
