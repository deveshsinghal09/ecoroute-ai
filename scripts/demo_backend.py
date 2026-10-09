"""Isolated authenticated API demo. Real saved pollution; wearable/alert fixtures explicit."""
import argparse
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from ecoroute.advisory.alerts import GUIDANCE
from ecoroute.auth import CognitoVerifier
from ecoroute.config import Settings
from ecoroute.environment.pipeline import repository
from ecoroute.environment.repository import LocalRepository
from ecoroute.main import create_app
from ecoroute.storage import LocalStore
from scripts.benchmark_routes import engine_for, verify_arithmetic


def run_demo(data, *, provider="recorded", live=False):
    repo, store = LocalRepository(data), LocalStore(":memory:")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    owner = "isolated-demo-subject"
    with TemporaryDirectory(prefix="ecoroute-demo-") as scratch:
        settings = Settings(_env_file=None, ecoroute_profile="local", aws_region="ap-south-1",
            enable_bedrock=False, enable_sms=False, enable_aws_location=False,
            enable_openaq=False, enable_weather=False, enable_wearable=False,
            local_db_path=":memory:", cognito_user_pool_id="ap-south-1_demo",
            cognito_client_id="isolated-demo", wearable_demo_mode=True, wearable_archive_path=scratch)
        class Keys:
            def get_signing_key_from_jwt(self, token):
                return SimpleNamespace(key=key.public_key())
        verifier = CognitoVerifier(settings, Keys())
        app = create_app(settings, store=store, verifier=verifier)
        app.state.route_service = engine_for(provider, store, repo, live=live)
        app.dependency_overrides[repository] = lambda: repo
        claims = {"iss": settings.issuer, "sub": owner, "client_id": settings.cognito_client_id,
            "token_use": "access", "iat": int(time.time()), "exp": int(time.time()) + 300,
            "scope": "ecoroute/read ecoroute/write"}
        token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "isolated-test-key"})
        headers = {"Authorization": "Bearer " + token, "Idempotency-Key": "isolated-demo-trip"}
        with TestClient(app) as client:
            def call(method, path, body=None, params=None):
                response = client.request(method, "/api/v1/" + path, headers=headers, json=body, params=params)
                if response.status_code not in {200, 201}:
                    raise RuntimeError(path + ": " + response.text)
                return response.json()
            departure = datetime.now(UTC) + timedelta(minutes=1)
            body = {"origin": {"longitude": 77.2295, "latitude": 28.6129}, "destination": {"longitude": 77.2167, "latitude": 28.6315},
                "departure_at": departure.isoformat(), "mode": "driving", "objective": "balanced", "consent_to_store": True}
            comparison = call("POST", "routes/compare", body)
            for route in comparison["routes"]:
                verify_arithmetic(route)
            selected = next(r for r in comparison["routes"] if r["route_id"] == comparison["selected_route_id"])
            departures = call("POST", "routes/departure-time-analysis", {**body, "departures": [departure.isoformat(), (departure + timedelta(hours=2)).isoformat()]})
            explanation = call("POST", "ai/explain-route", {"route_ids": [r["route_id"] for r in comparison["routes"]]})
            journey = call("POST", "trips", {"origin": body["origin"], "destination": body["destination"], "consent": True, "route_id": selected["route_id"]})
            device = call("POST", "devices/register", {"manufacturer": "Local fixture", "model": "No hardware", "bridge": "demo"})["device_id"]
            call("POST", "wearables/consent", {"device_id": device, "telemetry": True, "location": True, "history": True, "correlation": True})
            segment = selected["segments"][0]
            sample = {"device_id": device, "user_id": owner, "event_id": uuid.uuid4().hex, "timestamp": segment["sample_at"],
                "heart_rate_bpm": 80, "activity": "driving", "position": {"longitude": segment["sample_position"][0], "latitude": segment["sample_position"][1]},
                "accuracy_m": 10, "journey_id": journey["id"], "provenance": {"bridge": "demo", "sensor": "SYNTHETIC_TEST_ONLY", "source_record_id": "fixture", "synthetic": True}}
            call("POST", "wearables/measurements", sample)
            correlation = call("GET", f"journeys/{journey['id']}/wearable-correlation", params={"device_id": device})
            # Test-only threshold evidence, scoped to this ephemeral process/store. Never
            # modifies real provider data or enables SNS; normal route scoring used real data.
            end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
            rows = [{"record_id": f"SYNTHETIC_{i}", "location_id": "SYNTHETIC_TEST_ONLY", "sensor_id": "fixture",
                "pollutant": "pm25", "kind": "observed", "unit": "ug/m3", "value": 30,
                "quality_flags": [], "reported_at": (end - timedelta(hours=i)).isoformat(),
                "period_start": (end - timedelta(hours=i + 1)).isoformat(), "collected_at": datetime.now(UTC).isoformat()} for i in range(24)]
            with patch("ecoroute.advisory.alerts.read_rows", return_value=(rows, False)):
                alert = call("POST", "alerts/evaluate", {"source": "openaq", "location_id": "SYNTHETIC_TEST_ONLY", "end_at": end.isoformat(), "notify": False})
            call("POST", "wearables/consent", {"device_id": device, "telemetry": False})
            revoked = client.post("/api/v1/wearables/measurements", headers=headers, json={**sample, "event_id": uuid.uuid4().hex})
            assert revoked.status_code == 403
            result = {"scenario": "isolated_authenticated_backend_demo", "aws_routes_verified": provider == "aws",
                "geometry": "recorded_real_osrm" if provider == "recorded" else "live_provider_roads",
                "pollution": "actual_saved_provider_values_or_unavailable", "comparison": comparison,
                "departure_analysis": departures, "arithmetic_verified": True, "explanation": explanation,
                "bedrock_live_verified": False, "wearable": {"synthetic": True, "hardware_verified": False, "correlation": correlation, "revocation_verified": True},
                "alert": {"synthetic_test_only": True, "guidance": GUIDANCE, "created": alert["created"], "notification": alert["notification"]},
                "ml": call("GET", "ml/status"), "cloud_resources_verified": False}
    store.db.close()
    repo.db.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="work/environment")
    parser.add_argument("--provider", choices=["recorded", "osrm", "aws"], default="recorded")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", default="work/phase7-demo.json")
    args = parser.parse_args()
    report = run_demo(args.data, provider=args.provider, live=args.live)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output": str(path), "candidate_count": report["comparison"]["candidate_count"],
        "arithmetic_verified": True, "explanation_mode": report["explanation"]["mode"],
        "synthetic_wearable_pairs": report["wearable"]["correlation"]["paired_count"],
        "test_alert_created": report["alert"]["created"], "real_notifications_sent": 0,
        "aws_routes_verified": report["aws_routes_verified"], "ml_status": report["ml"]["status"]}))
