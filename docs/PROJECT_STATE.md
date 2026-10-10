# EcoRoute AI project state — Phases 1–7

## Google Routes and Journeys map integration � 2026-10-10 IST

Added Google Routes v2/Places text-search backend adapter, mode mapping for DRIVE/WALK/BICYCLE,
field masks, typed road geometry validation, quotas, redacted failure codes, and request-only
results (no Google route cache or persistent geometry). Existing pollution scoring reused.
Journeys uses Maps JavaScript with selected route overlays; no browser server secret.
CDK accepts an optional exact Google secret ARN with scoped GetSecretValue. No deployment.
Google route-ID retrieval, persistent correlation and backend explanation are intentionally
unavailable; frontend deterministic explanation uses current comparison metrics.
Missing: GOOGLE_ROUTES_API_KEY (or GOOGLE_ROUTES_SECRET_ARN), VITE_GOOGLE_MAPS_API_KEY,
existing Cognito setup, enabled Google APIs/billing and date-matched pollution data.
See GOOGLE_MAPS_SETUP.md for exact configuration. No live key/provider verification claimed.

## Full-length rail alignment correction � 2026-10-10 IST

User reported continued rail drift. Replaced rigid sprite rotation with 40 clipped image slices
per train, each anchored by its visible wheel baseline to a smooth traced rail curve. Reflections
use the same contact line. This corrects front/rear drift on bends rather than aligning only the
train center. Equal period/spacing and 100% viewport layout are preserved.
Actual validation: build passed, 6 unit tests and 9 browser tests passed; inspected rendered
screenshot. Added all-slice/all-loop rail-contact arithmetic test. Artwork remains decorative
2.5D, not real train tracking. No AWS resources changed.

## Train alignment and 100% viewport fit � 2026-10-10 IST

Replaced independent train trajectories with a traced backdrop rail centerline, tangent alignment,
and a shared 68-second period with half-loop spacing. Sprite contact offset is accounted for.
Desktop shell uses 100dvh with flexible scene/rail heights and internally scrolling planner;
removed effective fixed scene minimum heights. Mobile retains natural document scrolling.
Verified production build, 5 unit tests and 9 browser tests. Viewport-fit assertions pass at
1366x768, 1280x720 and 1536x864 with planner open and closed at default 100% zoom. No AWS changes.

## Unified animated city � 2026-10-10 IST

User requested one detailed scene with moving trains and removal of the old 3D UI. Removed
City.tsx, the orbit switch and Three.js dependencies. The city is now an SVG-composited 2.5D
illustration: generated train-free architectural backdrop, transparent articulated tram sprites,
perspective-scaled movement along decorative track curves, reflected sprites and restrained parallax.
Pause freezes actual train positions; reduced-motion starts paused; background tabs stop advancing.
Real route geometry and backend APIs remain separate under Route view. No cloud deployment.
Production build and 8 browser tests passed, including actual transform movement/pause assertions.
Previous separate-mode descriptions below are historical and superseded by this entry.

## Reference-matched cinematic opening � 2026-10-10 IST

After the user rejected the procedural city's resemblance, generated a detailed architectural
city artwork with the built-in image generation tool using the supplied screenshot as reference.
Saved frontend/public/assets/ecoroute-cinematic-city.png; prompt/provenance in
frontend/public/assets/ASSET_PROVENANCE.md. Default Cinematic view has image pan/zoom and clickable
planner/air-quality hotspots, with the planner collapsed to preserve the reference composition.
3D orbit remains a separate interactive Three.js scene. Route view still uses actual saved GeoJSON.
The generated render is explicitly illustrative, not a live map, genuine Delhi architecture or
freely orbitable 3D. No fake rider counts or pollution savings were copied from the reference.

Verification: production build passed; all 8 Edge browser tests passed (9.8 s); desktop and mobile
screenshots inspected. Independent review caught mode wiring, labels and zoom boundaries; fixed
before passing tests. No new dependencies, authenticated AWS actions, resources or provider calls.
Existing live service setup requirements are unchanged. Local production preview runs at
http://127.0.0.1:5173; start the full backend/dev pair with npm run dev after stopping that preview.

## City visual refinement � 2026-10-10 IST

User requested stronger contrast, clouds and finer building/train details. Added a camera-centered
procedural cloud sky (fixes far-plane clipping), revised light/material balance, floor bands,
side glazing, rooftop equipment, street furniture, rounded tram bodies, doors, wheels, cab lamps
and pantographs. The city remains illustrative, not a measured digital twin or a video render.
Verified production build and desktop screenshot after the sky fix. Earlier concurrent build/browser
checks exhausted Windows virtual memory; stopping our development servers and checking sequentially
resolved the build. Local preview uses the production bundle to reduce memory use.
Final verification: production build passed; all 7 Edge browser tests passed (17.4 s), including
mobile canvas, reduced motion, route geometry, authentication failures and keyboard focus. Three
data unit tests passed. An intermediate mobile run hit WebGL context loss; explicit context release
on unmount was added and the complete suite then passed. Desktop/mobile screenshots inspected.
GitHub Actions run 37998491860 passed both backend and frontend jobs on 7a0fcf5.
No new cloud resources, provider calls, credentials or API contract changes in this visual revision.

## User-authorized frontend integration — 2026-10-10 IST

