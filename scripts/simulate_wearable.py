"""Local-only broker-envelope simulation. No watch data, JWT bypass or network MQTT client."""
import base64
import json
import os
import uuid
from datetime import UTC, datetime

from dotenv import load_dotenv

from ecoroute.storage import LocalStore
from ecoroute.wearable.archive import Archive
from ecoroute.config import Settings
from ecoroute.wearable.handlers import process_mqtt
from ecoroute.wearable.models import Consent, Registration
from ecoroute.wearable.repository import WearableRepository, owner_key, topic


def main():
    load_dotenv(override=False)
    if os.getenv("ECOROUTE_PROFILE", "local") != "local":
        raise SystemExit("Simulation requires ECOROUTE_PROFILE=local")
    settings = Settings(_env_file=None, wearable_demo_mode=True, wearable_archive_path="work/wearable-demo/history")
    store = LocalStore("work/wearable-demo/telemetry.sqlite3")
    repo = WearableRepository(store)
    subject = "local-synthetic-demo"
    device, _ = repo.register(subject, Registration(manufacturer="Synthetic", model="No physical watch", bridge="demo"), "synthetic-demo-v1")
    repo.consent(subject, Consent(device_id=device["device_id"], telemetry=True, history=True))
    device = repo.device(subject, device["device_id"])
    device["certificate_thumbprint"] = "offline-test-principal"
    store.put_record("wearable", owner_key(subject), "device#" + device["device_id"], device, 90 * 86400)
    body = {"device_id": device["device_id"], "user_id": subject, "event_id": uuid.uuid4().hex,
        "timestamp": datetime.now(UTC).isoformat(), "heart_rate_bpm": 75, "activity": "unknown",
        "provenance": {"bridge": "demo", "sensor": "synthetic fixture", "source_record_id": uuid.uuid4().hex, "synthetic": True}}
    event = {"payload_b64": base64.b64encode(json.dumps(body).encode()).decode(),
        "owner_key": owner_key(subject), "device_id": device["device_id"],
        "mqtt_topic": topic(subject, device["device_id"]), "mqtt_client_id": "eco-" + device["device_id"],
        "principal": "offline-test-principal"}
    record, created = process_mqtt(event, repo, local_demo=True)
    _, repeated = process_mqtt(event, repo, local_demo=True)
    archived = Archive(settings).write(repo, subject, record)
    print(json.dumps({"synthetic": True, "network_mqtt_used": False, "accepted": created,
        "duplicate_detected": not repeated, "archived_locally": archived, "device_id": device["device_id"]}))


if __name__ == "__main__":
    main()
