# Google Maps + Routes setup

Implemented 2026-10-10. No Google calls or deployment have been performed with real keys.

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
```
If previously using OSRM, remove OSRM_BASE_URL. Keep ENABLE_AWS_LOCATION=false unless separately
using AWS Location. In `frontend/.env.local`, set:
```
VITE_GOOGLE_MAPS_API_KEY=your_browser_key
VITE_API_BASE_URL=http://127.0.0.1:8000
```
Also configure existing Cognito values in both frontend and backend per CREDENTIALS_CHECKLIST.md.
Adding map keys does not bypass route authorization. Map display works independently of sign-in;
protected comparisons require Cognito, Live services and consent to location processing.
Stop any old preview server and run `npm run dev` from repository root. Vite configuration changes
require a restart; production builds require rebuilding. Open Journeys: a Google map is centered on
Delhi, and returned route alternatives are drawn as selectable orange/grey polylines.

## Verify without exposing keys
- Open Journeys and confirm Google map tiles/attribution appear. No browser key means setup guidance
  in live mode; historical mode retains its offline geometry view.
- Connection settings > Live services > Sign in with Cognito. Choose Drive, Walk or Cycle, provide
  unambiguous Delhi locations and a departure within 48 hours, consent, then Compare routes.
- Check source details for google_routes and actual returned warnings. Delhi boundary remains enforced.
- Cycle coverage is not guaranteed. No route returns an explicit error, never a driving substitute.
- Pollution requires existing curated observations/forecasts covering the requested date. Missing
  pollution stays unavailable even when routing works. A map key does not provide air quality.
- Browser Network should call only the protected FastAPI comparison endpoint for route requests;
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
limits LOCATION_DAILY_LIMIT=100 and LOCATION_HOURLY_LIMIT=30 bound server provider requests;
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
