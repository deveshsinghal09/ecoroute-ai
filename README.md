# EcoRoute AI

## Interactive city dashboard

The requested React/TypeScript + Three.js frontend is now in [frontend/](frontend/README.md).
It follows the supplied cinematic city reference, with orbit/zoom controls, a route planner,
real recorded route geometry, source warnings and secure live API mode. Preview data is explicitly
historical; the city is illustrative. Existing backend behavior and JWT protection are preserved.

```powershell
npm --prefix frontend ci
npm run dev
```

Open http://127.0.0.1:5173 . This starts the local API and UI; no AWS deployment or paid provider
request is made on page load. Live Cognito/API configuration remains manual; see the frontend README.
The earlier backend-only phase notes below are historical and superseded by this user request.

Phase7 local integration and demo readiness: [runbook and actual evidence](docs/DEMO_READINESS.md),
[complete frontend integration contract](docs/FRONTEND_INTEGRATION.md),
[OpenAPI](docs/openapi.json), [Postman examples](examples/ecoroute.postman_collection.json).
No AWS deployment/public URL, trained model or supported physical watch connector is claimed.
Run `python -m scripts.demo_backend` for an isolated authenticated backend scenario; synthetic
wearable/alert inputs are explicitly labeled and real notifications remain disabled.

AWS-native backend for pollution-aware navigation in Delhi. **Phase 1 backend foundation and
Phase 2 environmental pipeline, Phase 3 routing engine, Phase 4 ML workflow and Phase 5 wearable-independent backend, Phase 6 advisories and Phase 7 integration are implemented locally. No AWS resources have been deployed.**
No frontend, trained ML model, verified Noise watch integration or street-level pollution claim.

FastAPI + Pydantic v2, Cognito JWT validation, Lambda/Mangum, CDK Python, S3/DynamoDB adapters,
Scheduler -> collector Lambda -> raw S3 -> SQS -> cleaning Lambda -> Parquet + metadata.
AWS target: Mumbai (`ap-south-1`). No idle Fargate service, NAT Gateway or database server.

## Wearable telemetry and consent

Device registration, revocable scoped consent, validated measurements, latest/history/deletion
and descriptive journey pairing now work through authenticated REST APIs. Optional IoT Core
mTLS rule/validator and private stream-based S3 history are synthesized; rule disabled and no
device enrolled. The confirmed watch is Noise ColorFit Pro3 Alpha with NoiseFit Assist; OS and
authorized export/API support are unverified, so no hardware connector is claimed.
Run `.\.venv\Scripts\python.exe scripts/simulate_wearable.py` for explicitly synthetic offline
MQTT-envelope acceptance/deduplication/archive checks. It does not connect to AWS or the watch.
[WEARABLES.md](docs/WEARABLES.md) covers all seven APIs, adapter contract, IAM/Console enrollment,
certificate revocation, privacy/retention/deletion and cost proposal. No frontend/mobile app.

Phase5 verification:129 local tests passed,1 Docker skip; default and optional IoT CDK synth
passed. Both implementation CI runs passed. Do not use legacy /wearables/telemetry writes:
they now return410; register a device and grant revocable consent first.

## Train and serve station forecasts

Install optional numerical dependencies with `.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt`.
Run `.\.venv\Scripts\python.exe scripts/train.py --prepare-only` to audit actual curated data.
Current result:197 records, including192 Open-Meteo modeled/forecast values and5 actual OpenAQ
PM2.5 observations from GK1 (Oberoi Terrace), attributed to Oberoi under reported CC BY4.0.
OpenAQ authentication and bounded ingestion passed after confirmed key rotation. Training
correctly stops with zero eligible samples; no real model metrics or predictions exist. RF/HGB, persistence/provider comparisons,
leakage-safe chronological preparation, trusted serialization, protected ML APIs and route
prediction matching are implemented. [ML_WORKFLOW.md](docs/ML_WORKFLOW.md) gives runnable
training/evaluation, S3 upload, dry-run SageMaker specifications, IAM/quotas, costs and cleanup.

