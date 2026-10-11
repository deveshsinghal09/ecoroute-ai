from datetime import UTC, datetime

import httpx

from scripts.check_live_services import alert_payload, summarize


def test_alert_check_never_requests_notification_and_uses_hour_aligned_window():
    payload = alert_payload(datetime(2026, 10, 11, 12, 23, 42, tzinfo=UTC))
    assert payload["notify"] is False
    assert payload["end_at"] == "2026-10-12T12:00:00+00:00"


def test_summaries_exclude_user_records_and_tokens():
    response = httpx.Response(200, json={"records": [{"user": "private-user"}],
        "access_token": "private-token", "notification": {"status": "not_requested", "delivered": False}})
    result = summarize("/test", response)
    assert result["records_count"] == 1
    assert "private-user" not in str(result)
    assert "private-token" not in str(result)
