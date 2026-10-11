# Frontend integration — EcoRoute AI backend

The React/Three.js frontend lives in frontend/; local UI: http://127.0.0.1:5173.
Backend local base URL: http://127.0.0.1:8000. See frontend/README.md for PKCE and live-mode setup.
AWS base URL: https://j1lgox7e00.execute-api.ap-south-1.amazonaws.com (Core runtime verified).
Authoritative request/response schemas: [openapi.json](openapi.json), exported from the SAME
runtime /openapi.json. Provider metadata and variable model metrics intentionally allow extra
properties; stable fields have explicit types. Error schemas describe normalized backend
errors; an upstream API Gateway rejection/throttle can have its own AWS error envelope.

Route factors: see [ROUTE_FACTORS.md](ROUTE_FACTORS.md). Compare/preview requests accept weather_weight,
terrain_weight and mode-specific avoidance flags in addition to exposure_weight. Optional weather,
terrain and routing_source.traffic fields retain units/source/status. Protected POST /routes/predict
returns full geometry using verified station predictions only; foreign/synthetic artifacts are blocked.
Experimental training results and SageMaker prerequisites: [LARGE_DATA_TRAINING.md](LARGE_DATA_TRAINING.md).

Use Cognito public client authorization-code flow with S256 PKCE. Configure an approved HTTPS
callback using CDK callback_urls, request openid and ecoroute/read ecoroute/write scopes, validate
state, exchange code/verifier at Cognito /oauth2/token. Never put an app secret/AWS key in a SPA.
Send Authorization: Bearer <ACCESS_TOKEN>, NOT the ID token. Backend verifies RS256 signature,
issuer, client_id, token_use=access, expiry, subject and required scope. Server derives ownership
from verified sub; another owner's IDs return404 or denied consent. Default local mode has NO
JWT bypass: unconfigured Cognito gives503 with a supplied bearer; missing bearer gives401.
An offline demo uses ephemeral signed test tokens ONLY inside an isolated TestClient process.
Google Maps display is public and needs only the restricted browser key. POST /api/v1/routes/preview
is a separate guest endpoint, disabled by default unless ENABLE_GUEST_ROUTES=true. It accepts
PreviewRequest (consent_to_store=false) and only request-only Google/optional ORS comparisons.
It never creates journeys, route caches or saved coordinates, and shares global provider budgets.
The AWS public POST route is defined only with CDK enable_guest_routes=true plus a Google secret.
Cognito remains mandatory for every existing private route, location, health, wearable and alert API.
Three NEW local phone-bridge GETs under /wearables/health-connect/ also accept an expiring,
read-only local pairing bearer. It is restricted to the backend's loopback address, approved
origins and configured phone owner; it never signs in to other APIs. Explicit consent=true
is required for data and summary. See HEALTH_CONNECT.md. No pairing key belongs in VITE_ env.
Local /api/v1/ready is public; deployed API Gateway requires the ecoroute/read scope for it.

## Geometry, units and confidence

The wearable screen has an optional consent-based standard Web Bluetooth adapter. Those readings
stay in browser memory; no anonymous health API or cloud upload exists. BLE timestamps describe
receipt time, not device observation time. GET /wearables/latest is still authenticated and maps
only non-synthetic available fields as a manual snapshot. Unknown vendor packets are not decoded;
the Noise adapter remains blocked pending a verified SDK/export. See LIVE_WATCH_SETUP.md.
Health Connect reads the Android app's documented local JSON API server-side. Fresh days1–30
reads are distinct from cached/incremental /latest. Eight summary metrics have explicit
available/unavailable states, units, record timestamps, source packages, resolution and warnings.
The browser sends its IANA timezone and selected calendar date; daily counts are not prorated
across midnight. Overlapping counts/projected future energy intervals produce unavailable totals.
Sleep is a union of recorded session intervals ending on the selected day, including any awake
time; not a scored or diagnosed sleep assessment. No raw health records are persisted/uploaded.

GeoJSON geometry is {"type":"LineString","coordinates":[[longitude,latitude],...]} in WGS84.
These are provider road routes, not straight-line substitutes. JSON Point inputs instead use
named longitude/latitude. Benchmark landmarks are approximate map coordinates, snapped by
the routing provider; no surveyed precision is claimed. Driving and walking are supported
where the provider permits. Google geocoding/coordinates are not restricted to Delhi; comparisons
remain limited to 100km and six hours. Legacy AWS/OSRM profiles retain their Delhi boundary.
Cycling is dispatched to openrouteservice cycling-regular
when CYCLING_PROVIDER=openrouteservice and its backend key are configured; otherwise an explicit
error is returned. Google currently does not list bicycle or photorealistic 3D coverage for India.
The map uses genuine satellite/streets with a vector tilted camera where supported.

