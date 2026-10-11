# Google Maps + Routes setup

## Hackathon routing allowance

AWS backend now allows100provider calls/hour with the same100/day cap, shared by all users.
A comparison with two place names usually uses2Places searches+1Routes call; selecting map
coordinates avoids those place searches. This is not100comparisons/day. Daily/hourly slots are
reserved atomically; rejected hourly attempts no longer consume daily slots. Existing counted
usage is preserved, not reset. UTC boundaries reset windows: daily00:00UTC/05:30IST. The response
identifies the exhausted window and Retry-After. Local defaults remain100/day and30/hour.
Google Cloud provider quotas/free allowances and billable browser Maps loads are separate; these
AWS application counters are not dollar caps and AWS credits do not cover Google charges.


Updated 2026-10-11. Real Google map tiles, Places geocoding, driving/walking routes and
openrouteservice cycling verified locally. Browser guest comparison returned three Google routes
and two map pins. No AWS action or deployment performed.

## Two different keys
1. Google Cloud Console: create/select a project, attach billing, then APIs & Services > Library.
   Enable **Routes API**, **Places API (New)** and **Maps JavaScript API**.
2. APIs & Services > Credentials > Create credentials > API key. Create a SERVER key restricted
   to Routes API and Places API (New). Restrict application usage to your server egress IP when
   available. Never put this key in a VITE variable, source control or chat.
3. Create a separate BROWSER key restricted to Maps JavaScript API and HTTP referrers:
   `http://127.0.0.1:5173/*`, `http://localhost:5173/*` and your exact deployed HTTPS origin.
   This browser key is public by design; API/referrer restrictions are mandatory. Do not reuse it
   for server calls. Creation requires suitable Google project API/service-usage and key-management
   permissions; billing attachment requires billing-account permission. No AWS admin access needed.

## Local files (ignored)
In the root `.env`, set:
```
ROUTING_PROVIDER=google
GOOGLE_ROUTES_API_KEY=your_server_key
ENABLE_GUEST_ROUTES=true
```
If previously using OSRM, remove OSRM_BASE_URL. Keep ENABLE_AWS_LOCATION=false unless separately
using AWS Location. In `frontend/.env.local`, set:
```
VITE_GOOGLE_MAPS_API_KEY=your_browser_key
VITE_API_BASE_URL=http://127.0.0.1:8000
```
Also configure existing Cognito values in both frontend and backend per CREDENTIALS_CHECKLIST.md.
Map display and the separate request-only guest comparison do not require Cognito. Existing
private endpoints still require Cognito. Guests consent to processing, never storage. Signed-in
comparisons use the protected endpoint. ENABLE_GUEST_ROUTES is disabled by default in infrastructure.
Stop any old preview server and run `npm run dev` from repository root. Vite configuration changes
require a restart; production builds require rebuilding. Open Journeys: start/destination are empty
and the map opens at a neutral world overview. Enter specific addresses, choose map points or click
My location (browser permission required). Returned alternatives are selectable orange/grey polylines.
Live routing has no fixed Delhi location. Historical mode still labels its saved Delhi comparison.

## Verify without exposing keys
- Open Journeys and confirm Google map tiles/attribution appear. No browser key means setup guidance
  in live mode; historical mode retains its offline geometry view.
- Choose Live services. Guests can compare without signing in when the backend is configured. Provide
  unambiguous locations and a departure within 48 hours, consent, then Compare routes.
- Check source details for google_routes and actual returned warnings. Google coordinates/geocoding
  accept valid worldwide locations where providers offer coverage. Comparisons remain bounded to
  100 km and six hours; legacy AWS/OSRM profiles retain their existing Delhi boundary.
- Drive and Walk use Google. Cycle uses ORS as described below; no car-route substitution exists.
- Pollution requires existing curated observations/forecasts covering the requested date. Missing
  pollution stays unavailable even when routing works. A map key does not provide air quality.
- Browser Network should call only FastAPI /routes/preview (guest) or /routes/compare (signed in);
  server key must never appear in frontend bundles or browser requests.

