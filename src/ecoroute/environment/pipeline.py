import json
import os
from datetime import date, timedelta

from ecoroute.environment.schema import utc
from functools import lru_cache

import boto3
from botocore.config import Config
from dotenv import load_dotenv

from ecoroute.environment.providers import JsonTransport, MissingCredential, OpenAQ, OpenMeteo, grid
from ecoroute.environment.repository import AwsRepository, LocalRepository, save_raw
from ecoroute.environment.schema import digest


@lru_cache
def repository():
    load_dotenv(override=False)
    if os.getenv("ECOROUTE_PROFILE", "local") == "aws":
        config = Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 2})
        return AwsRepository(boto3.client("s3", config=config), boto3.client("dynamodb", config=config),
                             os.environ["S3_DATA_BUCKET"], os.environ["ENVIRONMENT_TABLE"])
    return LocalRepository(os.getenv("ENVIRONMENT_LOCAL_PATH") or "work/environment")


def credential(source):
    env_name = "OPENAQ_API_KEY" if source == "openaq" else "OPEN_METEO_API_KEY"
    if os.environ.get(env_name):
        return os.environ[env_name]
    arn_name = "OPENAQ_SECRET_ARN" if source == "openaq" else "OPEN_METEO_SECRET_ARN"
    if os.getenv("ECOROUTE_PROFILE") == "aws" and os.getenv(arn_name):
        response = boto3.client("secretsmanager").get_secret_value(SecretId=os.environ[arn_name])
        return json.loads(response["SecretString"])["api_key"]
    if source == "openaq":
        raise MissingCredential("OPENAQ_API_KEY_missing")
    return None


def ingest(source, request, repo, *, transport=None):
    if source not in {"open_meteo", "openaq"}:
        raise ValueError("unsupported source")
    key = credential(source)  # fail before any provider request if mandatory credentials absent
    if source == "open_meteo":
        request = dict(request)
        request["latitude"], request["longitude"] = grid(request.get("latitude", 28.6139), request.get("longitude", 77.209))
        if bool(request.get("start")) != bool(request.get("end")):
            raise ValueError("both start and end required")
        if request.get("start"):
            start, end = date.fromisoformat(request["start"]), date.fromisoformat(request["end"])
            if start < date(2022, 8, 1) or not 0 <= (end - start).days <= 6:
                raise ValueError("history window must be 1-7 days, August 2022 or later")
    else:
        request = dict(request)
        if set(request) - {"location_id", "sensor_id", "start", "end", "page", "limit"}:
            raise ValueError("unknown observation request fields")
        for field in ("location_id", "sensor_id"):
            if type(request.get(field)) is not int or request[field] < 1:
                raise ValueError("positive integer station and sensor required")
        start, end = utc(request["start"]), utc(request["end"])
        if not timedelta(0) <= end - start <= timedelta(days=7):
            raise ValueError("observation window must be at most seven days")
        for field, maximum in (("page", 10000), ("limit", 100)):
            value = request.get(field, 1 if field == "page" else 100)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("invalid pagination bounds")
    cache_key = digest([source, request])
    cached = repo.get("CACHE#" + source, cache_key)
    if cached:
        return cached["raw_key"], True
    daily = min(1000, max(1, int(os.getenv("PROVIDER_DAILY_REQUEST_LIMIT") or "100")))
    hourly = min(100, max(1, int(os.getenv("PROVIDER_HOURLY_REQUEST_LIMIT") or "30")))
    transport = transport or JsonTransport(reserve=lambda: repo.reserve(source, daily, hourly))
    adapter = OpenMeteo(transport, key) if source == "open_meteo" else OpenAQ(key, transport)
    envelope = adapter.fetch(**request)
    raw_key = save_raw(repo, envelope)
    repo.put("CACHE#" + source, cache_key, {"raw_key": raw_key}, ttl=3600 if source == "open_meteo" else 300)
    return raw_key, False