Phase4 verification passed120 local tests; the container test is skipped on this laptop while Docker is stopped.
[CI run37979545452](https://github.com/deveshsinghal09/ecoroute-ai/actions/runs/37979545452)
passed the real ML Docker build and training/serving test using clearly labelled synthetic mechanics
fixtures. Those tests do not establish real pollution forecast accuracy. No paid job or endpoint
starts automatically; actual measured history and explicit deployment/training approval come first.

## Run locally

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
Copy-Item .env.example .env  # only on first setup; preserve an existing .env
.\scripts\dev.ps1
```

Open `http://127.0.0.1:8000/docs` for the REST contract, or GET `/api/v1/health`.
`/api/v1/ready` returns 503 until storage and Cognito configuration are available. Health does
not claim AWS/provider readiness. Local storage lives under ignored `work/`; use a single local
server/ingestion process for SQLite writes. Docker is optional (`docker compose up --build`);
the engine on this laptop was stopped, so container execution has not been verified.

Protected routes require a valid Cognito access token with `ecoroute/read` or `ecoroute/write`.
There is no insecure login bypass. Tests inject an ephemeral RSA verifier, isolated SQLite and
synthetic fixtures; these fixtures are never presented as live observations.
See [credential setup](docs/CREDENTIALS_CHECKLIST.md) for Cognito and OAuth PKCE prerequisites.

## Ingest real model data locally

```powershell
.\.venv\Scripts\python.exe scripts/ingest_air.py --source open_meteo
```

No key is required for Open-Meteo's eligible noncommercial free service. One real Delhi request
succeeded on 2026-10-08: 192 records (76 modeled, 116 forecast), two Parquet partitions, no missing
values in that response. This is a roughly 45 km global model, not measured roadside pollution.
See [ingestion runbook](docs/INGESTION.md) for provider attribution, backfill, OpenAQ setup,
actual saved object keys, query examples, limits and reproducible verification.

OpenAQ requires your own key configured locally. No live OpenAQ coverage or measurements have
been verified. Missing provider data returns `unavailable`; there is no fabricated fallback.
The Phase 3 `/api/v1/routes/*` endpoints implement route comparison, optimization, exposure,
departure analysis and owned retrieval. Trained predictions, school safety and the legacy
`/navigation/routes` placeholder still return explicit 503 responses.

## Pollution-aware routing

```powershell
.\.venv\Scripts\python.exe scripts/demo_routes.py --provider recorded
```

The demo uses two recorded genuine Delhi road routes and eligible local curated pollution.
Missing pollution stays unavailable. Real AWS Routes/Places adapters use the `dev-admin` profile
for IAM user `devesh_eco`; their latest live checks returned AccessDeniedException.
See [routing runbook](docs/ROUTING.md) for IAM setup, exact commands, API limits, sample results,
provider attribution and scientific caveats. All routes require consent and protected API scopes.

## Validate without AWS credentials

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke_local.py
.\.venv\Scripts\python.exe scripts/check_repo.py
.\.venv\Scripts\python.exe scripts/diagnose.py --region ap-south-1
npm.cmd ci --ignore-scripts
.\.venv\Scripts\python.exe scripts/build_lambda.py
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
npm.cmd run synth
```

Synthesis builds Core, Data and ML storage templates locally, without provisioning or lookups.
PyArrow is pinned to 20.x because its manylinux2014 wheel supports Lambda Python 3.11/AL2;
23.x requires newer glibc. The Linux asset is about 183 MiB uncompressed, below Lambda's limit.
CI also checks that the built Linux asset imports; Windows cannot execute those native wheels.

## Before deployment

The selected `dev-admin` profile identifies as IAM user `devesh_eco`; Mumbai is configured.
Identity is verified, but Location and Lambda reads are denied; bootstrap and account quotas
remain unverified. The old default/root profile belongs to a different account and is no longer
used. An authorized IAM operator must grant the scoped permissions documented in the runbook.
Do not add AdministratorAccess to work around failed diagnostic or data-plane calls.

Confirm eligible credit balance/expiry, alert recipient, Cognito callback URL and bootstrap role
policy. User permits using up to the reported $100 credits; this is a ceiling, not a spending target.
Review the [$10-15/month demo planning envelope](docs/COSTS_AND_BUDGET.md) and obtain specific
deployment approval before bootstrap/deploy. Budget alerts do not hard-cap costs.

## Documentation

- [Current state, checks and blockers](docs/PROJECT_STATE.md)
- [Architecture](docs/ARCHITECTURE.md) and [AWS services/IAM](docs/AWS_SERVICES.md)
- [Credential runbook](docs/CREDENTIALS_CHECKLIST.md) and [API contract](docs/API_CONTRACT.md)
- [Ingestion and real-run evidence](docs/INGESTION.md)
- [Routing algorithm, live-test blockers and demonstration](docs/ROUTING.md)
- [Verified official sources](docs/VERIFIED_SOURCES.md)
- [Joint contribution workflow](CONTRIBUTING.md)
# Phase 6 backend additions

Grounded Bedrock explanations with deterministic fallback, complete-window PM2.5 advisories,
opt-in SMS adapter, school commute comparison/forecast and optional inactive AWS orchestration
are implemented. **No AWS resources are deployed.** Bedrock, SMS and continuous workflows remain
disabled pending private configuration and cost approval. No frontend or live notification claim.

Run `python scripts/check_advisory.py` for offline SDK/configuration and retained-data checks.
See [Phase6 runbook](docs/PHASE6_ADVISORIES.md) for API examples, exact credentials/IAM/Console
steps, scientific limits, costs and activation/cleanup. Put local configuration in ignored .env;
never put credentials in committed code. Separate meaningful commits use the three supplied
individual Git authors as requested.

## Google routing integration (2026-10-10)
See docs/GOOGLE_MAPS_SETUP.md (repository root) for separate server/browser keys, APIs, Cognito,
restricted secret IAM and verification. Google Routes/Places feed the existing exposure engine;
Journeys displays Maps JavaScript tiles and route overlays. No real Google service call verified.
Google comparisons are request-only; saved route-ID workflows are unavailable for those results.
No AWS resources were deployed. Google charges are separate from AWS credits.
