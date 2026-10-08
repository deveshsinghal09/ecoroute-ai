import json
import time

import boto3
from botocore.stub import ANY, Stubber

from ecoroute.handlers.tasks import handler
from ecoroute.storage import DynamoStore, LocalStore


def client(service):
    return boto3.client(service, region_name="ap-south-1", aws_access_key_id="test",
                        aws_secret_access_key="test")


def test_dynamo_atomic_create_and_owner_key():
    dynamo = client("dynamodb")
    store = DynamoStore(dynamo, {"journeys": "journeys"}, "idempotency")
    with Stubber(dynamo) as stub:
        stub.add_response("transact_write_items", {}, {"TransactItems": [
            {"Put": {"TableName": "idempotency", "Item": ANY,
                     "ConditionExpression": "attribute_not_exists(pk) OR expires_at <= :now",
                     "ExpressionAttributeValues": ANY}},
            {"Put": {"TableName": "journeys", "Item": ANY,
                     "ConditionExpression": "attribute_not_exists(pk)"}},
        ]})
        record, created = store.create("journeys", "alice", {"status": "active"}, "request-001")
        assert created
        stub.add_response("get_item", {}, {"TableName": "journeys",
            "Key": {"pk": {"S": "bob"}, "sk": {"S": "journeys#" + record["id"]}}, "ConsistentRead": True})
        assert store.get("journeys", "bob", record["id"]) is None
        stub.assert_no_pending_responses()


def test_expired_record_is_hidden_before_dynamo_ttl_deletion():
    dynamo = client("dynamodb")
    with Stubber(dynamo) as stub:
        stub.add_response("get_item", {"Item": {"expires_at": {"N": "1"}, "payload": {"S": "{}"}}})
        assert DynamoStore(dynamo, {"journeys": "journeys"}, "keys").get("journeys", "alice", "id") is None


def test_local_expiration():
    store = LocalStore(":memory:")
    record, _ = store.create("journeys", "alice", {}, "key", ttl=-1)
    assert store.get("journeys", "alice", record["id"]) is None


def test_sqs_partial_batch_and_private_error_logs(caplog):
    s3 = client("s3")
    with Stubber(s3) as stub:
        stub.add_response("put_object", {}, {"Bucket": "reports-bucket",
            "Key": "reports/ingestion/event1.json", "Body": ANY,
            "ContentType": "application/json", "ServerSideEncryption": "AES256"})
        result = handler({"Records": [
            {"messageId": "good", "body": json.dumps({"type": "ingestion_tick", "event_id": "event1"})},
            {"messageId": "bad", "body": "private-payload"},
        ]}, None, client=s3, bucket="reports-bucket")
        assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
        assert "private-payload" not in caplog.text
        stub.assert_no_pending_responses()


def test_storage_failure_is_503(secured):
    from botocore.exceptions import EndpointConnectionError
    from unittest.mock import patch
    with patch.object(secured.store, "get", side_effect=EndpointConnectionError(endpoint_url="hidden")):
        response = secured.client.get("/api/v1/alerts/preferences",
            headers={"Authorization": "Bearer " + secured.token()})
        assert response.status_code == 503
        assert "hidden" not in response.text


def test_dynamo_retry_returns_original_record():
    from ecoroute.storage import fingerprint
    dynamo = client("dynamodb")
    data = {"status": "active"}
    record = {"id": "existing", **data}
    with Stubber(dynamo) as stub:
        stub.add_client_error("transact_write_items", service_error_code="TransactionCanceledException")
        stub.add_response("get_item", {"Item": {"fingerprint": {"S": fingerprint(data)},
            "record_id": {"S": "existing"}, "expires_at": {"N": str(int(time.time()) + 100)}}})
        stub.add_response("get_item", {"Item": {"payload": {"S": json.dumps(record)},
                                               "expires_at": {"N": str(int(time.time()) + 100)}}})
        assert DynamoStore(dynamo, {"journeys": "journeys"}, "keys").create(
            "journeys", "alice", data, "key") == (record, False)
