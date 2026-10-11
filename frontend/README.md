# EcoRoute city dashboard

## Health Connect in Wearable

Existing watch and wearable controls are preserved. The new Health Connect panel reads only
through the backend; no phone IP/token is included in the browser bundle. For local use before
Cognito setup, generate the private eight-hour pairing key using scripts/health_connect.py,
restart backend, enter the key and explicitly allow the session. Browser time zone/date select
daily totals. Manual refresh/default-off60/120second polling; disconnect/section change clears
records and credentials from memory. Other APIs still require their existing authentication.
[Setup, schema and actual phone verification](../docs/HEALTH_CONNECT.md). This displays records,
not a continuous sensor stream; there is no fabricated fallback or inferred health score.

React + TypeScript + Vite + Three.js. User-authorized frontend addition after Phase7; no cloud
deployment is implied. The supplied Axle image/video inspired the layout, not its branding or
statistics. The interactive city is an original illustrative scene, not a geographic Delhi model.

## Run

Node22.12+:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173 . Historical preview needs no credentials and uses the actual saved
OSRM/Open-Meteo response in ../examples/delhi-recorded-response.json. Route IDs/times are historical;
no live exposure improvement, AQI, emissions reduction or physical watch data is invented.
3D orbit/zoom/reset and pause are functional; route view projects actual returned GeoJSON.
Keyboard users can select routes with the route buttons. Reduced motion starts with trams paused.
WebGL failure leaves the route planner and route geometry available.

## Connect the existing backend

Start from repository root in a separate terminal:

```powershell
$env:CORS_ORIGINS='["http://127.0.0.1:5173"]'
.\.venv\Scripts\python.exe -m uvicorn ecoroute.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Copy frontend/.env.example to frontend/.env.local and set public configuration only:

- VITE_API_BASE_URL: localhost or verified HTTPS backend URL, without /api/v1.
- VITE_COGNITO_DOMAIN: full HTTPS Cognito domain URL.
- VITE_COGNITO_CLIENT_ID: public app client ID, no client secret.
- VITE_COGNITO_REDIRECT_URI: exact registered callback including path/trailing slash.

All VITE_ variables are public browser bundle configuration. Never put AWS keys, provider keys,
tokens or private certificates here. PKCE state/verifier is briefly stored in sessionStorage;
access tokens stay only in memory and are cleared on sign-out/expiry. Reload requires sign-in.
The app does not persist private API results, use cookies, invoke SMS or bypass JWT checks.
Sign-out clears this app's token; Cognito's hosted SSO session may still exist.

Settings → Live services clears historical routes. Sign in, enter origin/destination and departure,
choose mode/objective, explicitly consent to route storage, then Compare routes. Live error states
never substitute saved data. Air-quality quality reports, owned wearable latest reading, explanation,
ML status and alert list call their existing protected endpoints on explicit user action.
There is no automatic provider polling, notification send, device enrollment or wearable simulator UI.
Cycling stays disabled until the backend supports it. Historical mode is driving-only.

For AWS, configure CDK context arrays in cdk.json: frontend_origins=[exact HTTPS origin] and
callback_urls=[exact HTTPS callback]. Both Lambda CORS and API Gateway preflight use exact approved
origins; wildcard, paths and non-HTTPS origins fail synthesis. Existing JWT protections remain.
No hosting resources were added. Build output can later be served by an approved static host;
hosting/deployment requires a separate reviewed action and cost discussion.

## Verify

```powershell
npm run build
npm test
npm run test:e2e
npm audit --omit=dev
```

Local browser tests use installed Edge. CI uses Chromium installed by Playwright. API/Cognito live
login remains configuration-dependent; browser tests explicitly exercise offline/auth-failure paths.
Backend contract is ../docs/FRONTEND_INTEGRATION.md. No tests imply live AWS deployment.

### Scene modes

Cinematic is the default reference-matched AI-generated artwork, with restrained pan/zoom.
It is not a geographic map or freely orbitable 3D scene. Use **3D orbit** for procedural real-time
geometry and **Route view** for the actual provider's road geometry. Open the planner with
Explore your routes, the orange navigation pin, Journeys, or the menu toggle. Artwork provenance
and generation prompt are in public/assets/ASSET_PROVENANCE.md. No image API key is needed at runtime.

### Unified animated city (supersedes separate modes)
The old procedural 3D UI and Three.js were removed at the user's request. City view now
composites architectural artwork, moving transparent train sprites and reflections into a single
2.5D scene. There is no orbit mode. Route view and all existing backend contracts are preserved.

## Google routing integration (2026-10-10)
See docs/GOOGLE_MAPS_SETUP.md (repository root) for separate server/browser keys, APIs, Cognito,
restricted secret IAM and verification. Google Routes/Places feed the existing exposure engine;
Journeys displays Maps JavaScript tiles and route overlays. Live provider verification is recorded below.
Google comparisons are request-only; saved route-ID workflows are unavailable for those results.
No AWS resources were deployed. Google charges are separate from AWS credits.

Wearable now includes the original EcoRoute Pulse 3D preview. Full straps and seven demo screens
are modeled/rendered locally; tap/swipe or use accessible controls. The expanded sidebar retains
existing connection controls. See ../docs/CUSTOM_WATCH.md. No keys are needed for the preview.

## Public map and travel modes — 2026-10-10

Google map tiles now verified locally without sign-in. With a browser key, the default view is the actual satellite map with tilt/camera controls, coordinate selection and provider route overlays. Guest comparisons use /routes/preview; private APIs retain Cognito. Drive/Walk require the backend Google server key; Cycle needs a separate ORS key. See ../docs/GOOGLE_MAPS_SETUP.md. Google photorealistic 3D and bicycle coverage are not listed for India; no building/sensor precision is claimed. Browser tests isolate fake keys and mocked APIs on ports 5174/5175; npm run dev remains on 5173.

## Live routing verified — 2026-10-11

Google Drive/Walk and ORS Cycle returned real routes locally with the configured server keys.
The guest browser comparison displayed three Google alternatives and two geographic pins.
Live fields start empty: enter specific addresses, Choose start/destination on the map, or
click My location and grant browser permission. There is no fixed Delhi location in Google routing;
the existing historical preview remains explicitly Delhi-based. Missing air coverage stays unavailable.
The focused location field uses a warm highlight with no red rectangle. Keys stay in ignored files:
server keys in root .env; browser key/public API base in frontend/.env.local. The local API base must
be exactly http://127.0.0.1:8000 (without an extra letter or unmatched quote).

Opt-in billed browser/provider verification using public landmarks:
```
node scripts/verify-routing.mjs --origin "India Gate, New Delhi, India" --destination "Connaught Place, New Delhi, India" --mode driving
```
The output excludes secrets and full geometry. Ignored work/ holds the screenshot and filtered result.
Private wearable/health endpoints remain Cognito-protected. No AWS deployment performed.

## Wearable sensor connection — 2026-10-11

Wearable includes an explicit Bluetooth-consent checkbox and Connect Bluetooth/Disconnect & clear
controls. Only standard Heart Rate and optional Battery are read; no automatic connection/upload.
Missing metrics remain unavailable, stale values are hidden and the chart is received BPM, not ECG.
Protected backend latest records also map into the display as manual snapshots. Physical inspection
found the user's Noise session using vendor 0x0AF0/0x0AF7, with no standard Heart Rate service;
its health data is not decoded or verified. See ../docs/LIVE_WATCH_SETUP.md for prerequisites,
phone diagnostics, privacy and the remaining verified vendor-bridge requirement.
