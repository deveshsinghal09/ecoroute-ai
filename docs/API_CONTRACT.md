# API contract — backend foundation and environmental datasets

Final allowance release verified: Core UPDATE_COMPLETE, deployed100daily/100hourly, new Amplify
retry messages served and browser comparison returned2routes with full forecast coverage.


## Routing rate-limit responses - 2026-10-11

429 retains error.code/request_id. Known exhausted windows use location_hourly_budget_exhausted
or location_daily_budget_exhausted and numeric Retry-After seconds. Unknown-window fallback remains
location_request_budget_exhausted. Retry-After is exposed through exact-origin CORS; frontend
renders only a validated positive integer<=86400 as approximate wait minutes. No automatic retry
or provider-body exposure. Allowances count shared provider calls, not returned route candidates.


## Outside-Delhi verification follow-up - 2026-10-11

User confirmed the deployed Drive comparison now works. Real Mumbai Gateway of India->Marine
Drive preview returned HTTP200/twoGoogle routes (6119m/1191s and4191m/1227s). PM2.5 coverage0,
exposure null/confidence unavailable, correctly reflecting missing collected Mumbai data. Routing
is not Delhi-restricted; pollution-aware ranking needs area/time-matched collection and refresh.
Safe frontend error-message changes are committed/pushed; latest public bundle inspection did
not yet contain them, so no Amplify deployment completion is claimed. No new AWS/IAM changes.


## Safe client errors - 2026-10-11

HTTP error schema is unchanged: error.code/error.request_id. Client maps recognized routing
provider/secret/storage/allowance codes to safe explanatory text. For5xx only,32lowercasehex
request IDs may be shown as references. Arbitrary codes/details/reference strings are never
rendered. Actual Amplify guest Drive returned routes/forecast exposure; specific user503 pending.


## Live exposure verification - 2026-10-11

No schema/auth change. /routes/preview verified HTTP200 for Delhi Drive/Walk/Cycle with
pm25_coverage_fraction~1 and non-null estimated_pm25_exposure_ug_h_m3. Unit ug*h/m3; arithmetic
matches sum(segment concentration*duration_s/3600). Pollutants retain forecast/source/time/45km
resolution; confidence low, spatial_differentiation=not_resolved_same_model_cell. Later departure
uses corresponding forecast. Private wearable/alerts remain401 without JWT; no positive login claim.


## Collector result verification - 2026-10-11

No API contract change. Raw ingestion success does not establish available concentration/exposure. Curated coverage must be checked before route results can report full exposure; missing values remain unavailable.


## Activation walkthrough - 2026-10-11

No HTTP contract changed. AWS_ROUTE_AIR_SETUP.md gives compare/selected-route air display semantics:
PM2.5 ug/m3 and concentration-time exposure, not AQI or guaranteed street-level pollution differences.
Guest routing is request-only; private data/quality/ML/alerts require a verified Cognito access token.


## Route factors and prediction comparison - 2026-10-11

Request fields: weather_weight, terrain_weight, avoid_tolls/highways/ferries/steps. Nonnegative
weights+exposure_weight<=1; mode restrictions validated. Typed optional weather/terrain response
metadata; Google routing_source.traffic duration/historical-baseline seconds. JWT write-protected
POST /api/v1/routes/predict extends CompareRequest with station_ids1..20 and optional model_version;
returns full RouteComparison geometry plus forecasts, model versions and horizon1. Missing approved
model/fresh observations503; invalid input422. Runtime OpenAPI/Postman index exported. Definitions
and foreign/synthetic-model exclusions are in ROUTE_FACTORS.md and LARGE_DATA_TRAINING.md.


## Cognito registration and hosted Maps - 2026-10-11

No HTTP schema changes. Cognito hosted Sign up now available with email confirmation; JWT scope enforcement unchanged. Frontend setup errors distinguish hosted Amplify variables from local env files.

## Provider secrets connected � 2026-10-11

POST /api/v1/routes/preview now enabled in deployed API without JWT, bounded and no personal journey persistence. All3modes returned200; full PM2.5 exposure null when data missing. Private APIs unchanged. No schema change; correct fields duration_s and estimated_pm25_exposure_ug_h_m3.

## Uniform API key secret format � 2026-10-11

Routing secret configuration accepts api_key JSON or legacy plaintext, no HTTP schema change. No secret data returned to clients.

## Core live verification � 2026-10-11

Live API base: https://j1lgox7e00.execute-api.ap-south-1.amazonaws.com. Health200/OpenAPI200; private endpoints401 without token. CORS exact Amplify domain. No request/response schema change; public route scope infrastructure fixed.

