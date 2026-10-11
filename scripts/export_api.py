"""Export runtime-identical OpenAPI, complete endpoint index and safe Postman placeholders."""
import json
from pathlib import Path

from ecoroute.config import Settings
from ecoroute.main import create_app

GUIDE = """# Frontend integration — EcoRoute AI backend

The React/Three.js frontend lives in frontend/; local UI: http://127.0.0.1:5173.
Backend local base URL: http://127.0.0.1:8000. See frontend/README.md for PKCE and live-mode setup.
AWS base URL: <VERIFIED_API_GATEWAY_URL> (not deployed).
Authoritative request/response schemas: [openapi.json](openapi.json), exported from the SAME
runtime /openapi.json. Provider metadata and variable model metrics intentionally allow extra
properties; stable fields have explicit types. Error schemas describe normalized backend
errors; an upstream API Gateway rejection/throttle can have its own AWS error envelope.

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

GeoJSON geometry is {\"type\":\"LineString\",\"coordinates\":[[longitude,latitude],...]} in WGS84.
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

Backend errors: {\"error\":{\"code\":\"validation_error\",\"request_id\":\"opaque_id\"}}.
401 missing/invalid bearer;403 scope/consent;404 absent/other owner's record;409 idempotency/state;
413 body over256KiB;422 validation/unsupported route;429 request budget;500 unexpected failure;
503 dependency/auth/provider/model unavailable. /ready503 uses {\"status\":\"not_ready\"}.
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

Configure CORS_ORIGINS as a JSON array of exact origins, e.g. [\"http://localhost:3000\"] locally;
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
"""


def sample(schema, components, name=""):
    if "$ref" in schema:
        return sample(components[schema["$ref"].split("/")[-1]], components, name)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        return sample(next(s for s in schema["anyOf"] if s.get("type") != "null"), components, name)
    kind = schema.get("type")
    if kind == "object":
        value = {k: sample(v, components, k) for k, v in schema.get("properties", {}).items() if k in schema.get("required", [])}
        if name == "destination":
            value = {"longitude": 77.2167, "latitude": 28.6315}
        return value
    if kind == "array":
        return [sample(schema.get("items", {}), components, name.removesuffix("s"))]
    if kind == "boolean":
        return True
    if kind in {"number", "integer"}:
        if name == "longitude":
            return 77.2295
        if name == "latitude":
            return 28.6129
        return schema.get("minimum", 1)
    if name in {"departure_at", "departures"}:
        return "{{departure_at}}"
    if schema.get("format") == "date-time":
        return "{{alert_end_at}}" if name == "end_at" else "{{history_start}}" if name == "start" else "{{observed_at}}"
    if schema.get("format") == "time":
        return "00:00:00" if "start" in name else "23:59:00"
    if name == "location_id" or name == "forecast_location_id":
        return "cams_global:28.8000:77.2000"
    if name == "user_id":
        return "{{user_sub}}"
    if name in {"route_id", "device_id", "journey_id", "trip_id", "alert_id", "school_id", "event_id"}:
        return "{{" + name + "}}"
    if name.endswith("_id") or "pattern" in schema:
        return "a" * 32
    return "DEVELOPMENT_PLACEHOLDER"


