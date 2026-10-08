# EcoRoute AI project state — Phases 1, 2 and 3

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