## Mapping cleanup correction — 2026-10-11

Core DELETE_FAILED, no AWS API URL. Mapping permission correction introduces no HTTP schema change.

Latest Core ROLLBACK_FAILED; AWS URL unavailable. Workflow naming fix/API mapping read policy
correction introduce no HTTP schema changes. Live health/authentication tests still blocked.


Latest Core attempt failed on CloudWatch log-delivery authorization; no cloud API URL tested.
API schema unchanged. Health/authentication live checks must wait for successful deployment.


Latest Core retries failed stage tagging authorization after Cognito fix; no AWS base URL
verified. Schemas unchanged; local API remains the available runtime.


Follow-up: disabled IoT stack deployed; this creates no HTTP endpoint or public health access.
Core rollback remains complete; AWS API base URL still unavailable. Existing schemas unchanged.


Cloud status 2026-10-11: Data/ML preparation deployed, Core deployment failed on Cognito MFA
configuration permission and is rolling back. No AWS API base URL has passed runtime tests;
use existing local endpoints. CloudFront separately blocked by account verification. No API
schema changes are introduced by this infrastructure correction. See PROJECT_STATE.md.


## Owner-only Health Connect GETs — 2026-10-11

Added /api/v1/wearables/health-connect/status, /data and /summary. Bearer required; owner-bound
Cognito ecoroute/read or expiring local loopback pairing key. Data/summary additionally require
consent=true. Existing private endpoint authentication is unchanged. days1–30(default7),
explicit cached flag, summary selected_date and IANA timezone_name; browser sends its own zone.
Eight metrics return typed value/unit/status/time/source/resolution/warnings; unavailable=null,
not a zero reading. Daily overlap/future projection/cross-midnight ambiguity is explicit.
No-store responses, no permanent health storage. Errors additionally include502/504 for phone
responses/timeouts. Runtime OpenAPI and Postman now contain46 operations. Exact models and
local setup are in [HEALTH_CONNECT.md](HEALTH_CONNECT.md) and the exported full contract.

AWS preparation (2026-10-11): budget creation is user-confirmed; bootstrap/backend remain
undeployed. New scoped deployment IAM and optional workload boundary introduce no REST operation
in this change. Cognito ownership/consent checks remain required on private deployed APIs.
There is no cloud backend URL to configure yet; follow AWS_CONSOLE_BOOTSTRAP.md before deployment.

AWS assessment update (2026-10-11): IAM diagnostic attachment/read access is verified; no AWS
backend URL exists because bootstrap/project stacks are absent. Existing endpoint schemas,
Cognito ownership/consent protections and local functionality are unchanged. A metadata-read
policy is not application authentication or deployment permission. No new live data/model is
claimed by this diagnostic update.

Service-profile update (2026-10-10): the 42 existing business API operations and their schemas
are unchanged. Alternative FastAPI runtimes retain the same Cognito/ownership validation.
Gateway HTTP proxy handoff explicitly forwards `$request.path` and preserves read/write scopes.
Lightsail only forwards authenticated `/api/v1/*` requests to the existing Gateway and adds
its own infrastructure `/healthz`; it does not add public personal-data APIs. SQL analytics is
an internal anonymous report sink, not a new client-facing endpoint. Hosting needs the real
API URL/public Cognito configuration baked into the existing build and exact CORS/callbacks.

The newly authorized frontend consumes this existing contract; no endpoint was weakened or
renamed. Source: frontend/src/api.ts (PKCE/authenticated REST), frontend/src/data.ts (real historical
response), frontend/src/App.tsx (route/quality/wearable/alerts/ML/explanation clients). Historical
and live states are explicit and mutually exclusive. API Gateway CORS now accepts an optional
reviewed frontend_origins list. No unauthenticated domain data endpoint was added.

Phase7 authoritative complete contract: [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)
and runtime-exported [openapi.json](openapi.json). All42operations have explicit request/response
schemas, authorization scope, errors and Postman examples. Run scripts/export_api.py after API
changes; CI checks for drift. Legacy placeholder operations are marked deprecated/unavailable;
their presence is not proof of implemented live functionality. GeoJSON is longitude/latitude;
PM2.5 exposure is ug·h/m³; timestamps include timezone. Partial exposure remains null.
Local /ready is public; the AWS Gateway route requires read scope. No WebSocket is implemented.

Phase5 wearable contracts (full schemas at /docs; examples/limits in WEARABLES.md):