def export(root):
    app = create_app(Settings(_env_file=None, local_db_path=":memory:"))
    schema = app.openapi()
    app.state.store.db.close()
    docs, examples = root / "docs", root / "examples"
    docs.mkdir(exist_ok=True)
    examples.mkdir(exist_ok=True)
    (docs / "openapi.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    guide, items = GUIDE, []
    components = schema["components"]["schemas"]
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "delete"}:
                continue
            body_schema = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            parameters = operation.get("parameters", [])
            body_name = body_schema.get("$ref", "inline").split("/")[-1] if body_schema else "none"
            successful = next((v for k, v in operation["responses"].items() if k.startswith("2")), None)
            response = successful["content"]["application/json"]["schema"] if successful else {}
            response_name = response.get("$ref", "inline object").split("/")[-1] if successful else "ApiError"
            access = operation.get('x-ecoroute-scope') or 'public (configuration-dependent)'
            if operation.get("x-ecoroute-local-pairing"):
                access += " or scoped local pairing bearer"
            guide += f"| {method.upper()} {path} | {access} | {body_name}; {', '.join(p['name'] for p in parameters) or 'no parameters'} | {response_name}; pointer paths/{path.replace('/', '~1')}/{method}/responses | {'legacy unavailable/retired' if operation.get('deprecated') else 'configuration-dependent'} |\n"
            url = "{{base_url}}" + path
            for parameter in parameters:
                if parameter["in"] == "path":
                    url = url.replace("{" + parameter["name"] + "}", "{{" + parameter["name"] + "}}")
            query = [{"key": p["name"], "value": str(sample(p["schema"], components, p["name"])), "disabled": not p.get("required", False)} for p in parameters if p["in"] == "query"]
            headers = [{"key": p["name"], "value": "development-request-001"} for p in parameters if p["in"] == "header"]
            enabled_query = [q for q in query if not q["disabled"]]
            raw_url = url + ("?" + "&".join(q["key"] + "=" + q["value"] for q in enabled_query) if enabled_query else "")
            request = {"method": method.upper(), "url": {"raw": raw_url, "host": ["{{base_url}}"], "path": url.removeprefix("{{base_url}}").strip("/").split("/"), "query": query}, "header": headers}
            if not operation.get("security"):
                request["auth"] = {"type": "noauth"}
            if body_schema:
                body = sample(body_schema, components)
                if path == "/api/v1/devices/register":
                    body.update(manufacturer="Local demo", model="Synthetic fixture", bridge="demo")
                if path == "/api/v1/wearables/measurements":
                    body.update(heart_rate_bpm=80, provenance={"bridge": "demo", "sensor": "SYNTHETIC_TEST_ONLY", "source_record_id": "fixture", "synthetic": True})
                if path == "/api/v1/alerts/evaluate":
                    body.update(source="open_meteo", notify=False)
                if path == "/api/v1/schools/compare-routes":
                    body["position"] = body["route"]["destination"]
                request["header"].append({"key": "Content-Type", "value": "application/json"})
                request["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2)}
            items.append({"name": method.upper() + " " + path, "request": request,
                          "description": "User-triggered example; replace placeholders. See OpenAPI response schemas."})
    collection = {"info": {"name": "EcoRoute AI backend", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}]},
        "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": [
            "const now = new Date();", "pm.variables.set('departure_at', new Date(now.getTime()+600000).toISOString());",
            "pm.variables.set('observed_at', now.toISOString());", "pm.variables.set('history_start', new Date(now.getTime()-3600000).toISOString());",
            "pm.variables.set('event_id', pm.variables.replaceIn('{{$guid}}').replace(/-/g,''));",
            "pm.variables.set('alert_end_at', new Date(now.getTime()+86400000).toISOString().slice(0,13)+':00:00Z');"]}}], "item": items}
    environment = {"name": "EcoRoute private local configuration", "values": [{"key": k, "value": v, "enabled": True, "type": "secret" if k == "access_token" else "default"} for k, v in {
        "base_url": "http://127.0.0.1:8000", "access_token": "", "user_sub": "", "route_id": "", "trip_id": "", "journey_id": "", "device_id": "", "alert_id": "", "school_id": ""}.items()], "_postman_variable_scope": "environment"}
    (docs / "FRONTEND_INTEGRATION.md").write_text(guide, encoding="utf-8")
    for filename, value in (("ecoroute.postman_collection.json", collection), ("ecoroute.postman_environment.json", environment)):
        (examples / filename).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return schema, collection


if __name__ == "__main__":
    export(Path(__file__).resolve().parents[1])
    print("Exported runtime OpenAPI, every endpoint index and token-free Postman examples")
