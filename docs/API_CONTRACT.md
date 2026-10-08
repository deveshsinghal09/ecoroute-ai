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

## Phase 3 routes (implemented)

All endpoints below are authenticated; POST requires ecoroute/write and GET requires ecoroute/read.
Owner comes exclusively from the verified JWT subject. A different owner gets 404.

| Endpoint | Contract |
|---|---|
| POST /api/v1/routes/compare | All valid provider candidates, full segment scores, baseline, recommendations and exclusions |
| POST /api/v1/routes/optimize | Selected full route and recommendation/baseline metadata |
| POST /api/v1/routes/exposure | Owned route_id plus optional departure_at; recalculate pollution on stored geometry/duration, no invented input geometry |
| POST /api/v1/routes/departure-time-analysis | Compare request plus 1–3 unique departures; summary per time with retrievable route IDs |
| GET /api/v1/routes/{route_id} | Owned, unexpired scored route with geometry; segments fetched separately |
| GET /api/v1/routes/{route_id}/segments | offset 0–600, limit 1–200 (default100); segments, total, next_offset |

Compare/optimize body accepts origin/destination as {longitude,latitude} or nonempty place text
3–200 characters; mode walking/driving/cycling, aware departure_at, objective fastest /
lowest_exposure / balanced, max_detour_percent 0–100 (default25), exposure_weight 0–1 (default0.5),
segment_length_m 100–1000 (default250), max_alternatives 0–5 (default2), consent_to_store=true.
Departure must be no more than 48 hours ahead (five minutes clock tolerance); it is normalized
to UTC. Delhi coverage bounds are longitude76.8–77.6, latitude28.3–29.0. Cycling currently returns
422 because neither configured adapter implements a supported bicycle profile.
Departure analysis retains the required departure_at field and uses the explicit departures list.

```powershell
$body = @{
  origin = @{ longitude = 77.2295; latitude = 28.6129 }
  destination = @{ longitude = 77.2167; latitude = 28.6315 }
  mode = 'driving'
  departure_at = (Get-Date).ToUniversalTime().AddMinutes(10).ToString('o')
  objective = 'balanced'; max_detour_percent = 25; consent_to_store = $true
} | ConvertTo-Json
# Configure ACCESS_TOKEN privately after Cognito login; do not print it.
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/routes/compare -Method Post -ContentType application/json -Body $body -Headers @{Authorization="Bearer $env:ACCESS_TOKEN"}
```

Each route returns route_id, GeoJSON geometry [lon,lat], duration_s, distance_m,
estimated_pm25_exposure_ug_h_m3 (nullable), known_pm25_exposure_ug_h_m3,
pm25_coverage_fraction, relative_exposure_change_percent (nullable), baseline_route_id,
routing_source, source_metadata, confidence, pollutants, segments, warnings and recommendation_reason.
Segments contain geometry, distance/duration, arrival/sample/end times, pollutant concentrations
with kind/source/quality/resolution and pm25_exposure_ug_h_m3 contribution. No medical dose is claimed.
See ROUTING.md and the actual generated work/phase3-demo.json for a fully populated local response.

Comparison returns selected_route_id, recommended_route_ids (fastest/lowest_exposure/balanced),
baseline_definition, score_definition, spatial_differentiation and cache_hit. Missing coverage
produces null full exposure, never zero. Positive relative change means more exposure than the
fastest returned baseline; negative means less. All candidates sharing a coarse cell explicitly
warn that street-level differences are unresolved. Provider alternatives are not guaranteed.

Additional failures: 422 unsupported mode/area/route/geocoding, 429 application request budget,
502 malformed provider geometry/schema, 503 credentials/provider/dependency unavailable.
Existing /navigation/routes remains a legacy placeholder; clients should use /routes/compare.
