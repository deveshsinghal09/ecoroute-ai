import re

import boto3
from botocore.config import Config


def aws_client(settings, service):
    session = boto3.Session(profile_name=settings.aws_profile or None, region_name=settings.aws_region)
    config = Config(connect_timeout=2, read_timeout=5, retries={"total_max_attempts": 1})
    if settings.ecoroute_profile == "local":
        identity = session.client("sts", config=config).get_caller_identity()
        if identity["Account"] != settings.expected_aws_account_id or identity["Arn"].endswith(":root"):
            raise ValueError("AWS identity mismatch or root identity")
    return session.client(service, config=config)


def notify_sms(store, owner, alert, settings, client=None):
    preferences = store.get("preferences", owner, "settings") or {}
    if not settings.enable_sms or not preferences.get("alerts_enabled") or preferences.get("channel") != "sms":
        return {"status": "disabled", "delivered": False}
    # Operator binds a dedicated, single-recipient topic; clients cannot supply destinations.
    binding = store.get("notification_config", owner, "sms") or {}
    topic = binding.get("topic_arn")
    if topic not in settings.sns_allowed_topic_arns:
        return {"status": "destination_not_configured", "delivered": False}
    try:
        client = client or aws_client(settings, "sns")
        subscribers = client.list_subscriptions_by_topic(TopicArn=topic)
        rows = subscribers.get("Subscriptions", [])
        if subscribers.get("NextToken") or len(rows) != 1 or rows[0].get("Protocol") != "sms" or not re.fullmatch(r"\+[1-9][0-9]{7,14}", rows[0].get("Endpoint", "")) or not rows[0].get("SubscriptionArn", "").startswith("arn:"):
            return {"status": "destination_not_verified", "delivered": False}
        sandbox = client.get_sms_sandbox_account_status()
        if sandbox.get("IsInSandbox"):
            verified = client.list_sms_sandbox_phone_numbers()
            if verified.get("NextToken") or not any(p.get("PhoneNumber") == rows[0]["Endpoint"] and p.get("Status") == "Verified" for p in verified.get("PhoneNumbers", [])):
                return {"status": "destination_not_verified", "delivered": False}
        attrs = client.get_sms_attributes(attributes=["MonthlySpendLimit"])["attributes"]
        if not 0 < float(attrs.get("MonthlySpendLimit", "0")) <= settings.sms_monthly_spend_limit_usd:
            return {"status": "spend_limit_not_verified", "delivered": False}
        attributes = {"AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"},
            "AWS.SNS.SMS.MaxPrice": {"DataType": "Number", "StringValue": str(settings.sms_max_price_usd)}}
        if rows[0]["Endpoint"].startswith("+91"):
            if not re.fullmatch(r"[A-Za-z0-9]{1,11}", settings.sms_sender_id) or not re.fullmatch(r"[0-9]{1,50}", settings.sms_entity_id) or not re.fullmatch(r"[0-9]{1,50}", settings.sms_template_id):
                return {"status": "india_dlt_configuration_missing", "delivered": False}
            for name, value in (("SenderID", settings.sms_sender_id), ("EntityId", settings.sms_entity_id), ("TemplateId", settings.sms_template_id)):
                attributes["AWS.SNS.SMS." + name] = {"DataType": "String", "StringValue": value}
        # Atomic claims before publishing. Ambiguous timeouts are never automatically retried.
        if not store.claim("notification_state", owner, alert["id"], {}, 7 * 86400):
            return {"status": "deduplicated", "delivered": False}
        if not store.claim("notification_state", owner, "cooldown", {}, 3600):
            return {"status": "rate_limited", "delivered": False}
        result = client.publish(TopicArn=topic, Message="EcoRoute: a complete PM2.5 daily window exceeds WHO 2021 guidance. Check data confidence and official local advice. Not medical advice.",
            MessageAttributes=attributes)
        return {"status": "accepted" if result.get("MessageId") else "unknown", "message_id": result.get("MessageId"), "delivered": False}
    except Exception:
        return {"status": "unavailable_or_unknown", "delivered": False}