The user explicitly replaced the backend-only constraint with a request for a cinematic 3D
dashboard matching the supplied image/video, and confirmed city-first layout with a side planner.
Added frontend/ (React, TypeScript, Vite, Three.js), PRODUCT.md, DESIGN.md and scripts/dev.mjs.
Preserved backend APIs. The city is original illustrative geometry; route view uses actual saved
OSRM GeoJSON. PM2.5 metrics derive from the saved real response, clearly historical, not live.
Live mode clears historical data and uses Cognito PKCE + protected REST calls; tokens remain in
memory. No keys are bundled, notifications sent, physical watch connected or model accuracy invented.

Features: 3D orbit/zoom/reset/pause; route comparison panel; source/quality warnings; air data quality,
wearable latest reading, alert list, grounded explanation and ML status clients; reduced-motion,
mobile layout, WebGL fallback, focus-trapped settings and no silent demo fallback. No hosting deployed.
Added exact HTTPS frontend_origins CDK context for API Gateway/Lambda CORS, rejecting wildcard origins.

Actual verification: production build passed;3 data-unit tests and4 Edge browser tests passed;
real browser→local FastAPI health/CORS request passed;169 backend tests passed,1 Docker test skipped,
3 upstream warnings; Ruff and production npm audit passed (0 known production vulnerabilities).
Desktop/mobile screenshots inspected. Design detector returned[]; independent review findings
addressed for live attribution, warning visibility, pending mode changes and mobile loading layout.
Default CDK synthesis and structural security review passed. Full npm audit initially found
development-runner advisories; upgrading Vitest to5.0.3 resolved them, with3 tests passing and
0 vulnerabilities in the full audit. CI follow-up results are recorded after verification. Live Cognito/provider service
success remains unverified; historical preview works without credentials. Separate team commits.

## Phase 7 current state — 2026-10-10 IST

Local integration, complete 42-operation OpenAPI/response contracts, token-free Postman examples,
authenticated isolated demo, real-road Delhi benchmark, replay verifier, guarded deployment/
retaining-teardown wrapper and structural infrastructure review are implemented. No frontend.
The following Phase7 status supersedes older historical credential/feature notes below.
Full evidence, costs, commands and cleanup are in [DEMO_READINESS.md](DEMO_READINESS.md).
**AWS resources actually provisioned/used: none. Public deployed backend URL: none.**

Real external checks: Open-Meteo 192 records; OpenAQ two bounded authenticated sensor queries
returned 0 new observations; live OSRM six cases/two real road candidates each. Complete
PM2.5 coverage in four cases; two partial cases have null full exposure. No improvement over
fastest demonstrated. Saved benchmark arithmetic replay verified 12 routes without provider calls.
The original live report predates content hashing: zero content hashes verified for that report;
new benchmark reports include Parquet content hashes. Do not infer reproducible provider state
from replay alone. Demo uses actual saved forecasts plus clearly synthetic wearable/alert fixtures;
no notification or real watch event. Genuine Amazon Location routing remains unverified live.

ML preparation:389 records,5 observed PM2.5,1 station,0 eligible hourly samples. Training unavailable;
no measured MAE/RMSE/bias or persistence comparison. Bedrock fallback/ownership/consent and JWT
failure tests run offline. Cognito cloud login, SMS delivery, CloudWatch alarms and live IoT remain
unverified. User continues to defer credentials. No authenticated AWS action/deploy/training run.

Files created: src/ecoroute/contracts.py; scripts/{export_api,benchmark_routes,demo_backend,
replay_benchmark,manage_cloud,security_review}.py; tests/test_phase7.py;
docs/{FRONTEND_INTEGRATION,DEMO_READINESS}.md, docs/openapi.json and examples/Postman JSONs.
Updated app description, grounded coverage field, ML/wearable repository dependency injection,
development dependency lock, CI Docker/API checks and all five living project documents.
Existing Dockerfiles, CDK stacks and schemas reused; no completed phase recreated.

Validation commands: pytest; Ruff; pip check; export_api.py; smoke_local.py; build_lambda.py;
offline cdk synth --no-lookups; security_review.py; manage_cloud.py plan; bounded ingest_air.py;
benchmark_routes --provider osrm --live; replay_benchmark; demo_backend; train.py --prepare-only.
Expected ML preparation failure is insufficient real data. Initial full test failures exposed a
legacy config test inheriting local AWS settings; it now explicitly supplies empty prerequisites.
A concurrent synthesis/test attempt encountered Node-process errors; sequential execution is used
on this laptop. Final local validation: **164 passed, 1 Docker-dependent skipped, 3 upstream
deprecation warnings**. Ruff, pip check, health/docs/auth smoke, default and optional IoT/workflow
CDK synth, structural security review and export passed. Linux Lambda asset 183.1 MiB rebuilt and
updated with final source changes. Recorded replay verified 4 routes and 5 Parquet content hashes;
live report replay verified 12 routes with no content hashes (older report format). No vulnerability
database scan or live penetration test was performed. Docker execution is a CI verification step.

