import pytest

from ecoroute.routing.models import RoutingError
from ecoroute.routing.service import routing_secret_key


@pytest.mark.parametrize("payload", ['{"api_key":"test-key"}', "test-key", " test-key\n"])
def test_console_json_and_legacy_plaintext_keys(payload):
    assert routing_secret_key(payload) == "test-key"


@pytest.mark.parametrize("payload", ["", "{broken-private-value", '{"api_key":null}',
    '{"api_key":12}', '{"other":"private-value"}', "[]", '"private-value"',
    '{"api_key":""}', '{"api_key":"bad key"}'])
def test_invalid_secrets_fail_without_exposing_payload(payload):
    with pytest.raises(RoutingError) as caught:
        routing_secret_key(payload)
    assert "private-value" not in str(caught.value)
