"""Request counters only: no real provider traffic or environmental readings."""
from datetime import UTC, datetime, timedelta

import boto3
import pytest
from botocore.stub import ANY, Stubber

from ecoroute.config import Settings
from ecoroute.environment.repository import AwsRepository, BudgetExceeded, LocalRepository
from ecoroute.routing.api import service
from ecoroute.routing.service import create_service


def test_hourly_rejection_does_not_consume_daily_slot(tmp_path):
    repo = LocalRepository(tmp_path)
    repo.reserve("location", daily=100, hourly=1)
    for _ in range(4):
        with pytest.raises(BudgetExceeded) as error:
            repo.reserve("location", daily=100, hourly=1)
        assert error.value.window == "hour"
        assert 1 <= error.value.retry_after <= 3600
    rows = repo.db.execute("SELECT count FROM budget").fetchall()
    assert rows == [(1,), (1,)]


@pytest.mark.parametrize("index,window", [(0, "day"), (1, "hour")])
def test_aws_counters_use_one_atomic_transaction_and_report_failed_window(index, window):
    client = boto3.client("dynamodb", region_name="ap-south-1",
                          aws_access_key_id="fixture", aws_secret_access_key="fixture")
    repo = AwsRepository(None, client, "unused", "environment")
    reasons = [{"Code": "None"}, {"Code": "None"}]
    reasons[index] = {"Code": "ConditionalCheckFailed"}
    with Stubber(client) as stub:
        stub.add_client_error("transact_write_items", service_error_code="TransactionCanceledException",
                              expected_params={"TransactItems": [ANY, ANY]},
                              modeled_fields={"CancellationReasons": reasons})
        with pytest.raises(BudgetExceeded) as error:
            repo.reserve("location", daily=100, hourly=100)
        assert error.value.window == window
        assert 1 <= error.value.retry_after <= (86400 if window == "day" else 3600)
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("window,code", [("day", "location_daily_budget_exhausted"),
                                        ("hour", "location_hourly_budget_exhausted")])
def test_rate_limit_http_response_identifies_window_and_retry_time(secured, window, code):
    class Exhausted:
        def reserve(self, *args):
            raise BudgetExceeded("provider_request_budget_exhausted", window=window, retry_after=120)

    engine = create_service(Settings(_env_file=None, routing_provider="google",
                                     google_routes_api_key="fixture"), secured.store, Exhausted())
    secured.app.dependency_overrides[service] = lambda: engine
    response = secured.client.post("/api/v1/routes/compare", json={
        "origin": {"latitude": 28.61, "longitude": 77.22},
        "destination": {"latitude": 28.63, "longitude": 77.21},
        "departure_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "mode": "driving", "consent_to_store": True,
    }, headers={"Authorization": "Bearer " + secured.token()})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == code
    assert response.headers["Retry-After"] == "120"
