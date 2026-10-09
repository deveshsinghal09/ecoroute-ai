import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ecoroute.config import Settings
from ecoroute.main import create_app


def test_health_is_explicit_about_scaffold():
    client = TestClient(create_app(Settings(_env_file=None, local_db_path=":memory:")))
    assert client.get("/healthz").json() == {
        "status": "ok", "profile": "local", "phase": "7-integrated-backend",
        "live_domain_providers": False,
    }
    assert client.post("/v1/routes").status_code == 404
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ready").status_code == 503
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("setting", [
    {"ecoroute_profile": "aws"}, {"enable_aws_location": True},
    {"enable_openaq": True}, {"enable_weather": True}, {"enable_wearable": True},
])
def test_unimplemented_live_modes_fail_closed(setting):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **setting)