Remaining work: configure least-privilege non-root deployment credentials/Cognito and selected
provider/model/channel settings, review resource costs, obtain deployment approval, verify real
AWS services after deployment, gather enough measured history, and validate a supported watch
bridge. Credentials and exact steps remain in CREDENTIALS_CHECKLIST.md and linked runbooks.
Separate individually attributed commits are used with all three teammates' authorization.
GitHub verified author mappings for the three Phase7 implementation/security/contract commits.
The first Phase7 CI run37992768638 passed Python checks, then Docker Hub returned504 while
fetching the Python base-image OAuth token; this is not a successful Docker verification.
Final follow-up adds a schema-validated historical real Delhi response and template inventory.
After a second Docker Hub504, both Dockerfiles switched to Docker's official ECR Public image.
Anonymous public image access required no account IAM credentials or resource deployment.
**CI passed on code commit f0a829d**:
https://github.com/deveshsinghal09/ecoroute-ai/actions/runs/37993419466 . All steps passed,
including164 Python tests (1 container test skipped in the normal suite), then1 separate Docker
ML mechanics test, API/ML image builds, real container health/auth smoke, export drift,
Linux-native Lambda imports, default CDK synth and structural security review.
This does not validate measured-data model accuracy or live AWS services. The subsequent
documentation-only verification commit records this exact code revision's result.

## Phase 6 current state — 2026-10-10 IST

Grounded Converse explanations/fallback, owner-scoped deterministic PM2.5 daily advisories,
opt-in verified SMS adapter, private school commute comparison/next-day forecast and optional
inactive environmental orchestration are implemented. Existing route scoring, data pipeline,
ML inference, tables, bucket and Cognito templates are reused. **Real deployed AWS resources:
none.** Bedrock/SMS/workflow executions remain untested live and disabled. User selected SMS
and deferred all credentials until later; no authenticated AWS call was attempted this phase.

Files: new advisory/{api,alerts,explanation,notifications,workflows}.py,
infra/environment_workflow.py, scripts/check_advisory.py, tests/test_advisory.py,
tests/test_environment_workflow_infra.py, docs/PHASE6_ADVISORIES.md. Updated Core/app CDK,
settings/storage/models/router integration, smoke checks, .env.example, README and all five
living documents. Prompt template is SYSTEM_PROMPT in advisory/explanation.py.

Actual checks: full pytest **154 passed, 1 skipped, 3 upstream warnings**; focused advisory
tests **24 passed**; Ruff passed; temporary loopback health/docs/auth smoke passed; SDK
Converse/SNS/StartExecution compatibility passed offline; Linux Lambda asset rebuilt at
**183.1 MiB**; default/optional offline CDK synth and pip compatibility checks passed. Initial school test failed for absent Windows IANA tzdata; corrected with
contemporary Delhi UTC+05:30 support and rerun passed. Local Docker-dependent test remains
skipped; no Docker/live cloud success is implied by local fixture tests.

Offline real-data check: retained OpenAQ station 8917 had **0 usable hourly samples** in the
current 24h assessment window; status unavailable, concentration/breach null, no alert sent.
Earlier real five observations remain intact but cannot support current daily safety or ML
accuracy. New tests use explicitly synthetic mechanics fixtures, not fabricated production
data. Bedrock model ID/access/region compatibility, quotas, SNS topic/destination/DLT IDs,
spending settings, deployed workflow ARN, Cognito IDs and bootstrap remain unverified/missing.
Defaults: 20 Bedrock requests/day, 5/hour, max output256; SMS disabled with 1 USD monthly
allowance and 0.05 USD maximum acceptable message price; proposed Phase6 budget 5 USD/month
requires approval before live enablement. Alerts are not a financial hard cap.

Commands executed: Ruff, focused/full pytest with existing memory/thread caps,
scripts/check_advisory.py, scripts/smoke_local.py, scripts/build_lambda.py; offline CDK synth
passed for default and optional workflows (--no-lookups); Git changes are committed separately. No deploy/Bedrock invocation/SNS
publish/OTP/provider refresh/paid training/workflow execution was run. Separate commits now
use the user-authorized individual authors, rather than joint co-author trailers.

Follow-up: aligned school-day window to the UTC hour preceding India midnight so the
provider two-day forecast can cover the next day. Added timezone/ownership regression test.
The first new test run caught a misplaced test block (NameError); corrected it and all24
focused tests passed. GitHub CI at b6cdbf1 passed every step, including Docker ML mechanics
training/serving tests and Linux asset imports; this is not measured-data ML validation.

Remaining: configure credentials privately after phases, confirm chosen model/provider terms,
regional IAM/quotas and SMS sandbox/DLT, approve exact regional cost/deployment proposal, deploy
and verify cloud behavior. Collect sufficient fresh hourly measurements before claiming daily
observed advisories or trained-model performance. No physical-watch integration is claimed.
Detailed contracts, limits, setup/verification and cleanup: PHASE6_ADVISORIES.md.

## Phase 5 current state — 2026-10-10 IST

Secure wearable-independent registration, revocable scoped consent, measurement ingest,
latest/history/deletion and descriptive journey correlation are implemented. Existing Cognito,
Core/Data infrastructure, route geometry/pollution index and local SQLite are reused. IoT Rule
and validation worker are optional, disabled by default; private stream-based history archive
works for HTTPS/MQTT records in synthesized infrastructure. **Real AWS resources deployed:none.**
No physical watch, cloud MQTT connection, live health measurement or real correlated journey
has been tested. User confirms Noise ColorFit Pro3 Alpha / NoiseFit Assist. OS, public/export API
and Health Connect support are unverified; no hardware connector is selected. WEARABLES.md
records official sources, adapter contract, exact credentials/IAM/enrollment/revocation and costs.

Files: added wearable/{models,repository,api,archive,handlers,correlation,policy}.py;
scripts/simulate_wearable.py, iot_device_plan.py, bind_iot_certificate.py;
infra/wearable_workflow.py, tests/test_wearable.py and docs/WEARABLES.md. Updated Core/Data/IoT
stack integration, app/config/models, legacy telemetry migration, smoke checks, test cleanup,
.env.example, README and all five living documents. Raw certificates/keys/data are never committed.