## AWS secret reference (optional after deployment approval)
Secrets Manager > Store a new secret > Other type > Plaintext: store ONLY the server key, choose
an appropriate encryption key, name it, and copy its complete ARN. Configure CDK context
`google_routes_secret_arn` with that ARN; do not put the value in CDK context. The API role receives
only secretsmanager:GetSecretValue on this ARN; customer-managed KMS keys also need scoped Decrypt
and a matching key policy. Runtime selects Google and reads this secret on demand. Local secret
lookup requires an authorized temporary AWS CLI profile; no AWS calls are needed for local .env keys.
Secrets Manager storage/retrieval and Google calls can incur charges. No NAT Gateway is introduced.

## Storage and display limitations
Google route content is returned only for the active comparison: no S3/DynamoDB geometry storage,
report export or route-result cache. Consequently Google route IDs are not retrievable by GET,
wearable stored-journey correlation or backend route-ID explanation APIs. The frontend uses its
existing deterministic explanation of currently displayed metrics for Google comparisons.
Departure-time comparison still computes fresh requests. Exposure scoring uses the existing engine.
Required Google attribution stays visible in the map; route cards identify Google Maps. Other data
sources remain distinct. Publish appropriate Terms and Privacy pages before public deployment.

## Cost controls
Google billing is separate from AWS credits. Each text comparison can use two Places searches and
one Routes request; coordinates skip Places. Map loads have their own billing. Existing application
Local defaults LOCATION_DAILY_LIMIT=100 and LOCATION_HOURLY_LIMIT=30 bound server provider requests; AWS uses100daily/100hourly for bounded hackathon usage;
they do not cap browser map loads. Set Google API quotas and billing alerts before enabling keys.
Alerts do not hard-cap spend. Avoid automatic polling. Current SKU/rates depend on account eligibility,
region and requested features: verify in Google Cloud Billing before live testing.

## Official references checked
- https://developers.google.com/maps/documentation/routes/compute_route_directions
- https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes
- https://developers.google.com/maps/documentation/places/web-service/text-search
- https://developers.google.com/maps/documentation/javascript/load-maps-js-api
- https://developers.google.com/maps/documentation/routes/policies

## Offline verification
```
.venv/Scripts/python.exe -m pytest tests/test_google_routes.py tests/test_routing.py -q
npm --prefix frontend run build
cd frontend
node node_modules/@playwright/test/cli.js test --config playwright.maps.config.ts
```
Map tests intercept Google's script using a mock. They verify configuration, coordinate order,
polylines and failure UI, not real Google coverage or billing entitlement.

## User-selected map and public access
With a browser key, the opening screen uses a genuine satellite/street map with vector
rendering, camera tilt, zoom, north, fit, satellite toggle and map coordinate picking. A/B markers
use Google-projected coordinates from selected points or returned route geometry. Default text
addresses are not invented geocoded pins. No pollution sensors/buildings are fabricated.
India is not listed for photorealistic 3D or bicycle directions in the current Google coverage
matrix: https://developers.google.com/maps/coverage. This is a tilted geographic map; detailed
3D building coverage is not promised. Device WebGL support can also restrict perspective.

POST /api/v1/routes/preview uses PreviewRequest and returns the existing RouteComparison envelope.
No login/token is necessary. Guest request consent_to_store must be false. The endpoint cannot
read another user's records or persist route geometry. Max alternatives=2; minimum segment=250m.
It shares atomic LOCATION_DAILY_LIMIT and LOCATION_HOURLY_LIMIT with protected provider calls;
three calls may be needed for two place searches plus routing. Anyone can exhaust this shared
allowance when publicly enabled. API Gateway throttles 2 requests/s, burst 5. Before production,
review abuse protection, Google quotas, billing alerts and privacy/terms. Do not expose the local
server to the internet. No automatic route polling occurs.
AWS requires explicit CDK enable_guest_routes=true and google_routes_secret_arn. The one public
POST route is added only then; all private routes retain JWT authorization. Not deployed here.

