# Phase 3 routing runbook

Implemented locally on 2026-10-09 IST. No AWS resource was created or deployed.
`dev-admin` is the user-confirmed CLI profile for IAM user `devesh_eco`, region `ap-south-1`.
STS succeeds. Real Routes V2 and Places V2 calls both returned AccessDeniedException.
This is an authorization blocker, not evidence that Mumbai lacks the service.

## Credentials and one bounded AWS demonstration

AWS_PROFILE, AWS_REGION and EXPECTED_AWS_ACCOUNT_ID are mandatory non-secret configuration
for local AWS routing. The existing ignored .env selects dev-admin and the verified account;
do not replace it with .env.example. CLI-managed credentials stay outside Git in the user
profile. Never paste credentials or login tokens in chat. Renew through your existing approved
login/temporary credential mechanism. No root profile is used by the routing service.

An authorized IAM operator can open **IAM → Users → devesh_eco → Permissions → Add permissions
→ Create inline policy → JSON**, paste [location-read.json](iam/location-read.json), review
and name it EcoRouteLocationMumbai. Attaching this requires `iam:PutUserPolicy` on the exact
user; it is an operator task, not an application permission. For a role, attach the equivalent
role policy using `iam:PutRolePolicy`. Boundaries, SCPs and session policies can still deny access.
Do not attach AdministratorAccess. This project has not changed any IAM policy.

The policy permits only `geo-routes:CalculateRoutes` and `geo-places:Geocode`, scoped to their
Mumbai provider/default ARNs (these ARNs deliberately have an empty account component).
Server-side boto3 uses SigV4; no Location API key or legacy route calculator/place index is needed.
Policy attachment itself has no service fee; data requests can incur Location charges.

```powershell
aws sts get-caller-identity --profile dev-admin --region ap-south-1
.\.venv\Scripts\python.exe scripts/diagnose.py --aws --profile dev-admin --region ap-south-1
# After the Location permissions are actually granted, one billed route request:
.\.venv\Scripts\python.exe scripts/demo_routes.py --provider aws
# Optional single geocode authorization check (may incur a Storage-tier charge):
aws geo-places geocode --query-text 'India Gate Delhi' --max-results 1 --intended-use Storage --profile dev-admin --region ap-south-1 --query 'length(ResultItems)'
```

The demo explicitly enables AWS only for that command; regular application integration remains
disabled until ENABLE_AWS_LOCATION=true is set locally. Protected HTTP calls also require
COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID and a valid short-lived access token; those are still
missing. See CREDENTIALS_CHECKLIST.md for OAuth PKCE setup. Tokens remain in local environment.
No authenticated live HTTP endpoint or successful AWS route is claimed.

## Local execution without pretending AWS succeeded

```powershell
.\.venv\Scripts\python.exe scripts/demo_routes.py --provider recorded
```

This uses the labelled public-landmark recording in tests/fixtures/delhi_osrm_routes.json,
not an invented path, and reads actual curated pollution from work/environment. Without
eligible pollution, full exposure is null. It never creates pollution to make the demo succeed.
Run scripts/ingest_air.py --source open_meteo when fresh model data is needed and network is available.
Synthetic pollutant values in pytest exist only for arithmetic/edge-case tests.

Recorded road evidence: one HTTP 200 from OSRM at 2026-10-08T20:23:40.2707Z, India Gate
[77.2295,28.6129] to Connaught Place [77.2167,28.6315]. Two routes, 117 and 96 vertices.
The fixture retains the exact response, request URL, collection timestamp and OSM attribution.
Current local demo output lives in ignored work/phase3-demo.json and is reproducible while
the saved environmental forecast remains eligible. It is not an AWS response or live traffic evidence.

| Recorded route | Distance m | Static duration s | Segments | Estimated PM2.5 index ug*h/m3 |
|---|---:|---:|---:|---:|
| Fastest baseline | 2822.5 | 206.7 | 12 | 5.0009916667 |
| Alternative | 2712.6 | 231.6 | 11 | 5.6034333333 |

