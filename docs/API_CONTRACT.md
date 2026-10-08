# API contract — version 0.0.1

Only `GET /healthz` and `GET /openapi.json` exist. `/healthz` returns HTTP 200 with
`{"status":"ok","profile":"local","phase":"0-scaffold","integrations_enabled":false}`.
Liveness is not proof of AWS access, pollution coverage or model readiness. No frontend exists.
Interactive Swagger/Redoc pages are disabled; OpenAPI JSON remains available.

## Proposed Phase 1+ endpoints (not implemented)

| Endpoint | Auth / input | Response / constraints |
|---|---|---|
| POST /v1/routes | routes:read; origin/destination lon+lat, departure_at RFC3339 UTC, travel_mode, maximum detour ratio, pollution weight | 200 alternatives with GeoJSON LineString, duration_s, distance_m, concentration-time exposure, units, coverage_fraction, provenance, warnings and ranking version; 503 when route provider unavailable |
| GET /v1/air-quality | air:read; bbox or lon+lat, pollutant, time | measured/estimated/missing status, source, timestamps, units, quality flags; never synthetic data labeled observed |
| GET /v1/forecasts | air:read; bounded area, horizon | forecast series, model_version, issued_at, valid_at, evaluation reference; 503 forecast_unavailable until trained/published |
| POST /v1/exposure/sessions | exposure:write; consent and start time | 201 opaque session ID owned by token subject |
| POST /v1/exposure/sessions/{id}/samples | exposure:write; timestamped GPS samples and accuracy; Idempotency-Key | 202 accepted event count/job ID; deduplicate, cap batch 100 points / 256 KiB |
| GET /v1/exposure/sessions/{id} | exposure:read, owner | summary and coverage, 404 for absent or other-user objects |
| DELETE /v1/exposure/sessions/{id} | exposure:write, owner | 202 deletion job; status via job resource |
| POST /v1/wearables/imports | wearable:write; consent, source/model, metric, unit, timestamps | 202 import job, provenance identifies real export versus synthetic fixture; no claimed Noise connection |
| GET /v1/jobs/{id} | authenticated owner | queued/running/succeeded/failed plus redacted failure code |

Validate finite coordinates (longitude -180..180, latitude -90..90), supported Delhi coverage,
ordered timestamps, bounded date ranges and travel modes verified against the provider. Coordinate
request objects use named longitude/latitude to reduce swaps; convert to GeoJSON lon-first internally.
Reject unknown fields and oversized bodies. Pagination uses opaque cursors and explicit limits.
Error envelope will be `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`.
Use 401 unauthenticated, 403 insufficient scope, 422 invalid input, 409 idempotency conflict,
429 rate limited with Retry-After, 502 upstream failure and 503 required data unavailable.
An absent pollution estimate is null with a reason, never zero. Include data_mode=real/fixture,
observed_at, source, model_version (nullable) and estimated coverage with every domain response.
Do not calculate multi-pollutant exposure by adding incompatible units.

JWT checks, error envelope and all domain routes are planned; Phase 0 uses FastAPI's default 404.
AWS HTTP API will use payload format 2.0; Mangum event tests belong to the deployment phase.