| Command/check | Actual result |
|---|---|
| python -m pytest -q with NODE_OPTIONS=--max-old-space-size=512, OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 | **129 passed,1 skipped,3 upstream warnings** |
| python -m pytest tests/test_wearable.py -q |8 passed; ownership, revoked consent, latest ordering, duplicate/conflicting events, GPS permission, history pagination, deletion, spoofed certificate/topic/client, SDK transaction shape/race and descriptive correlation |
| python -m pytest tests/test_infra.py -q |8 passed; disabled broker rule, source-account/ARN invoke boundary, private retention and scoped role exceptions |
| python scripts/simulate_wearable.py |Synthetic offline envelope accepted, duplicate detected, private local archive created; no network broker/watch |
| python scripts/iot_device_plan.py with placeholder account/hash/device |Offline CreateThing/CreatePolicy SDK shapes passed; writes work/iot JSON plans only |
| python scripts/bind_iot_certificate.py --help |CLI runs; --apply never used, no authenticated AWS calls |
| python scripts/build_lambda.py |Linux Python3.11 base asset183.0MiB built locally |
| npm run synth; npx cdk synth --no-lookups -c enable_iot=true |Both passed; optional rule disabled; no deployment |
| python scripts/smoke_local.py |Real loopback health/docs200; all7 Phase5 routes without token401, including DELETE; server stopped |
| python -m ruff check .; python -m pip check; tracked credential heuristic; git diff --check |Passed; heuristic is not a complete audit |
| GitHub CI37983707708/37983888606 |Both implementation commits passed, including Docker ML tests and Linux package imports |

Meaningful joint commits addee08 (owned backend) and695cbbc (bounded infrastructure/test
cleanup); final runbook/operator-plan follow-up is jointly credited too. Primary author preserved,
Mayank Gupta and Devesh Raj have contiguous Co-authored-by trailers.

Failures corrected: generated stream IAM initially had unconstrained ListStreams Resource*;
replaced helper mapping with exact stream reads and a region-conditioned required exception.
Local CDK/combined tests initially exhausted Node memory and hit a Windows test stack overflow;
bounded heap/numerical threads and explicit TestClient context cleanup allowed the full suite
to pass. Initial bind-script CLI import failed because scripts is not installed; moved reusable
policy generator into ecoroute.wearable.policy and verified CLI help. No AWS denial is relabelled
as deployment success.

Security/retention: scopes and ownership precede processing; atomic revision/consent check with
event writes, observation TTL7d, private pseudonymous archive lifecycle7d (not anonymized),
per-device deletion/tombstone90d, AWS stream/failure retention up to24h. MQTT principal is checked
against operator-bound actual certificate thumbprint, exact topic/client and payload owner.
Legacy /wearables/telemetry returns410 to prevent a revocation bypass. No health-data SNS delivery
or medical/causal heart-rate inference; environmental threshold alerts are deferred until correct
averaging windows, sourced limits and notification consent exist.

Blockers: watch OS/export API; actual authorized bridge; scoped AWS IAM/bootstrap; Cognito
login/IDs; deployed wearable table/bucket/roles; IoT endpoint/Thing/certificate/policy binding;
account quotas and budget recipient. No new authenticated AWS action was taken. Previous
dev-admin/devesh_eco identity in credit account/ap-south-1 remains selected, Lambda denied.
Before provisioning show final stack/resource costs and request deployment approval. Official
Mumbai IoT-only example3 bridges at1 <=5KB message/minute for30days estimates USD0.189;
storage/compute/alarms/API and taxes extra. Proposed USD5 incremental warning is not a hard cap.
No frontend or mobile app was created. Phase4 real environmental data remains197 records,
including5 measured PM2.5 observations, insufficient for ML training; no new model/job.

## Previous Phase 4 report (preserved)

## Current state — 2026-10-10 IST

Phase 1–3 prerequisite verification passed before Phase 4 implementation: 107 tests,
loopback health/authentication smoke checks and successful prior GitHub CI. Their cloud blockers
remain unresolved; existing code and infrastructure were reused.

Phase 4 training, evaluation, inference and optional SageMaker orchestration are implemented.
**Real AWS resources deployed: none. Real training jobs/endpoints/uploads: none.**
The actual local dataset now has 197 records:192 Open-Meteo (76 modeled,116 forecast) and
5 measured OpenAQ PM2.5 observations; zero eligible training samples. Training stops with insufficient_data;
there is no real trained model, measured accuracy or claimed improvement over persistence.

### Files created and updated

- Added requirements-ml.txt, Dockerfile.ml, src/ecoroute/ml/{preprocessing,training,inference,
  api,route_index,sagemaker,workflow,cloud,container}.py; scripts/train.py, evaluate.py,
  sagemaker_plan.py and upload_ml_dataset.py; tests/test_ml.py, test_ml_container.py and test_ml_workflow.py.
- Added infra/ml_workflow.py; integrated optional ML resources with Core/Data/ML stacks,
  FastAPI configuration and routing cache namespaces. Updated Docker context whitelist, CI,
  local smoke checks, .env.example, README and all five living documents. ML_WORKFLOW.md is
  the detailed data, IAM, cost and operation runbook.