These results used the real Open-Meteo retrieval from 2026-10-08T18:11:31.163657Z, with
PM2.5 87.1 ug/m3 at the matched forecast time. The longer-duration alternative is +12.0464%
relative to the fastest baseline. This is **not an exposure reduction demonstration**: both
routes share the same coarse model cell, with no observed street-level difference established.
Forecast issue time is not supplied; collection time is not represented as model issue time.

## Algorithm and scientific bounds

Amazon Routes V2 receives longitude first, Car or Pedestrian, an RFC3339 departure, up to five
alternatives and FlexiblePolyline geometry. The provider may return fewer alternatives. Cycling
has no Bicycle mode in the verified API and returns 422 until an appropriate provider is added;
Scooter is not substituted. Places V2 Geocode uses India filtering, Delhi bias and IntendedUse=Storage.
No result, broad administrative results, out-of-area points or materially ambiguous matches fail explicitly.

The engine validates connected provider legs, endpoint snapping within 250 m, positive durations,
geometry/reported-distance agreement and finite WGS84 coordinates. It decodes flexible polylines
to GeoJSON [longitude,latitude]. Segmentation preserves every original vertex and inserts points
only along existing provider edges; it never generates a direct navigable route between endpoints.
Haversine distance and local linear interpolation are bounded to the Delhi demo. Uniform speed
within each leg estimates segment timing; this is not turn-by-turn traffic reconstruction.
Limits: 100 km, six hours, 10,000 vertices, 600 segments, 100–1000 m target segment length,
six candidates, 4 MiB comparison response. Large work should become an asynchronous job.

Segment midpoints join the existing curated index. Station observations must be within 1 km,
not newer than the segment, and at most one hour old; they are never extrapolated into future
trips. Model points use a 0.4-degree cell footprint, at most 30 minutes from a returned hourly
valid time, and a retrieval at most 24 hours old. Future trips require forecast-kind records.
These are conservative demo eligibility rules, not a validated spatial interpolation model.
Flagged/null/wrong-unit records are excluded. No filling gaps with zero. PM2.5, PM10, NO2 and O3
each retain source, time, location/grid, freshness metadata, quality, resolution and provenance.
Model resolution remains roughly 45 km; finer route segmentation does not improve it.
Uncertainty categories are qualitative, not calibrated probabilities or confidence intervals.

E = sum(PM2.5 ug/m3 × duration seconds / 3600), in **ug*h/m3**, a concentration-time index.
Partial known contribution and coverage are reported separately; incomplete or truncated data
makes full E unavailable. No AQI integration, inhaled dose, medical advice or measured ML accuracy.
Optional ventilation-based inhalation is deferred until a sourced activity model is selected.

Fastest means the fastest returned valid candidate. Time detour uses that baseline, not distance.
Lowest exposure selects only fully covered, detour-eligible candidates; it cannot establish a
minimum over alternatives with unavailable pollution. Balanced scoring is unavailable if any
eligible candidate lacks full coverage. Otherwise min-max normalization across eligible candidates
gives `(1-weight)*normalized_time + weight*normalized_exposure`; equal ranges contribute zero.
Missing objectives fall back to fastest with an explicit reason. Relative change is
100 × (route E − baseline E) / baseline E; null when the baseline is unavailable or zero.
Only provider-generated alternatives are ranked; no global pollution-optimal network claim is made.

Departure analysis accepts at most three unique UTC-normalized times over the next 48 hours.
It obtains routes for each departure, reuses resolved coordinates, and enforces a bounded deadline.
The fallback has static timings, which are labelled. A durable Step Functions route study is
deferred because this small synchronous workload does not justify another workflow service.

## Storage, privacy and operations

HTTP authentication and scopes are checked before provider access. Owner-scoped DynamoDB
route_metadata entries point to private S3 JSON; route_cache entries share the table with distinct
sort-key prefixes. Full geometry never risks DynamoDB's item-size limit. Consent is mandatory.
Route reuse is five minutes and owner-scoped. Exact requests include departure time and scoring
settings in the cache key; the 5-minute snapshot can lag newly ingested data and exposes scored_at.

```text
routes/<owner-hash>/<route-id>.json             # candidate + scored route, 7-day lifecycle
routes/<owner-hash>/cache-<random-id>.json       # 5-minute logical reuse, 7-day lifecycle
reports/routes/date=YYYY-MM-DD/<random>.json    # duration/distance/exposure only, 7-day lifecycle
```