PM2.5/PM10/NO2/O3 concentrations use ug/m3, not AQI. Aware ISO8601 timestamps include UTC offset;
backend normalizes to UTC. duration_s is seconds, distance_m is meters. PM2.5 exposure index
= sum(segment concentration * duration_s/3600), unit ug*h/m3; never actual dose/diagnosis.
Full exposure is null when coverage is incomplete; known_pm25_exposure_ug_h_m3 is a partial contribution.
Coverage uses pm25_coverage_fraction. recommended_route_ids contains fastest, lowest_exposure,
balanced; unavailable categories are null. Baseline is fastest RETURNED route at SAME departure.
relative_exposure_change_percent=(route-baseline)/baseline*100; negative means estimated reduction.
No percentage is inferred when baseline/full exposure is unavailable or baseline is zero.
Detour uses travel time. Balanced min-max score is meaningful only with complete eligible coverage.

Environmental kind/status distinguishes observed, forecast, modeled and unavailable.
routing_source.fixture=true marks recorded geometry, NOT fabricated measured pollution.
Telemetry provenance.synthetic=true and bridge=demo require explicit local demo mode.
Bedrock mode=deterministic means fallback; bedrock_arranged_approved_text means a validated model
response arranged server sentences. SNS accepted is not delivered. hardware_connected=false is
not physical watch verification. No data/model/deployment flag may be inferred from health200.
Coarse CAMS global support is about45km, native3-hourly interpolated to hourly. Small route
segments do not increase pollution resolution. confidence/quality warnings and source timestamps
must remain visible. A station value is a nearby proxy; a one-hour station prediction is not
a grid forecast or validated street-level reading. No verified measured-data model currently exists.

## Errors and privacy

Backend errors: {"error":{"code":"validation_error","request_id":"opaque_id"}}.
401 missing/invalid bearer;403 scope/consent;404 absent/other owner's record;409 idempotency/state;
413 body over256KiB;422 validation/unsupported route;429 request budget;500 unexpected failure;
503 dependency/auth/provider/model unavailable. /ready503 uses {"status":"not_ready"}.
Phone-bridge responses additionally use502 for invalid/failed provider responses and504 for
timeouts. Missing readings return null with unavailable status, never synthetic zero values.
Idempotency-Key is required for trip/device registration; same body replays200, changed body409.
Route compare/exposure results are bounded; segment/history queries paginate. Respect truncated
and next_offset/next_cursor; unavailable is NOT a zero concentration or a safety guarantee.

Wearables: register device, explicitly consent telemetry/location/history/correlation scopes,
then post Measurement with device_id, verified user_id, event_id, aware timestamp, optional heart
rate20–250, activity, optional steps plus steps_semantics, GPS plus accuracy_m, source provenance.
At least one reading is required. Do not manufacture readings in production. Revocation blocks
future processing; deletion revokes device then requires repeated bounded requests while pending.
GPS/history/correlation each require consent. MQTT certificate enrollment is a separate operator
workflow, not a REST auth bypass. Noise ColorFit Pro3 Alpha / NoiseFit Assist hardware APIs are
unverified. Synthetic demo pairing establishes no causal relationship between HR and pollution.

Configure CORS_ORIGINS as a JSON array of exact origins, e.g. ["http://localhost:3000"] locally;
AWS origins require HTTPS. No wildcard or credentialed CORS. Poll only while an active journey:
latest telemetry every30–60s, route changes on explicit request, forecast every15–30min, alerts
every60–120s; these are suggested client intervals, subject to API limits (AWS default2req/s).
Use bounded backoff on429/503, no blind POST retries. Responses use Cache-Control:no-store;
do not persist health/GPS/token data in browser caches or shared analytics. Route cache is
server-side, owned and5minutes; privacy-sensitive responses must not be shared across users.
No WebSocket, SSE, public MQTT subscription or event-stream API is implemented. Poll REST.

## Development examples

Import examples/ecoroute.postman_collection.json and examples/ecoroute.postman_environment.json.
Environment access_token is EMPTY and secret-type; configure privately, do not export tokens.
Collection pre-request script supplies timestamps. Set IDs using real owned responses; a32hex
dummy ID is not a real record. All requests are user-triggered; do not run the whole collection
against production (it includes consent/deletion writes). Example telemetry is explicitly
synthetic/demo and rejected unless local demo mode is enabled. Environmental examples use real
queries or unavailable values; examples contain no fabricated measured pollution or trained metrics.
See DEMO_READINESS.md for repeatable benchmark, curl, deployment and cleanup instructions.
examples/delhi-recorded-response.json contains an actual historical public-landmark comparison;
its response member follows RouteComparison. File metadata marks it historical, not current.

## Endpoint index

Every request body/parameter/response JSON schema is in openapi.json at the listed operation.
GET requests have no body. Below: scope, request schema/query parameters, success response;
provider payloads/model metrics use flexible objects without pretending their contents are fixed.

