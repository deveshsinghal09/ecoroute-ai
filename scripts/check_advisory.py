"""Offline readiness report: never invokes AWS, models, SMS or external providers."""
import json
from datetime import UTC, datetime
from pathlib import Path

import botocore.session

from ecoroute.advisory.alerts import daily_window
from ecoroute.config import Settings
from ecoroute.environment.repository import LocalRepository


def main():
    settings = Settings()
    sdk = botocore.session.get_session()
    required = {"bedrock-runtime": ["Converse"], "sns": ["Publish", "GetSMSSandboxAccountStatus", "ListSMSSandboxPhoneNumbers", "GetSMSAttributes"], "stepfunctions": ["StartExecution"]}
    compatible = {service: all(op in sdk.get_service_model(service).operation_names for op in operations) for service, operations in required.items()}
    root = Path("work/environment")
    data = {"status": "unavailable", "reason": "no_local_environment_repository"}
    if (root / "index.sqlite3").exists():
        repo = LocalRepository(root)
        stations, _ = repo.query("STATIONS#openaq", limit=1)
        if stations:
            data = daily_window(repo, "openaq", str(stations[0]["id"]), datetime.now(UTC).replace(minute=0, second=0, microsecond=0))
            data.pop("record_ids", None)
        repo.db.close()
    print(json.dumps({"authenticated_calls": 0, "sdk_compatible": compatible,
        "bedrock_enabled": settings.enable_bedrock, "sms_enabled": settings.enable_sms,
        "configuration_present": {name: bool(getattr(settings, name)) for name in (
            "aws_profile", "expected_aws_account_id", "bedrock_model_id", "sns_allowed_topic_arns", "sms_sender_id", "sms_entity_id", "sms_template_id", "workflow_state_machine_arn")},
        "local_measured_daily_evaluation": data}, indent=2))


if __name__ == "__main__":
    main()
