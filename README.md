# EcoRoute AI

AWS-native backend for pollution-aware navigation in Delhi. **Phase 1 backend foundation and
Phase 2 environmental pipeline are implemented locally. No AWS resources have been deployed.**
No frontend, trained ML model, verified Noise watch integration or street-level pollution claim.

FastAPI + Pydantic v2, Cognito JWT validation, Lambda/Mangum, CDK Python, S3/DynamoDB adapters,
Scheduler -> collector Lambda -> raw S3 -> SQS -> cleaning Lambda -> Parquet + metadata.
AWS target: Mumbai (`ap-south-1`). No idle Fargate service, NAT Gateway or database server.

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
Navigation, trained predictions and school safety currently return explicit 503 responses.

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

The current default AWS login identifies as root (user-authorized read-only exception), but
Lambda reported `SubscriptionRequiredException` and EC2/CloudFormation `OptInRequired`.
Resolve account activation/service access in the AWS Console or with AWS Support first.
Use an individual temporary development role for ongoing work; workload roles are least privilege.
No service-access error will be fixed by adding AdministratorAccess.

Confirm eligible credit balance/expiry, alert recipient, Cognito callback URL and bootstrap role
policy. User permits using up to the reported $100 credits; this is a ceiling, not a spending target.
Review the [$10-15/month demo planning envelope](docs/COSTS_AND_BUDGET.md) and obtain specific
deployment approval before bootstrap/deploy. Budget alerts do not hard-cap costs.

## Documentation

- [Current state, checks and blockers](docs/PROJECT_STATE.md)
- [Architecture](docs/ARCHITECTURE.md) and [AWS services/IAM](docs/AWS_SERVICES.md)
- [Credential runbook](docs/CREDENTIALS_CHECKLIST.md) and [API contract](docs/API_CONTRACT.md)
- [Ingestion and real-run evidence](docs/INGESTION.md)
- [Verified official sources](docs/VERIFIED_SOURCES.md)
- [Joint contribution workflow](CONTRIBUTING.md)