| Endpoint | Contract |
|---|---|
| POST /api/v1/devices/register |write; Idempotency-Key; manufacturer/model/bridge; owned random device, initial consent false |
| POST /api/v1/wearables/consent |write; device_id and explicit telemetry/location/history/correlation scopes, wearable-v1 policy; atomic revision/revocation |
| POST /api/v1/wearables/measurements |write; owned device/user,event ID,timestamp, optional HR/activity/steps/GPS and provenance;201 accepted/200 identical duplicate/409 changed event |
| GET /api/v1/wearables/latest |read; owned device_id, latest observed time, unavailable if no readings |
| GET /api/v1/wearables/history |read+history consent; device_id,aware start/end within7d, limit1–200,cursor; private bounded records |
| DELETE /api/v1/wearables/data |write; device_id; revoke/disable then bounded primary deletion, repeat while pending; streams/retry retention up to24h |
| GET /api/v1/journeys/{journey_id}/wearable-correlation |read+correlation consent; owned device_id/journey/linked route; time/GPS paired environmental provenance, no dose/causal score |

POST /trips now optionally links an owned stored route_id. Legacy /wearables/telemetry returns
410 after authentication/validation to prevent consent-revocation bypass. Future bridges must
preserve permissions/source IDs/units and never claim watch MQTT/air pollution capability.

Phase 4 adds these protected endpoints, with unchanged Cognito scopes and body/security limits:

2026-10-10 data follow-up: local station metadata now contains100 discovered OpenAQ entries;
history/current can retrieve five real GK1 PM2.5 observations after authorized ingestion.
Existing freshness/coverage limits still apply. No provider is called from API queries and no
verified ML model is available. These data updates do not change endpoint schemas or authentication.

| Endpoint | Scope and behavior |
|---|---|
| GET /api/v1/ml/status | read; registry readiness, no fabricated accuracy |
| GET /api/v1/ml/models | read; bounded model metadata |
| GET /api/v1/ml/metrics | read; verified selected version's actual held-out metrics; 503 if unavailable |
| POST /api/v1/ml/predict | write; station_id, optional model_version/current issued_at; next-hour station PM2.5 |
| POST /api/v1/ml/batch-predict | write; station_ids1–20, optional model_version/current issued_at; per-station availability |
| POST /api/v1/routes/predict-departure-times | write; existing departure comparison body plus station_ids/model_version; genuine road routes with matched station prediction proxies |

ML response carries station coordinates, model_version, horizon_hours1, valid_at, concentration
ug/m3, station_prediction kind, qualitative confidence, null interval and warnings. No verified
model/fresh supported history returns unavailable, not invented predictions. Route joins require
within1km and30minutes of valid time; missing matches retain separately labelled provider/grid
coverage. Routes never infer street precision from station proximity. See ML_WORKFLOW.md for
sample bodies and horizon/availability limits. Legacy /predictions remains a placeholder.

Base path `/api/v1`. Exact request/response schemas are generated at `/openapi.json` and `/docs`.
All domain routes require RS256 Cognito access JWTs: issuer, client_id, expiry, token_use and scope
are verified in FastAPI and JWT/scopes additionally in API Gateway. No user identity in request
payloads can override token ownership. `ecoroute/read` for GET; `ecoroute/write` for POST/PUT/DELETE.

| Endpoint | Behavior |
|---|---|
| GET /api/v1/health (alias /healthz) | Public 200 liveness; no downstream calls |
| GET /api/v1/ready | 200 or 503 for storage/auth configuration; gateway-protected in AWS, loopback diagnostic locally; not a provider or JWKS network probe |
| GET /docs, /openapi.json | Public technical API documentation |
| POST /api/v1/trips | Consent and validated trip details; Idempotency-Key; 201 first create, 200 identical replay, 409 changed body |
| GET /api/v1/trips/{trip_id} | Owner only; 404 for expired, missing or another user's trip |
| POST /api/v1/wearables/telemetry | Legacy contract; authenticated valid requests410; migrate to device registration/scoped consent/measurements |
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
# Phase 6 protected advisory APIs

| Endpoint | Contract |
|---|---|
| POST /api/v1/ai/explain-route | write;1–6 owned 32hex route_ids sharing a documented baseline; approved text/fallback, stored metrics and sanitized provenance; scores unchanged |
| POST /api/v1/alerts/evaluate | write; source openaq/open_meteo,location_id,aware hour-aligned end_at,notify=false; complete24h PM2.5 guidance or unavailable; owned dedup alert; SMS accepted is not delivered |
| GET /api/v1/alerts | read; owned alerts only, bounded50 records and truncation flag |
| PUT /api/v1/alerts/preferences | write; alerts_enabled explicit,channel in_app/sms; no caller-supplied phone/topic |
| POST /api/v1/schools/compare-routes | write; school_id/name/position/grid,commute_start/end,nested route CompareRequest with consent; true provider routes, matching destination/grid/commute; persists owned config90days |
| GET /api/v1/schools/forecast | read;owned school_id,optional forecast_date default next India day; explicit approximate India school-day UTC24h forecast window,confidence,coarse/missing warnings,no official closures |
| GET /api/v1/workflows/status | read; configured ARN presence,owner manifests/truncation; no public workflow start or cloud deployment verification claim |