- Meaningful joint commits: 71bd555 implementation and dc36fcf container/CI verification;
  documentation/upload/smoke work follows in another joint commit. Both teammates have
  contiguous Co-authored-by credit alongside the actual primary author.

### Commands executed and results

| Check | Actual result |
|---|---|
| python -m pytest -q | 120 passed, 1 container test skipped locally, 3 upstream warnings |
| python -m ruff check .; python -m pip check | Passed |
| python scripts/smoke_local.py | Real loopback health/docs200; domain, routing and all six ML endpoint requests without tokens401; server stopped |
| python scripts/train.py --prepare-only | Expected insufficient_data nonzero exit; 192 inputs, zero measured labels/samples; work/ml/data_audit.json |
| python scripts/diagnose.py --aws --profile dev-admin --region ap-south-1 --json-out work/phase4-iam-diagnostic.json | STS/region pass; Lambda denied; bootstrap/SageMaker quotas unverified; Cognito/budget missing; Docker stopped |
| GitHub CI run37979545452 on dc36fcf | Success, including real Docker build and container training/serving protocol test on explicitly synthetic mechanics fixtures |
| python scripts/build_lambda.py | Linux base asset183.0MiB built; numerical dependencies kept in optional container |
| npm run synth; npx cdk synth --no-lookups -c ml_image_uri=PLACEHOLDER_REGIONAL_DIGEST | Default and optional ML configurations passed offline; placeholder image is not a real ECR integration |
| Official public AWS price offer retrieval | Mumbai ml.m5.large training and batch transform each USD0.121/hour; pricing evidence saved under ignored work/ |

Initial ML dependency installation failed because C: had no space. A combined cleanup command
was rejected by automatic approval review without a reason; generated Phase 3 CDK output was
instead preserved by moving it to D: scratch. Optional ML dependencies were installed there
and linked into this local virtualenv. The initial MaxPendingTimeInSeconds600 SDK contract
test failed; corrected to the supported minimum1800, with subsequent tests passing.
The first direct npm synth used system Python and failed to import aws_cdk. Prepending
the project .venv/Scripts to PATH corrected the interpreter; both subsequent synth runs passed.

### Blockers and remaining work

Collect sufficient real hourly monitoring history with honest availability timestamps. The user
confirmed OpenAQ rotation on2026-10-10 IST; bounded live discovery and measurement ingestion
then succeeded using local credentials. Backfilled observations fetched today cannot
be silently treated as features available months ago. No weather adapter/history is configured.

Selected identity remains dev-admin / IAM user devesh_eco in user-confirmed credit account,
ap-south-1. Missing: scoped permissions, verified bootstrap and training quota, existing approved
ML bucket, reviewed regional ECR image digest, execution-role ARN, Cognito configuration and
budget alert recipient. Follow ML_WORKFLOW.md before any authenticated ML operation.

Proposed ml.m5.large runtime cap15minutes gives USD0.03025 compute arithmetic, plus startup,
storage, orchestration, logs and other charges. A USD1 experiment warning is proposed; alerts
are not hard caps and credits do not remove billing risk. No paid training, endpoint or deployment
will start without a concrete resource/cost review and explicit approval. No frontend exists.

### OpenAQ verification follow-up — 2026-10-10 IST

Commands: ingest_air.py --source openaq --stations --max-pages1 returned100 station entries,
incomplete=true/resume_page2 (expected bounded-page exit2, not an authentication failure).
Selected GK1 (Oberoi Terrace), location2860223/sensor9320367, with provider-reported
CC BY4.0 attribution to Oberoi. One measurement page for2026-10-09T14:00Z..20:00Z
returned5 hourly observed PM2.5 values, normalized ug/m3, range51.2..82.0; missing/rejected0,
flagged0. Reports cover15:00Z..19:00Z; collected19:38:48Z. Values were not fabricated.

Local-only files: raw/stations/date=2026-10-10/page=1.json, raw/source=openaq/date=2026-10-09/
a0dd0f1e0e55650c6e377eac5378b2e35fa3b8520e19190cd374ceb83c5c703a.json and
curated/source=openaq/date=2026-10-09/3e13c194baa6a5c99b26858f71a043b6a1f7fc67e3ee2181ff4e02a17768f350.parquet
under ignored work/environment, plus SQLite metadata. No key/raw dataset was committed.

Re-running train.py --prepare-only returned insufficient_data:197 inputs,5 measured records,
1 station series,0 eligible samples. Minimum temporal span and availability constraints remain.
No model, accuracy, AWS upload, paid training or deployment. Updated README, all five living
documents, INGESTION.md and ML_WORKFLOW.md; source unchanged, no new unit tests needed.
Previous final code CI run37981134919 passed. Follow-up document checks are recorded in commit.

## Previous Phase 3 report (preserved)

## Current state — 2026-10-09 IST

Phase 1 foundation, Phase 2 ingestion and Phase 3 routing are implemented and verified locally.
**Real AWS resources deployed: none.** No frontend, ML training or working watch connection.
CLI profile **dev-admin** authenticates as IAM user **devesh_eco**, region **ap-south-1**.
The user confirmed this account holds hackathon credits. Ignored .env uses that profile and
verified account; the old default/root profile belongs to a different account and is no longer used.

Real Routes V2 CalculateRoutes and Places V2 Geocode probes both returned AccessDeniedException.
The new IAM diagnostic verifies STS/region configuration but cannot verify Lambda access,
bootstrap or quotas. No additional IAM policies, Budget, resources or deployments were created.
The exact two-action Location policy and operator Console steps are in ROUTING.md.

