import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from ecoroute.auth import CognitoVerifier
from ecoroute.config import Settings
from ecoroute.main import create_app
from ecoroute.storage import LocalStore


@pytest.fixture
def secured():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(_env_file=None, local_db_path=":memory:",
                        cognito_user_pool_id="ap-south-1_test", cognito_client_id="testclient")

    class Keys:
        def get_signing_key_from_jwt(self, token):
            if jwt.get_unverified_header(token)["kid"] != "test-key":
                raise jwt.PyJWKClientError("Unknown key")
            return SimpleNamespace(key=key.public_key())

    def token(**changes):
        claims = {"iss": settings.issuer, "sub": "alice", "client_id": "testclient",
                  "token_use": "access", "iat": int(time.time()), "exp": int(time.time()) + 300,
                  "scope": "ecoroute/read ecoroute/write"}
        claims.update(changes)
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})

    store = LocalStore(":memory:")
    app = create_app(settings, store=store, verifier=CognitoVerifier(settings, Keys()))
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, app=app, token=token, store=store, key=key)
    store.db.close()
