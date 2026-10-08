# API contract — backend foundation and environmental datasets

Base path `/api/v1`. Exact request/response schemas are generated at `/openapi.json` and `/docs`.
All domain routes require RS256 Cognito access JWTs: issuer, client_id, expiry, token_use and scope
are verified in FastAPI and JWT/scopes additionally in API Gateway. No user identity in request
payloads can override token ownership. `ecoroute/read` for GET; `ecoroute/write` for POST/PUT.

| Endpoint | Behavior |
|---|---|
| GET /api/v1/health (alias /healthz) | Public 200 liveness; no downstream calls |
| GET /api/v1/ready | 200 or 503 for storage/auth configuration; gateway-protected in AWS, loopback diagnostic locally; not a provider or JWKS network probe |
| GET /docs, /openapi.json | Public technical API documentation |
| POST /api/v1/trips | Consent and validated trip details; Idempotency-Key; 201 first create, 200 identical replay, 409 changed body |
| GET /api/v1/trips/{trip_id} | Owner only; 404 for expired, missing or another user's trip |
| POST /api/v1/wearables/telemetry | Consent, ordered timestamped batch <=100, past 7 days; idempotency required; returns ID/count without private samples; no claimed device connection |
| GET, PUT /api/v1/alerts/preferences | Owner-scoped notification preferences; no messages sent |
| GET /api/v1/alerts/{alert_id} | Owner-scoped stored alert; no generation engine yet |
| POST /api/v1/navigation/routes | Validates coordinates/travel inputs then 503 routing_provider_not_connected |
| GET /api/v1/predictions | Validates coordinates and horizon 1..6h then 503 forecast_model_unavailable |
| GET /api/v1/school-safety | Validates coordinates then 503 school_safety_data_unavailable |
| GET /api/v1/air-quality | Legacy point query validates coordinates then 503; no unsupported street interpolation |
| GET /api/v1/air-quality/current | Required location_id; source=openaq (default) or open_meteo; latest non-null per sensor/pollutant within 6h |
| GET /api/v1/air-quality/forecast | Required model location_id; hours 1..48 (default24); Open-Meteo latest retrieval vintage <=24h old |
| GET /api/v1/air-quality/stations | Locally indexed OpenAQ station metadata, max 100; empty until station discovery/measurement ingestion |
| GET /api/v1/air-quality/history | source, location_id, timezone-aware start/end, maximum 7d |
| GET /api/v1/data/quality | source (default open_meteo); latest 10 ingestion quality reports |

Dataset queries never call external providers. They query at most 20 indexed Parquet objects and
return at most 200 records, with `truncated: true` if a limit is reached. For fuller exports use
curated Parquet; narrower dates can reduce truncation. This is bounded demo retrieval, not a
complete arbitrary-history export or a geospatial search engine. There is no pagination cursor yet.
Unknown location or empty coverage returns HTTP200 with `status: unavailable`, empty `records`.
Provider outages leave prior data intact; data age and retrieval timestamps expose staleness.

Each record includes source, observed/forecast/modeled kind, pollutant, nullable concentration,
unit ug/m3, original value/unit, UTC reported/collected timestamps, optional averaging-period
start, station/sensor/grid ID, coordinates, quality flags, provider quality, resolution/model
metadata, provenance JSON and raw-object key. Open-Meteo issue/run time is null when not supplied.
AQI is not a concentration and is not returned by these adapters. No gap filling or accuracy claim.
`current` excludes null/invalid/provider-flagged concentrations; history preserves them for audit.
Forecast valid times that have passed are described as modeled in `current`.

Request body limit 256KiB. Finite bounded coordinates, unknown-field rejection, generic 422 errors.
Other responses: 401 invalid/missing token, 403 missing scope, 404 inaccessible object,
409 idempotency conflict, 413 oversized body, 503 dependency failure; cloud gateway may throttle 429.
Application errors: `{"error":{"code":"...","request_id":"..."}}`; gateway errors can differ.
Responses carry no-store and request IDs. Logs exclude bodies, bearer tokens and query strings.
No wildcard production CORS; configure exact HTTPS origins only when a future client is selected.