Phase 3 adds six authenticated /api/v1/routes endpoints; valid provider route generation,
flexible-polyline decoding/GeoJSON, distance segments and traversal timestamps, time/spatial
pollutant matching, coverage/provenance/uncertainty, PM2.5 concentration-time exposure, baseline
relative changes, detour limits, normalized ranking and departure comparison. Missing data is
unavailable, never zero. All routes sharing one model grid explicitly warn against street-level
claims. Cycling is rejected because no supported bicycle provider is configured. Optional
ventilation-dose estimation and durable batch route studies are deferred, as explained in ROUTING.md.

Owner-isolated route pointers/cache reuse DynamoDB route_metadata; private route JSON and
redacted aggregates use S3 prefixes in the existing data bucket. Local equivalents work under
ignored work/. Route metadata/lifecycle7d; logical cache5min. Storage consent, bounded calls,
body/response limits, structured logs, default-disabled Location IAM and existing alarms remain.
Legacy /navigation/routes stays a placeholder; callers use /routes/compare and /routes/optimize.

### Files and meaningful commits

- d1d32ed: routing/{models,geometry,providers,pollution,service,api}.py, demo_routes.py,
  recorded Delhi fixture and routing tests; configuration/storage/main integration;
  CDK optional scoped Location IAM/lifecycle and smoke/infrastructure tests.
- This report update: README and all five required living documents, ROUTING.md, cost/source
  notes and the current credential gates. Joint commits retain the actual primary author
  and credit Mayank Gupta and Devesh Raj with contiguous Co-authored-by trailers.

GitHub's authors API verified that adfa4a1 links all three accounts: deveshsinghal09,
Mayank2142 and DEVESH859. The final follow-up replaces the interim reason on unselected
routes with eligibility/coverage explanations; all 35 routing tests pass again. Documentation
whitespace was corrected and git diff --check passes. GitHub CI is also run on each push;
local passing checks do not by themselves establish its result.

### Commands and verified results

| Command/check | Result |
|---|---|
| aws sts get-caller-identity --profile dev-admin --region ap-south-1 | Passed; IAM user devesh_eco, user-confirmed credit account |
| python scripts/diagnose.py --aws --profile dev-admin --region ap-south-1 --json-out work/iam-diagnostic.json | Identity/region/tools pass; Lambda AccessDeniedException, bootstrap/quotas unverified; Cognito/budget missing; Docker engine stopped |
| python -m pytest -q | **107 passed**, 3 upstream deprecation warnings, zero failures |
| python -m ruff check .; python -m pip check | Both pass |
| python scripts/smoke_local.py | Real loopback FastAPI process: health/docs200; protected domain and four routing POSTs401; readiness checked; process stopped |
| python scripts/demo_routes.py --provider recorded | Two genuine recorded OSRM road routes scored with existing real Open-Meteo forecast; output work/phase3-demo.json |
| python scripts/build_lambda.py | Linux Python3.11 asset183.0MiB; no cloud upload |
| npm run synth | EcoRouteData/Core/ML synthesized with --no-lookups; no provisioning |
| python scripts/check_repo.py; git diff --cached --check | Tracked-file credential heuristic and whitespace check pass; heuristic is not a complete secret audit |

During added SDK-contract testing, one mock initially omitted a required nonempty TruckRoadTypes
list. Corrected the test fixture to match the SDK schema; full 107-test run passes. Live denied
AWS probes remain failures, not converted into success by mocked tests.

### Real demonstration evidence and remaining work

One live public-landmark OSRM call returned HTTP200, two road geometries (117/96 vertices),
2822.5m/206.7s and 2712.6m/231.6s. It is stored as a clearly labelled recorded fixture.
The rerun used the existing real Open-Meteo collection from 2026-10-08T18:11:31.163657Z,
matched valid time21:00Z and concentration87.1ug/m3. Exposure indices are5.0009916667 and
5.6034333333ug*h/m3; alternative+12.0464% against fastest baseline. Same cell means the
difference reflects travel time, not a demonstrated cleaner street. No successful AWS route,
OpenAQ station observation or S3 upload is claimed. Detailed provenance is in ROUTING.md.

An OpenAQ credential disclosed in chat was not saved or used. Revoke it and configure a fresh
OPENAQ_API_KEY in ignored .env. Then run bounded station discovery/ingestion and verify actual
Delhi coverage/licensing. Do not send the replacement in chat.

Next: an authorized operator grants scoped Location and diagnostic permissions; rerun the
bounded AWS demo only after permissions change. Configure Cognito IDs/callback/login, inspect
bootstrap/quotas and credit expiry/eligibility, choose budget alerts/recipient, review a concrete
regional cost estimate and approve deployment separately. Alerts do not hard-cap costs. Optional
watch/ML/batch study work remains outside this completed local Phase 3 scope.

## Historical Phase 1 and 2 report (superseded where noted above)

As of 2026-10-09 (India time; real ingestion timestamp below is UTC). Backend foundation and environmental pipeline implemented and tested locally.
**Real AWS resources deployed: none.** No bootstrap, Budget, secret, pool, training job or paid
workload created. No frontend. Previous report preserved in PHASE0_REPORT.md; its old stop/status
statements are historical and superseded by the authorized Phase 1+2 work.

## Implemented scope

- FastAPI versioned health/ready/docs, seven domain routers, strict Pydantic validation,
  Cognito access JWT verification/scopes, owner isolation, consent, bounded telemetry/trips,
  idempotency and SQLite/DynamoDB adapters. Navigation/ML/school products explicitly return 503.
