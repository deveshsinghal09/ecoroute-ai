# EcoRoute AI

AWS-native pollution-aware navigation backend for Delhi. **Phase 0: architecture and environment
assessment complete; only a local health endpoint is implemented.** No frontend, measured pollution
dataset, trained model, working wearable integration or AWS deployment is claimed.

Design: FastAPI/Pydantic → Lambda + API Gateway HTTP API; Amazon Location Routes V2;
S3/DynamoDB; Scheduler/SQS ingestion. Optional ML and wearable services are gated by evidence,
credentials and cost approval. Target region: Mumbai (ap-south-1).

## Run locally on Windows

```powershell
cd <your-clone-directory>
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn ecoroute.main:app --host 127.0.0.1 --port 8000
```

In another terminal, `Invoke-RestMethod http://127.0.0.1:8000/healthz`.
Blank .env variables use safe app defaults. Keep live flags false. Domain endpoints are planned
in [API contract](docs/API_CONTRACT.md), not silently mocked as successful services.
Docker is optional for this phase; no image pull or engine startup is needed.

## Validate without cloud calls

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/diagnose.py --region ap-south-1
.\.venv\Scripts\python.exe scripts/check_repo.py
npm.cmd ci --ignore-scripts
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
npm.cmd run synth
```

Python CDK entrypoint contains no stacks/resources. Synthesis is local and is not a deployment
test. Never run bootstrap/deploy in Phase 0. Linux/macOS use `.venv/bin/python` and `npm`.

## Configure before Phase 1

1. Read [credential checklist](docs/CREDENTIALS_CHECKLIST.md). Create/login to a named temporary
   AWS profile locally; never paste credentials into chat. Offline development can start without it.
2. Set expected account ID and Mumbai region in your local environment. Run `scripts/diagnose.py
   --aws --profile ecoroute-dev --region ap-south-1` after SSO login. This is read-only.
3. Choose a numeric monthly budget, alert recipient and cash-spend tolerance; check credit balance,
   expiry and eligible services. Review [cost proposal](docs/COSTS_AND_BUDGET.md). Alerts are not caps.
4. For later real pollution data, obtain an OpenAQ v3 key locally and verify Delhi coverage/license.
   Real adapters do not exist yet; do not enable them in this scaffold.
5. Confirm exact Noise watch model, phone OS, companion app and whether an export is available.
   No direct watch integration has been verified.
6. Friends accept repository invitations; set their own Git author identity before their sessions.

## Living documentation

- [Project state and phase report](docs/PROJECT_STATE.md)
- [Architecture and ML/geospatial decisions](docs/ARCHITECTURE.md)
- [AWS service dependencies, IAM and quota gates](docs/AWS_SERVICES.md)
- [Credential and configuration runbook](docs/CREDENTIALS_CHECKLIST.md)
- [API contract](docs/API_CONTRACT.md)
- [Official-source verification](docs/VERIFIED_SOURCES.md)
- [Shared-laptop contribution workflow](CONTRIBUTING.md)

Next phase implements local provider contracts, route scoring with honest fixtures, validation
and an initial forecasting baseline. No paid provisioning begins without a concrete estimate
and explicit approval. Phase 0 stops here.
