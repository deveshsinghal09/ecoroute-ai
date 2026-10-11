"""Configure an expiring local pairing key or probe the phone without printing health data/secrets."""
import argparse
import json
import secrets
import time
import uuid
from pathlib import Path

from dotenv import dotenv_values, set_key

from ecoroute.config import Settings
from ecoroute.wearable.health_connect import HealthConnectClient, HealthConnectError, validate_phone_url
from ecoroute.wearable.health_connect_summary import summarize

ROOT = Path(__file__).resolve().parents[1]


def configure(base_url, hours=8, *, root=ROOT):
    validate_phone_url(base_url)
    if not 1 <= hours <= 24:
        raise ValueError("Pairing duration must be 1–24 hours")
    env = root / ".env"
    values = dotenv_values(env)
    if values.get("ECOROUTE_PROFILE", "local") not in {"", "local"}:
        raise ValueError("Local pairing is unavailable in an AWS configuration")
    owner = values.get("HEALTH_CONNECT_OWNER_SUB") or "local-health-" + uuid.uuid4().hex
    key, expires = secrets.token_urlsafe(32), int(time.time()) + hours * 3600
    for name, value in {"HEALTH_CONNECT_BASE_URL": base_url.rstrip("/"), "HEALTH_CONNECT_OWNER_SUB": owner,
                        "HEALTH_CONNECT_LOCAL_ACCESS_TOKEN": key,
                        "HEALTH_CONNECT_LOCAL_ACCESS_EXPIRES_AT": str(expires)}.items():
        set_key(str(env), name, value)
    path = root / "work/health-connect-pairing.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key + "\n", encoding="utf-8")
    return {"configured": True, "pairing_file": str(path), "expires_at_epoch": expires,
            "instructions": "Restart backend. Copy the local pairing key into Wearable → Health Connect. Never paste it into chat."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configure-local", action="store_true")
    parser.add_argument("--base-url", help="Private phone LAN IP URL; not a secret")
    parser.add_argument("--hours", type=int, default=8)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--days", type=int, choices=range(1, 31), default=7)
    parser.add_argument("--timezone", default="UTC")
    args = parser.parse_args()
    if args.configure_local:
        if not args.base_url:
            parser.error("--base-url is required; do not put a token in command arguments")
        print(json.dumps(configure(args.base_url, args.hours), indent=2))
    if args.check:
        phone = HealthConnectClient(Settings(_env_file=ROOT / ".env"))
        try:
            sync = phone.status()
            data = phone.data(args.days)
            result = summarize(data, zone_name=args.timezone)
            print(json.dumps({"ping": "ok", "records": len(data.records),
                "record_counts": {kind: sum(r.measurement_type == kind for r in data.records)
                    for kind in sorted({r.measurement_type for r in data.records})},
                "last_sync_available": sync is not None, "skipped_records": data.skipped_records,
                "metric_status": {k: v.status for k, v in result.metrics},
                "warnings": result.warnings,
                "medical_assessment": False, "health_values_printed": False}, indent=2))
        except HealthConnectError as error:
            print(json.dumps({"status": "unavailable", "error_code": error.code}))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
