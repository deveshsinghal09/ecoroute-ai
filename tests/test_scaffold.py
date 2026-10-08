import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ecoroute.config import Settings
from ecoroute.main import create_app


def test_health_is_explicit_about_scaffold():
    client = TestClient(create_app(Settings(_env_file=None)))
    assert client.get("/healthz").json() == {
        "status": "ok", "profile": "local", "phase": "0-scaffold",
        "integrations_enabled": False,
    }
    assert client.post("/v1/routes").status_code == 404


@pytest.mark.parametrize("setting", [
    {"ecoroute_profile": "aws"}, {"enable_aws_location": True},
    {"enable_openaq": True}, {"enable_weather": True}, {"enable_wearable": True},
])
def test_unimplemented_live_modes_fail_closed(setting):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **setting)
