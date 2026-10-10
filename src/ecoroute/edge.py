"""Lightsail HTTPS companion proxy. No AWS credentials, storage or authentication bypass."""
import os
import json
import time
import uuid
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


def create_edge(origin=None, transport=None):
    origin = origin or os.environ.get("UPSTREAM_API_ORIGIN", "")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("UPSTREAM_API_ORIGIN must be an exact HTTPS origin")
    api = FastAPI(docs_url=None, openapi_url=None, redoc_url=None)

    def failure(request, code, status):
        headers = {"cache-control": "no-store"}
        if status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse({"error": {"code": code, "request_id": request.state.request_id}},
                            status_code=status, headers=headers)

    @api.middleware("http")
    async def observe(request, call_next):
        request.state.request_id = uuid.uuid4().hex
        started = time.monotonic()
        response = await call_next(request)
        if "x-request-id" not in response.headers:
            response.headers["x-request-id"] = request.state.request_id
        print(json.dumps({"event": "edge_request", "request_id": request.state.request_id,
                          "status": response.status_code, "latency_ms": round((time.monotonic() - started) * 1000)}))
        return response

    @api.get("/healthz")
    def health():
        return {"status": "ok", "role": "authenticated_api_proxy"}

    @api.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    async def forward(path: str, request: Request):
        if any(c in path for c in ("\\", "\r", "\n")) or any(part in (".", "..") for part in path.split("/")):
            return failure(request, "invalid_path", 400)
        if path != "health" and request.method != "OPTIONS" and not request.headers.get("authorization", "").startswith("Bearer "):
            return failure(request, "authentication_required", 401)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 262144:
                return failure(request, "request_too_large", 413)
        headers = {k: v for k, v in request.headers.items() if k.lower() in
                   {"authorization", "content-type", "accept", "idempotency-key", "origin", "access-control-request-method", "access-control-request-headers"}}
        try:
            async with httpx.AsyncClient(transport=transport, timeout=28, trust_env=False, follow_redirects=False) as client:
                result = await client.request(request.method, origin.rstrip("/") + "/api/v1/" + path,
                    params=list(request.query_params.multi_items()), content=bytes(body), headers=headers)
            safe_headers = {k: v for k, v in result.headers.items() if k.lower() in
                {"content-type", "x-request-id", "access-control-allow-origin", "access-control-allow-methods", "access-control-allow-headers", "access-control-expose-headers", "vary", "retry-after"}}
            return Response(content=result.content, status_code=result.status_code,
                            headers={**safe_headers, "cache-control": "no-store"})
        except httpx.HTTPError:
            return failure(request, "upstream_unavailable", 502)
    return api


# Import is safe for offline tests; a deployed proxy requires explicit configuration.
app = create_edge() if os.environ.get("UPSTREAM_API_ORIGIN") else FastAPI(docs_url=None, openapi_url=None)