| Method/path | Scope | Body / parameters | Response schema | Status |
|---|---|---|---|---|
| GET /api/v1/health | public (configuration-dependent) | none; no parameters | inline object; pointer paths/~1api~1v1~1health/get/responses | configuration-dependent |
| GET /api/v1/ready | public (configuration-dependent) | none; no parameters | inline object; pointer paths/~1api~1v1~1ready/get/responses | configuration-dependent |
| POST /api/v1/navigation/routes | ecoroute/write | RouteRequest; no parameters | ApiError; pointer paths/~1api~1v1~1navigation~1routes/post/responses | legacy unavailable/retired |
| GET /api/v1/air-quality | ecoroute/read | none; longitude, latitude | ApiError; pointer paths/~1api~1v1~1air-quality/get/responses | legacy unavailable/retired |
| GET /api/v1/predictions | ecoroute/read | none; longitude, latitude, horizon_hours | ApiError; pointer paths/~1api~1v1~1predictions/get/responses | legacy unavailable/retired |
| POST /api/v1/wearables/telemetry | ecoroute/write | TelemetryBatch; idempotency-key | ApiError; pointer paths/~1api~1v1~1wearables~1telemetry/post/responses | legacy unavailable/retired |
| GET /api/v1/alerts/preferences | ecoroute/read | none; no parameters | inline object; pointer paths/~1api~1v1~1alerts~1preferences/get/responses | configuration-dependent |
| PUT /api/v1/alerts/preferences | ecoroute/write | Preferences; no parameters | inline object; pointer paths/~1api~1v1~1alerts~1preferences/put/responses | configuration-dependent |
| GET /api/v1/alerts/{alert_id} | ecoroute/read | none; alert_id | OwnedRecord; pointer paths/~1api~1v1~1alerts~1{alert_id}/get/responses | configuration-dependent |
| GET /api/v1/school-safety | ecoroute/read | none; longitude, latitude | ApiError; pointer paths/~1api~1v1~1school-safety/get/responses | legacy unavailable/retired |
| POST /api/v1/trips | ecoroute/write | TripCreate; idempotency-key | OwnedRecord; pointer paths/~1api~1v1~1trips/post/responses | configuration-dependent |
| GET /api/v1/trips/{trip_id} | ecoroute/read | none; trip_id | OwnedRecord; pointer paths/~1api~1v1~1trips~1{trip_id}/get/responses | configuration-dependent |
| GET /api/v1/air-quality/current | ecoroute/read | none; source, location_id | DataEnvelope; pointer paths/~1api~1v1~1air-quality~1current/get/responses | configuration-dependent |
| GET /api/v1/air-quality/forecast | ecoroute/read | none; location_id, hours | DataEnvelope; pointer paths/~1api~1v1~1air-quality~1forecast/get/responses | configuration-dependent |
| GET /api/v1/air-quality/history | ecoroute/read | none; source, start, end, location_id | DataEnvelope; pointer paths/~1api~1v1~1air-quality~1history/get/responses | configuration-dependent |
| GET /api/v1/air-quality/stations | ecoroute/read | none; no parameters | inline object; pointer paths/~1api~1v1~1air-quality~1stations/get/responses | configuration-dependent |
| GET /api/v1/data/quality | ecoroute/read | none; source | inline object; pointer paths/~1api~1v1~1data~1quality/get/responses | configuration-dependent |
| POST /api/v1/routes/compare | ecoroute/write | CompareRequest; no parameters | RouteComparison; pointer paths/~1api~1v1~1routes~1compare/post/responses | configuration-dependent |
| POST /api/v1/routes/preview | public (configuration-dependent) | PreviewRequest; no parameters | RouteComparison; pointer paths/~1api~1v1~1routes~1preview/post/responses | configuration-dependent |
| POST /api/v1/routes/optimize | ecoroute/write | CompareRequest; no parameters | inline object; pointer paths/~1api~1v1~1routes~1optimize/post/responses | configuration-dependent |
| POST /api/v1/routes/exposure | ecoroute/write | ExposureRequest; no parameters | ScoredRoute; pointer paths/~1api~1v1~1routes~1exposure/post/responses | configuration-dependent |
| POST /api/v1/routes/departure-time-analysis | ecoroute/write | DepartureRequest; no parameters | DepartureAnalysis; pointer paths/~1api~1v1~1routes~1departure-time-analysis/post/responses | configuration-dependent |
| GET /api/v1/routes/{route_id} | ecoroute/read | none; route_id | inline object; pointer paths/~1api~1v1~1routes~1{route_id}/get/responses | configuration-dependent |
| GET /api/v1/routes/{route_id}/segments | ecoroute/read | none; route_id, offset, limit | inline object; pointer paths/~1api~1v1~1routes~1{route_id}~1segments/get/responses | configuration-dependent |
| GET /api/v1/ml/status | ecoroute/read | none; no parameters | inline object; pointer paths/~1api~1v1~1ml~1status/get/responses | configuration-dependent |
| GET /api/v1/ml/models | ecoroute/read | none; no parameters | inline object; pointer paths/~1api~1v1~1ml~1models/get/responses | configuration-dependent |
| GET /api/v1/ml/metrics | ecoroute/read | none; model_version | inline object; pointer paths/~1api~1v1~1ml~1metrics/get/responses | configuration-dependent |
| POST /api/v1/ml/predict | ecoroute/write | PredictionRequest; no parameters | StationPrediction; pointer paths/~1api~1v1~1ml~1predict/post/responses | configuration-dependent |
| POST /api/v1/ml/batch-predict | ecoroute/write | BatchRequest; no parameters | inline object; pointer paths/~1api~1v1~1ml~1batch-predict/post/responses | configuration-dependent |
| POST /api/v1/routes/predict-departure-times | ecoroute/write | PredictedDepartures; no parameters | DepartureAnalysis; pointer paths/~1api~1v1~1routes~1predict-departure-times/post/responses | configuration-dependent |
| POST /api/v1/routes/predict | ecoroute/write | PredictedRoute; no parameters | PredictedRouteComparison; pointer paths/~1api~1v1~1routes~1predict/post/responses | configuration-dependent |
| POST /api/v1/devices/register | ecoroute/write | Registration; idempotency-key | WearableRegistration; pointer paths/~1api~1v1~1devices~1register/post/responses | configuration-dependent |
| POST /api/v1/wearables/consent | ecoroute/write | Consent; no parameters | inline object; pointer paths/~1api~1v1~1wearables~1consent/post/responses | configuration-dependent |
| POST /api/v1/wearables/measurements | ecoroute/write | Measurement; no parameters | WearableAcceptance; pointer paths/~1api~1v1~1wearables~1measurements/post/responses | configuration-dependent |
| GET /api/v1/wearables/history | ecoroute/read | none; device_id, start, end, limit, cursor | inline object; pointer paths/~1api~1v1~1wearables~1history/get/responses | configuration-dependent |
| GET /api/v1/wearables/latest | ecoroute/read | none; device_id | inline object; pointer paths/~1api~1v1~1wearables~1latest/get/responses | configuration-dependent |
| DELETE /api/v1/wearables/data | ecoroute/write | none; device_id | inline object; pointer paths/~1api~1v1~1wearables~1data/delete/responses | configuration-dependent |
| GET /api/v1/journeys/{journey_id}/wearable-correlation | ecoroute/read | none; journey_id, device_id | inline object; pointer paths/~1api~1v1~1journeys~1{journey_id}~1wearable-correlation/get/responses | configuration-dependent |
| GET /api/v1/wearables/health-connect/status | ecoroute/read or scoped local pairing bearer | none; no parameters | HealthConnectStatus; pointer paths/~1api~1v1~1wearables~1health-connect~1status/get/responses | configuration-dependent |
| GET /api/v1/wearables/health-connect/data | ecoroute/read or scoped local pairing bearer | none; days, cached, consent | HealthConnectData; pointer paths/~1api~1v1~1wearables~1health-connect~1data/get/responses | configuration-dependent |
| GET /api/v1/wearables/health-connect/summary | ecoroute/read or scoped local pairing bearer | none; days, selected_date, timezone_name, cached, consent | HealthConnectSummary; pointer paths/~1api~1v1~1wearables~1health-connect~1summary/get/responses | configuration-dependent |
| POST /api/v1/ai/explain-route | ecoroute/write | ExplanationRequest; no parameters | Explanation; pointer paths/~1api~1v1~1ai~1explain-route/post/responses | configuration-dependent |
| POST /api/v1/alerts/evaluate | ecoroute/write | AlertRequest; no parameters | AlertEvaluation; pointer paths/~1api~1v1~1alerts~1evaluate/post/responses | configuration-dependent |
| GET /api/v1/alerts | ecoroute/read | none; no parameters | inline object; pointer paths/~1api~1v1~1alerts/get/responses | configuration-dependent |
| POST /api/v1/schools/compare-routes | ecoroute/write | SchoolRequest; no parameters | inline object; pointer paths/~1api~1v1~1schools~1compare-routes/post/responses | configuration-dependent |
| GET /api/v1/schools/forecast | ecoroute/read | none; school_id, forecast_date | inline object; pointer paths/~1api~1v1~1schools~1forecast/get/responses | configuration-dependent |
| GET /api/v1/workflows/status | ecoroute/read | none; no parameters | inline object; pointer paths/~1api~1v1~1workflows~1status/get/responses | configuration-dependent |