These are implemented layouts, currently local files only; no real S3 objects were uploaded.
Reports omit subject, precise coordinates, geometry and route IDs. Logical route expiry is seven
days and enforced on reads. S3 lifecycle and DynamoDB physical TTL deletion are asynchronous;
monitor cleanup before production and honor provider retention terms. Local work files do not
auto-delete; remove expired local route/report objects during demo cleanup. Never publish AWS
route data into the ODbL fixture dataset. No map/frontend is included.

Core Lambda optionally gains only two geo actions with `-c enable_location=true` at synthesis;
the default template keeps Location disabled. Data owns private encrypted/TLS S3 and TTL tables.
API role gains only route-prefix GetObject/PutObject, report-prefix PutObject and environmental
budget UpdateItem. Existing CloudWatch API/Lambda error and latency alarms cover these requests;
structured routes_scored logs contain counts/provider/latency and omit personal paths/tokens.
API timeout is 28 seconds, below HTTP API's 30-second ceiling. No NAT, VPC, ECS or idle endpoint.

Request budgets are application safeguards: default 100 Location calls/day and 30/hour shared
across users, including geocodes and failed attempts. An uncached coordinate comparison normally
uses one CalculateRoutes request; two text endpoints add up to two geocodes. Three departures
with text can require five requests. These limits do not hard-cap account spending or affect
calls made outside this application. Concurrent local threads share a protected SQLite adapter;
use one local process. AWS uses conditional DynamoDB budget updates.

## Pricing, sources and fallback terms

CalculateRoutes bills per API request and feature tier; Car/Pedestrian without toll features
uses the Core feature set. Stored geocoding uses the Storage tier. Exact Mumbai unit prices,
taxes and credit eligibility must be checked before deployment; no billed cost has been measured.
Add `route_calls * regional_route_rate + geocodes * regional_storage_geocode_rate` to the
existing demo cost proposal. Paid deployment remains gated by a concrete estimate and approval.
Budgets alert asynchronously and do not stop spending. Nothing was provisioned in this phase.

- [Routes V2 boto3 schema](https://docs.aws.amazon.com/boto3/latest/reference/services/geo-routes/client/calculate_routes.html)
- [Places V2 Geocode schema](https://docs.aws.amazon.com/boto3/latest/reference/services/geo-places/client/geocode.html)
- [Regional endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/location.html)
- [Routes IAM](https://docs.aws.amazon.com/service-authorization/latest/reference/list_geo-routes.html) and [Places IAM](https://docs.aws.amazon.com/service-authorization/latest/reference/list_geo-places.html)
- [Routes billing categories](https://docs.aws.amazon.com/location/latest/developerguide/routes-pricing.html), [pricing](https://aws.amazon.com/location/pricing/) and [Places intended use](https://docs.aws.amazon.com/location/latest/developerguide/places-intended-use.html)
- [Amazon Location data attribution](https://docs.aws.amazon.com/location/latest/developerguide/data-attribution.html): preserve the response attribution link conspicuously in future clients.
- [AWS Service Terms section 82](https://aws.amazon.com/service-terms/): route retention, data-provider and mapping restrictions apply; do not combine AWS data into an ODbL redistribution database.
- [Flexible polyline format/reference](https://github.com/heremaps/flexible-polyline): independently implemented decoder; reference-vector test.
- [OSRM API](https://project-osrm.org/docs/v5.24.0/api/), [demo policy](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server), [OpenStreetMap attribution/licensing](https://www.openstreetmap.org/copyright).

OSRM is an explicit pluggable fallback, not automatic on AWS failure. Set ROUTING_PROVIDER=osrm
and OSRM_BASE_URL to an operator-approved HTTPS origin. It supports driving and coordinates
only in this adapter; it never claims traffic-aware departure durations. The public demo was
used once for public-landmark evidence, within its one-request/second policy. Do not configure
that shared demo as the production service; choose a hosted/self-managed service with documented
capacity and licensing. AWS and OSRM provenance remain distinct.
