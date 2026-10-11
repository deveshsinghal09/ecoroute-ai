"""Bounded live checks; credentials/token remain local, no SMS or synthetic readings."""
import argparse
import getpass
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3
import httpx
from botocore.exceptions import ClientError

BASE = "https://j1lgox7e00.execute-api.ap-south-1.amazonaws.com"
ORIGIN = "https://main.d3txif33djiy59.amplifyapp.com"
COLLECTOR = "EcoRouteCore-Collector9EBA7CF5-3QqSZI3RLYxS"
TABLE = "EcoRouteData-environmentA2E95CAF-18GSQK8N0H0Q"
GRID = "cams_global:28.8000:77.2000"


def alert_payload(clock):
    return {"source": "open_meteo", "location_id": GRID,
            "end_at": (clock.replace(minute=0, second=0, microsecond=0)
                       + timedelta(hours=24)).isoformat(), "notify": False}


def summarize(path, response):
    result = {"path": path, "http_status": response.status_code}
    try:
        body = response.json()
    except ValueError:
        return result
    # Whitelist summaries, never dump records, JWTs or provider errors.
    if isinstance(body, dict):
        for key in ("status", "truncated", "created"):
            if key in body:
                result[key] = body[key]
        if isinstance(body.get("error"), dict):
            result["error_code"] = body["error"].get("code")
        for key in ("records", "stations", "alerts"):
            if isinstance(body.get(key), list):
                result[key + "_count"] = len(body[key])
        if isinstance(body.get("evaluation"), dict):
            e = body["evaluation"]
            result["evaluation"] = {k: e.get(k) for k in
                ("status", "kind", "samples", "breach", "warnings")}
        if isinstance(body.get("notification"), dict):
            result["notification"] = {k: body["notification"].get(k)
                                       for k in ("status", "delivered")}
    return result


def pipeline(session):
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != "112920804206" or identity["Arn"].endswith(":root"):
        raise ValueError("Expected non-root EcoRoute account required")
    event = {"source": "open_meteo", "request": {"latitude": 28.6139, "longitude": 77.209}}
    response = session.client("lambda").invoke(FunctionName=COLLECTOR,
        InvocationType="RequestResponse", Payload=json.dumps(event).encode())
    if response.get("FunctionError"):
        return {"pipeline": "collector_failed", "details": "inspect collector logs locally"}
    raw = json.loads(response["Payload"].read()).get("raw_key")
    if not isinstance(raw, str) or not raw.startswith("raw/source=open_meteo/"):
        return {"pipeline": "invalid_collector_response"}
    ddb = session.client("dynamodb")
    for _ in range(12):
        rows = ddb.query(TableName=TABLE,
            KeyConditionExpression="pk = :p", ExpressionAttributeValues={
                ":p": {"S": "QUALITY#open_meteo"}}, ScanIndexForward=False, Limit=20)["Items"]
        for row in rows:
            report = json.loads(row["payload"]["S"])
            if report.get("raw_key") == raw:
                return {"pipeline": "curated_metadata_verified", "raw_key": raw,
                        "records": report.get("records"), "quality": report.get("status"),
                        "curated_files": len(report.get("curated_keys", []))}
        time.sleep(5)
    return {"pipeline": "raw_saved_cleaning_not_verified", "raw_key": raw}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authenticated", action="store_true",
                        help="Paste Cognito ACCESS token into a hidden local prompt, never chat")
    parser.add_argument("--pipeline", action="store_true", help="Invoke collector ONCE; billable usage")
    parser.add_argument("--profile", default="dev-admin")
    args = parser.parse_args()
    rows = []
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        rows.append(summarize("/api/v1/health", client.get(BASE + "/api/v1/health")))
        for path in ("/api/v1/wearables/latest", "/api/v1/alerts"):
            rows.append(summarize(path, client.get(BASE + path)))
            rows.append(summarize(path + " invalid bearer", client.get(BASE + path,
                         headers={"Authorization": "Bearer invalid-test-token"})))
        response = client.options(BASE + "/api/v1/routes/preview", headers={"Origin": ORIGIN,
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        rows.append({"cors_status": response.status_code,
                     "allow_origin": response.headers.get("access-control-allow-origin")})
        if args.authenticated:
            token = getpass.getpass("Cognito ACCESS token (hidden, never saved): ").strip()
            if not token or len(token) > 8192:
                parser.error("Access token missing/invalid length")
            headers = {"Authorization": "Bearer " + token}
            for path in ("/api/v1/ready", "/api/v1/air-quality/stations",
                         "/api/v1/air-quality/forecast?location_id=" + GRID,
                         "/api/v1/data/quality", "/api/v1/alerts"):
                rows.append(summarize(path, client.get(BASE + path, headers=headers)))
            body = alert_payload(datetime.now(UTC))
            for _ in range(2):
                rows.append(summarize("/api/v1/alerts/evaluate", client.post(
                    BASE + "/api/v1/alerts/evaluate", json=body, headers=headers)))
            # No token/log/health-record persistence.
            del token, headers
    if args.pipeline:
        try:
            rows.append(pipeline(boto3.Session(profile_name=args.profile, region_name="ap-south-1")))
        except ClientError as exc:
            rows.append({"pipeline": "aws_permission_or_service_error",
                         "code": exc.response["Error"]["Code"]})
    report = Path("work/live-services-check.json")
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