- Core/Data/ML CDK stacks plus optional IoT identity scaffold. Lambda chosen over idle Fargate;
  private encrypted/TLS storage, six on-demand tables with TTL/caps, two buckets with lifecycle,
  three business Lambdas, HTTP API/Cognito, disabled schedule, queue/DLQ, logs/six alarms/SNS and
  external secret references. Extra CDK S3-notification helper is deployment-only.
- Real Open-Meteo adapter; credential-gated OpenAQ v3 adapter; typed observed/forecast/modeled
  records, unit/time/coordinate validation, provenance/quality, bounded rate-limited historical
  requests, coarse-grid request cache, deterministic replay, raw JSON/curated Parquet,
  metadata queries and five environmental endpoints. No fabricated gap filling.
- Local ingestion CLI, Lambda collector/cleaner with partial failures, Docker setup, diagnostics,
  Linux packaging script, CI, tests and current credential/API/service/cost documentation.

## Files created or changed

Phase 1: src/ecoroute/{auth,models,storage,routers,config,main}.py; handlers/{api,tasks}.py;
infra/{app,stacks}.py; tests/{conftest,test_api,test_adapters,test_infra}.py; Dockerfile,
compose.yaml, .dockerignore; scripts/{build_lambda,smoke_local}.py and dev.ps1; requirements,
.env.example and CI. Commits 8f44f22 and 2b13639 preserve these implementation units.

Phase 2: src/ecoroute/environment/{schema,providers,repository,pipeline,api}.py;
handlers/ingestion.py; scripts/ingest_air.py; tests/test_environment.py; updates to CDK/app,
requirements/CI/diagnostics and all five living docs; docs/INGESTION.md and README/CONTRIBUTING.
Phase 2 implementation commit: 7a3bb17 (joint co-author credit).
The earlier tasks.py handler remains a tested bounded helper; the deployed template selects
handlers.ingestion.collect/clean for the actual Phase 2 workflow.

## Executed checks and exact results

| Command/check | Result |
|---|---|
| python -m pytest -q | 71 passed; three upstream deprecation warnings (Starlette/httpx and Mangum event loop); no failures |
| python -m ruff check . | Passed after correcting three redundant-parenthesis findings |
| python -m pip check | Passed |
| python scripts/smoke_local.py | Actual loopback server: health/docs 200, unauthorized domain 401, readiness checked; process stopped |
| python scripts/ingest_air.py --source open_meteo | One real HTTP 200; 192 records, two Parquet partitions; repeat cache_hit=true |
| python scripts/build_lambda.py | Initial PyArrow 23 wheel incompatibility fixed by pin 20; Linux asset 182.9 MiB |
| npm run synth (cdk synth --no-lookups) | EcoRouteData, EcoRouteML, EcoRouteCore synthesized; initial dependency cycle fixed by queue ownership in Data |
| python scripts/diagnose.py --region ap-south-1 | Offline tool/SDK checks; warnings for missing budget/Cognito and stopped Docker; no new authenticated AWS calls |
| docker compose config --quiet | Passed earlier; engine execution not tested |
| aws sts get-caller-identity (earlier authorized read) | default profile root identity valid; hackathon profile absent |
| lambda get-account-settings; EC2 DescribeRegions; CFN DescribeStacks (earlier reads) | SubscriptionRequiredException / OptInRequired; entitlement and bootstrap blocked/unverified |

Cloud behavior is structural/mocked validation only. Windows cannot execute Linux native wheels;
CI includes built-asset import checks. GitHub run 37824934626 succeeded at commit e70742e:
https://github.com/deveshsinghal09/ecoroute-ai/actions/runs/37824934626 . This verified Ubuntu
tests, lint, smoke, secret heuristic, native Linux package imports and CDK synthesis.
No model was trained or evaluated; no wearable data was retrieved from a real watch.

## Real environmental evidence

One Open-Meteo response collected 2026-10-08T18:11:31.163657Z. Returned model coordinates
28.800003, 77.20001. 192 records = 76 modeled + 116 forecast at collection; zero missing/flagged
values in that response. Approximately 45 km native model resolution, not street observations.
Raw/Parquet keys and attribution in INGESTION.md. Raw data remains in ignored local work/environment;
no S3 object upload was performed. OpenAQ stopped before HTTP because its key is absent.

## Credentials, deployment and next steps

1. Resolve AWS account activation/subscription errors. Current valid default session is root,
   authorized by the user for read-only checks; use scoped temporary roles for ongoing development.
2. Configure OpenAQ key privately, discover actual Delhi stations, inspect licenses/coverage,
   then run a bounded observation ingestion. Do not paste any credential into chat.
3. Confirm credit eligibility/expiry and alert email. User permits up to reported US$100 credits;
   use the $10-15/month small-demo planning envelope, not deliberate credit exhaustion. Create
   proposed budgets only with reviewed setup; alerts do not hard-cap costs.
4. Review account concurrency, bootstrap execution policy, Cognito callback URL, runtime IAM,
   synthesized resources and current region pricing; obtain specific deployment approval.
5. After deployment only: verify outputs, configure Cognito login, subscribe/confirm operational
   email, run authenticated AWS smoke tests, one bounded ingest and S3/Parquet/index/DLQ checks;
   enable the schedule only after these pass.