Strict bodies reject extra fields/spoofed owner IDs. All endpoints reuse existing JWT scopes,
body limit, secure no-store headers and exact CORS. Alert units ug/m3 are not AQI; WHO daily
guidance is not an instant threshold. Next-hour station ML is not a next-day school forecast.
Full schemas at /docs; examples/setup/limitations in PHASE6_ADVISORIES.md.

Cinematic frontend revision (2026-10-10): presentation-only scene modes and planner visibility;
no HTTP request/response contracts changed. The rendered city image is not route geometry.

## Google routing integration (2026-10-10)
See docs/GOOGLE_MAPS_SETUP.md (repository root) for separate server/browser keys, APIs, Cognito,
restricted secret IAM and verification. Google Routes/Places feed the existing exposure engine;
Journeys displays Maps JavaScript tiles and route overlays. Live provider verification is recorded below.
Google comparisons are request-only; saved route-ID workflows are unavailable for those results.
No AWS resources were deployed. Google charges are separate from AWS credits.

Custom smartwatch preview adds no API routes or schema changes. Its seven screens are explicitly
local demo state; existing authenticated wearable API requests remain in the original panel.

## Public map and travel modes — 2026-10-10

New public POST /api/v1/routes/preview: PreviewRequest (consent_to_store=false, max_alternatives<=2, segment_length_m>=250) -> RouteComparison, persistence=request_only. Enabled explicitly; otherwise guest_routes_disabled (503). Request-only Google provider required. Drive/Walk dispatch to Google; Cycle dispatches to configured ORS, otherwise cycling_provider_not_configured (422) / cycling_key_missing (503). Private /routes/compare and wearable/health/owned APIs remain protected. New OpenAPI/Postman/FRONTEND_INTEGRATION exports include this operation. Named Point inputs are used for map picks; GeoJSON outputs retain [longitude,latitude].

## Geographic selection — 2026-10-11

No request/response schema or endpoint changed. Google text geocoding no longer imposes a Delhi
bias/India region and accepts valid worldwide coordinates where provider coverage permits.
Legacy AWS/OSRM profiles remain Delhi-limited; route comparisons remain bounded to 100km/six hours.
Invalid/non-finite coordinate responses fail with invalid_geocoding_coordinates (422); ambiguous
place searches require selecting an exact map point. Live fields begin empty and geolocation is
an explicit browser action, not inferred account/device location. Source resolution/coverage still
govern exposure availability. Local Google/ORS comparisons and guest browser drawing are verified;
no deployed API URL or global air-quality coverage is implied.

## Wearable display adapter — 2026-10-11

No HTTP schema or endpoint changed. Standard browser Bluetooth readings stay local and are never
sent to a public health endpoint. Protected GET /wearables/latest retains ownership, Cognito and
consent checks; the frontend maps only explicitly non-synthetic BPM/daily_total steps. Interval
counts are not shown as daily totals, timestamps need timezone information and missing fields
remain unavailable. Backend values are manual snapshots. Standard BLE provides no observation
timestamp; its browser receipt time is labeled explicitly and cannot be silently substituted for
a device observation timestamp in the existing Measurement API. A verified future companion bridge
must follow the unchanged Registration/Consent/Measurement schemas. See LIVE_WATCH_SETUP.md.

## Gemini explanation provider — 2026-10-11

Existing protected POST /api/v1/ai/explain-route retains its route_ids request and Explanation
response. With explicitly configured Gemini it returns mode=gemini_arranged_approved_text;
scores/ranking never change. Missing/invalid provider output or bounded request exhaustion
returns deterministic mode and gemini_unavailable_or_invalid_output/gemini_request_limit.
Only server-owned route facts are passed, without geometry, user/health/place/provider prose.
API and Cognito ownership/scopes remain unchanged. Guest Google request-only Insights does not
invoke this saved-route API and remains deterministic. See AWS_READINESS_AND_GEMINI.md.
No deployed API URL, successful Gemini call or trained-model result is claimed.
