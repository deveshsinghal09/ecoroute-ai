"""Cognito access-token verification; no development bypass or unverified JWT decoding."""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ecoroute.config import Settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    scopes: frozenset[str]


class CognitoVerifier:
    def __init__(self, settings: Settings, key_client=None):
        self.settings = settings
        self.configured = bool(settings.cognito_user_pool_id and settings.cognito_client_id)
        self.keys = key_client or jwt.PyJWKClient(
            settings.issuer + "/.well-known/jwks.json", timeout=3, lifespan=300,
        )

    def verify(self, token: str) -> Principal:
        if not self.configured:
            raise HTTPException(503, "authentication_not_configured")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise jwt.InvalidTokenError()
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"], issuer=self.settings.issuer,
                options={"require": ["exp", "iat", "iss", "sub", "token_use", "client_id"],
                         "verify_aud": False},
            )
            if (claims["token_use"] != "access"
                    or claims["client_id"] != self.settings.cognito_client_id
                    or not isinstance(claims["sub"], str) or not claims["sub"]
                    or len(claims["sub"]) > 128 or not isinstance(claims.get("scope", ""), str)):
                raise jwt.InvalidTokenError()
            # Match API Gateway's audience behavior if a resource-bound token includes aud.
            if "aud" in claims:
                audience = claims["aud"]
                audience = [audience] if isinstance(audience, str) else audience
                if not isinstance(audience, list) or self.settings.cognito_client_id not in audience:
                    raise jwt.InvalidTokenError()
            return Principal(claims["sub"], frozenset(claims.get("scope", "").split()))
        except jwt.PyJWKClientConnectionError as exc:
            raise HTTPException(503, "authentication_keys_unavailable") from exc
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise HTTPException(401, "invalid_access_token", headers={"WWW-Authenticate": "Bearer"}) from exc


def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "bearer_token_required", headers={"WWW-Authenticate": "Bearer"})
    if len(credentials.credentials) > 8192:
        raise HTTPException(401, "invalid_access_token")
    return request.app.state.verifier.verify(credentials.credentials)


def require(scope: str):
    def dependency(user: Principal = Depends(principal)) -> Principal:
        if "ecoroute/" + scope not in user.scopes:
            raise HTTPException(403, "insufficient_scope")
        return user
    return dependency