6. Routing, exposure scoring, trained ML, durable multi-city backfill orchestration and actual
   Noise watch integration are subsequent work. Do not claim them from this foundation.

OpenAQ, Cognito identifiers/login, service entitlement, bootstrap/deploy boundary and a confirmed
notification recipient are missing. Exact creation/storage/verification instructions are in
CREDENTIALS_CHECKLIST.md; no deployment success is inferred from synthesis.

## Shared-laptop contributions

User confirms all three teammates jointly work in this chat/laptop. New joint commits credit
Mayank Gupta <mayankcoding73@gmail.com> and Devesh Raj <deveshraj003@gmail.com> using Co-authored-by
trailers while retaining the configured primary author. No fabricated individual work or history
rewrite to balance counts. GitHub attribution requires each account to associate the email.

Final verification update: tracked-file secret heuristic and git diff --check passed; no local
changes to credentials or live cloud resources. Added scripts/commit-joint.ps1 after GitHub's
co-author API revealed that blank-separated trailers in the first two Phase 2 commits recognized
only the final co-author. The helper preserves both teammates in a contiguous final trailer block.
Published earlier history is preserved. Remote attribution is checked on the helper/report commit.

UI cleanup and travel controls (2026-10-10): removed observatory/history overlay, scene-bottom badges, footer text and Explore your routes CTA as requested. Source/date disclosure remains in route details and connection settings. Walk/Cycle are selectable and clear mismatched driving results. Walking still requires authenticated live AWS routing; cycling remains blocked by missing bicycle provider (no fabricated routes). Production build and 10 browser tests passed, including travel-mode selection and removed-element assertions. No backend/provider provisioning performed.

Google Maps integration verification (2026-10-10): implemented server-only Routes/Places adapter, request-only Google route results (no persistent route cache), and Journeys Google map with separate restricted browser key. Earlier validation in this work session: 179 backend tests passed, 1 skipped; Ruff passed; 6 frontend unit tests and 2 mocked Google Maps browser tests passed. Final production build and all 10 dashboard browser tests passed, including train motion/pause. No live Google requests or AWS deployment performed. Google keys and Cognito configuration remain prerequisites; see GOOGLE_MAPS_SETUP.md.

Local display recovery: restarted npm run dev after port 5173 had no listener. Dashboard, city background, train sprite and backend health all returned HTTP 200. Existing animation test passed. Insights already uses Bedrock Converse for supported stored routes when enabled; deterministic explanations remain the fallback (including Google request-only routes). No Gemini integration added, per user preference. Configure ENABLE_BEDROCK, BEDROCK_MODEL_ID and an authorized AWS profile/region before live use; no model invocation was performed.
CDK synth --no-lookups passed on retry; the first attempt failed with a temporary jsii module extraction error (Cannot find module ../errors). Synthesis does not provision resources.

## Original 3D wearable showcase — 2026-10-10

Added an original procedural React Three Fiber / Three.js watch in the existing Wearable panel.
No CodePen/template/model/image asset reused. Seven canvas-textured screens, full modeled straps,
beveled case/glass, crown, bounded rotation, floating motion, local theme/brightness/demo-card settings.
Wearable panel only is widened (430px desktop, 370px tablet; mobile remains fluid). Existing device
read/auth/consent behavior is preserved. All health values remain explicitly demo; no hardware
connection, API data ingestion, notification delivery or AWS changes claimed.

Validation: production build passed; 6 existing frontend unit tests passed; 13 browser tests passed
in one run (10 existing + 3 new), plus a fourth new 3D tap/crown/pause test passed separately after
correcting its scroll position. Visually reviewed desktop and mobile screenshots. Initial texture
UV cropping found during visual review was fixed. Dependency installation reported 0 vulnerabilities.
Build warns about the lazy Three.js chunk (~245 kB gzip); this code loads only for Wearable.
No backend tests rerun for this frontend-only change. See CUSTOM_WATCH.md for limitations.

Watch display readability (2026-10-10): enlarged physical case/display 45%, refit camera to retain
both straps, expanded Wearable panel to 460px and canvas height, reduced viewing tilt, doubled
screen texture resolution to 1024x1200, raised DPR cap to 2, and increased text weight/minimum size,
metric type and label contrast. Accessible summary is larger too. Production build and all four
watch browser tests passed, including mobile render, WebGL fallback, swipe and modeled crown.
Desktop screenshot inspected; no API/data/auth changes. Lazy bundle size warning remains.

Wearable theme and screen containment (2026-10-10): user superseded blue-sidebar request with
white/orange. Sidebar and device controls now share warm white surfaces, fine neutral borders,
orange selection states and a transit-orange default screen theme. Screen uses a flat rounded
ShapeGeometry instead of mapping text across extruded bevels. Label widths are measured and fitted
inside individual safe boxes, shortened labels avoid overlap, mipmap blur is disabled and renderer
DPR is 2. Desktop screenshot inspected. Build and all 15 browser tests passed, including a new
canvas measurement test across all seven screens and home metric-card bounds. No backend changes.
Existing lazy Three.js bundle warning remains. No new resources or credentials required.

Wearable placeholder removal (2026-10-10): removed the default health fixture entirely. With no
connected data, every measurement page now reports no readings / watch not connected; only local
time/date and appearance settings are populated. No invented health or battery readings are shown.
Replaced visible demo wording, and extended the orange showcase border uniformly around all four
sides. Real hardware connection remains unavailable; no new integration is claimed. Production
build and five watch browser tests passed. Existing lazy bundle warning unchanged.