## Genuine cycling (optional provider)
Google does not list Indian bicycle coverage. Register at https://account.heigit.org/ using
openrouteservice's official account link. Verify your email, create an API key in the account
API-key/dashboard area, and review the current quota/plan and attribution requirements. Store
privately in the root .env (never a VITE variable):
```
CYCLING_PROVIDER=openrouteservice
OPENROUTESERVICE_API_KEY=your_private_provider_key
```
Restart the backend. No AWS IAM permission is needed for a local provider key. API keys are
sensitive; account sign-up/verification is required. Directions use Authorization headers and
https://api.heigit.org/openrouteservice/v2/directions/cycling-regular/geojson. Old
api.openrouteservice.org is being retired; official migration:
https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912.
At most three alternatives are requested; actual routes and bicycle accessibility depend on
OSM coverage. Durations are seconds, distances metres, coordinates longitude then latitude.
See https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/ and
https://openrouteservice.org/restrictions/. Plan quotas can change; AWS credits do not pay for ORS.
For verification choose two map points (skips Google Places), Cycle and Compare; verify provider
openrouteservice and profile cycling-regular in Sources. One real Delhi cycling request succeeded
on 2026-10-11. This does not guarantee coverage for every location. Missing key/configuration stops
integration with a specific error.
Optional AWS storage: Secrets Manager > Other type > Plaintext, store only the key. Copy ARN,
set cycling_secret_arn CDK context, and approve deployment separately. The API receives scoped
secretsmanager:GetSecretValue on this ARN and CYCLING_PROVIDER=openrouteservice. No secret is
created automatically. Customer-managed KMS also needs scoped Decrypt. Revocation: disable/delete
the provider key in the provider dashboard, remove config/reference, restart the backend.
Secret storage/access and non-free plans may charge; check current provider quotas before use.

## Verification performed
One local Maps browser verification confirmed tiles_loaded=true and authorization_failure=false,
without sign-in. Screenshot is local work/google-map-live.png; no URLs or keys were logged.
On 2026-10-11, local guest HTTP requests returned real driving (2,702 m / 333 s), walking
(2,824 m / 2,428 s) and cycling (3,558.9 m / 806.9 s) routes between public Delhi landmarks.
Each had existing curated forecast coverage; no new pollution measurements were collected.
Google Places resolved Gateway of India in Mumbai, demonstrating geocoding outside Delhi.
A separate browser comparison using address text returned HTTP 200, three Google alternatives,
two visible pins, available exposure and input outline=none without sign-in. Its desktop screenshot
was inspected locally. Route lengths can differ because coordinate endpoints and text places snap
differently. No route geometry or keys are committed with verification reports.

Automated SDK/provider tests use mocks and recorded road geometry for contract mechanics only.
Separate scripts/verify-map.mjs under frontend loads the real map once when explicitly run.
The opt-in live routing verifier also incurs provider/map usage:
```
cd frontend
node scripts/verify-routing.mjs --origin "India Gate, New Delhi, India" --destination "Connaught Place, New Delhi, India" --mode driving
```
Use public landmarks, not private home/work addresses, in verification commands. No provider URLs,
keys or raw error bodies are logged. Filtered results and screenshot stay under ignored work/.
The configured local frontend API URL was corrected to http://127.0.0.1:8000 (a typo and mismatched
quote prevented requests). Server-only keys were moved from frontend/.env.local to root .env.


## 2D and 3D controls

Choose 2D for overhead streets or satellite. Choose 3D for a vector street map:
the camera moves to building-scale zoom and tilts; use Rotate to change heading.
Satellite remains a separate imagery choice. Building detail depends on location coverage.
The app waits for Google renderer initialization instead of declaring an initializing map unsupported.
An optional Map ID is not required when VECTOR is explicitly requested.
If Google still returns raster, enable graphics acceleration in Chrome/Edge Settings > System,
restart the browser and retry. See Google's [rendering guide](https://developers.google.com/maps/documentation/javascript/map-rendering-type)
and [browser support](https://developers.google.com/maps/documentation/javascript/webgl/support).
No code can guarantee GPU-backed rendering on every device.
