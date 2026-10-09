# Phase 7 readiness and operating runbook

Status: locally integrated backend; AWS deployment pending. No frontend or public backend URL.
Read [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md) and [openapi.json](openapi.json)
for all 42 operations, exact request/response schemas and authentication prerequisites.

## Verified environmental demonstration — 2026-10-10 IST

One live Open-Meteo request returned 192 modeled/forecast records, collected
2026-10-09T20:41:21.425577Z; zero missing/rejected values. Data is locally archived raw JSON
and curated Parquet, not uploaded to S3. CAMS global native resolution is approximately 45 km;
hourly values are temporally interpolated. These are not roadside sensor measurements.
Two authenticated, bounded OpenAQ sensor backfills (26032 and12235002, station 8917,
last 24h, one page each) succeeded but returned zero observations. Earlier five real
measurements remain intact. This does not establish that all Delhi stations lack coverage.

Live OSRM fallback benchmark: three public landmark pairs at two departure times, six
successful cases with two genuine road candidates each. Amazon Location was NOT called.
Coordinates are approximate public map landmarks, not verified Places geocoding:

| Origin [longitude,latitude] | Destination | Result |
|---|---|---|
| India Gate [77.2295,28.6129] | Connaught Place [77.2167,28.6315] |206.7s; complete coverage|
| Connaught Place | ITO [77.2415,28.6289] |347.8s; complete coverage|
| India Gate | Lodhi Garden [77.2193,28.5933] |303.9s;74.1% coverage; full exposure null|

First/second departure exposure respectively: India Gate→CP 3.973233/3.864142;
CP→ITO 6.685489/6.501928 ug·h/m³. All complete cases selected fastest as lowest exposure:
**zero demonstrated reduction**. Same coarse forecast cell cannot establish street differences.
Exposure equals sum(PM2.5ug/m³ × segment seconds/3600). Partial sums never become full totals.
Uniform speed within each leg, static fallback traffic,250m segments,25% maximum time detour,
0.5 exposure weight, driving only. Results may change with provider forecasts and road data.
Ignored work/phase7-benchmark.json retains departure timestamps, inputs, geometry and provenance.
Repeat with the same departure timestamp and saved curated dataset; replay verifies arithmetic
without new network calls. Preserve content-hashed dataset snapshots for controlled comparisons.

## Reproduce locally

```powershell
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m uvicorn ecoroute.main:app --host 127.0.0.1 --port 8000 --no-access-log
# In another shell:
python scripts/smoke_local.py
python -m scripts.demo_backend
python -m scripts.benchmark_routes --provider recorded
python -m scripts.replay_benchmark
python scripts/export_api.py
python -m pytest -q
python -m ruff check .
```

The recorded benchmark supports only its documented India Gate/CP fixture; unsupported pairs
remain unavailable. --provider osrm --live explicitly makes six external routing requests with
rate limits; pollution still comes from actual saved provider data. Do not refresh unnecessarily.
The demo is isolated TestClient integration with ephemeral signed test JWTs, actual recorded
road geometry and available saved pollution, two departures, deterministic grounded explanation,
one clearly synthetic wearable message, consent revocation and test-only synthetic daily alert.
It sends no notifications. It does not bypass production Cognito or claim Noise watch support.

```sh
docker build -t ecoroute-api .
docker run --rm -p 8000:8000 --env-file .env ecoroute-api
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/wearables/latest
# Last request must return401 without a bearer token.
```

Import examples/*.postman_*.json; populate only your local environment. Never commit tokens.
Windows laptop has no Docker engine; container validation is performed separately in CI.

## Validation results

Local full suite: **164 passed, 1 skipped, 3 upstream deprecation warnings**. The skip is the
Docker ML container test; no local Docker success is implied. Ruff, pip dependency compatibility,
health/docs/auth smoke, API export, Linux Lambda packaging (183.1 MiB), default CDK synth and
optional IoT/environment-workflow synth passed. Structural review passed for each active
assembly. Contract tests cover all protected endpoints' authentication/scope failures, request
validation/privacy, representative route/explanation response JSON Schemas, owner isolation,
missing pollution, consent revocation and safe cloud action guards. Existing tests cover
provider outages, JWT claims, grounded output, notification rate limits and workflow failures.
Tracked-file secret heuristic is limited; no vulnerability database scan or live penetration
test was performed. CI additionally builds API/ML Docker images, tests container execution,
checks exported-contract drift and Linux-native Lambda imports. Inspect the actual Actions run
before claiming those checks passed on a particular commit.

Saved live benchmark replay: 12 routes validated, 0 content hashes (created before hash support).
New recorded benchmark: 2 supported cases, 4 explicitly unavailable; replay verified 4 routes and
5 Parquet content hashes. No external request is made by replay, and it cannot prove a provider
will return identical geometry/forecasts later. Initial test failures were corrected: configuration
test now explicitly supplies missing prerequisites; data dependencies honor selected demo data;
local CDK/test runs execute sequentially after a concurrent Node-process failure.

## Truthful feature status

No deployed AWS resources. Core/Data/ML and optional IoT/workflow templates reuse existing
API Gateway, Cognito, Lambda, DynamoDB, S3, SQS/DLQ, Scheduler, CloudWatch and role definitions.
Location/Bedrock/SNS adapters are integrated but not verified live. Alarms and IAM structural
checks are not evidence of deployed delivery, authorization or operational monitoring.
ML preparation examined389 actual records:5 measuredPM2.5 records,1 station,0 eligible hourly
samples. No training, model, MAE/RMSE/bias, persistence comparison or SageMaker logs exist.
Noise ColorFit Pro3 Alpha / NoiseFit Assist has no verified supported bridge; simulation only.
Bedrock deterministic fallback is tested; real Converse permissions/model access remain unknown.
SMS is disabled, requires opt-in and verified destination; an SNS MessageId proves acceptance,
not delivery. No SMS has been sent. School forecasts are advisories, never official closures.

## Credentials and AWS approval boundary

User deferred setup. Missing/unverified configuration names: Cognito pool/client/domain/callback,
CDK bootstrap and scoped deploy permissions; service quotas; deployed table/bucket/queue/role
identifiers; external-provider Secrets Manager ARN; Bedrock model/access; SNS verified destination,
SMS sandbox/India DLT IDs; IoT bridge/certificate paths; ML execution role/image/model artifacts.
AWS_PROFILE=dev-admin (IAM devesh_eco), ap-south-1 and expected account are selected locally;
no authenticated AWS verification was performed in Phase7. See CREDENTIALS_CHECKLIST.md and
linked service runbooks for exact creation, IAM, secure storage and verification instructions.
Never paste secrets into chat. Use temporary non-root CLI credentials and ignored .env or
Secrets Manager. Local /ready is public; deployed API Gateway requires read scope for it.

## Cost proposal — review before deployment

No money was spent on AWS in this phase. Proposed small-demo envelope: US$5–20/month,
not a price quote or guarantee. Assumes at most 10,000HTTP calls/month, 100 bounded route comparisons,
hourly collection only after explicit enablement, <1 GB S3, low DynamoDB utilization,
bounded logs, no NAT/Fargate/real-time SageMaker endpoint, SMS and Bedrock disabled initially.
Secrets Manager and storage incur charges even while idle. SageMaker, SMS, model tokens,
Location request types, logging and optional workflow executions require separate estimates.
Credits eligibility, expiry, account Free Tier type and regional availability must be checked;
US$100 credits are not a spending target or assurance every service is covered.

Use current [AWS Pricing Calculator](https://calculator.aws/) and
[Location pricing](https://aws.amazon.com/location/pricing/),
[Bedrock pricing](https://aws.amazon.com/bedrock/pricing/),
[SNS pricing](https://aws.amazon.com/sns/pricing/),
[SageMaker pricing](https://aws.amazon.com/sagemaker-ai/pricing/).
Budget proposal: US$10 monthly total cost; actual alerts 50%,80%,100% and forecast 100%,
confirmed email/SNS subscriber; optional second US$5 AI/SMS budget. Budget evaluation is delayed
and **does not hard-cap costs**. No budget was created. Use existing BUDGET_NAME,
MONTHLY_BUDGET_USD and BUDGET_ALERT_EMAIL placeholders; opt-in recipient configuration required.
Schedules remain disabled; concurrency, provider rate limits and TTL/lifecycle controls reduce
usage but are not financial caps.

```powershell
npm ci --ignore-scripts
python scripts/build_lambda.py
npx cdk synth --no-lookups
python scripts/security_review.py
python scripts/manage_cloud.py plan
# Only AFTER deployment approval and reviewing exact synthesized resources/costs:
python scripts/manage_cloud.py deploy --apply --accept-estimated-charges
```

Deploy defaults exclude optional IoT/Location/workflows. Configure approved CDK contexts and
callback/model/provider references before deploying selected integrations. Do not infer service
availability from offline synth. No deploy command above was executed with --apply.

## Cleanup

Stop schedules, executions, training jobs and notifications first. Snapshot resource inventory.
After deliberate teardown authorization, one command removes the selected stacks:

```powershell
python scripts/manage_cloud.py teardown --apply --confirm-retaining-teardown
# Add --iot only if optional IoT stack was deployed.
```

**RETAIN is intentional:** protected DynamoDB tables, S3 data, Cognito and bootstrap assets can
remain billable. This is stack teardown, not irreversible data purge or a guarantee of zero costs.
Inventory is written to ignored work/teardown-resource-inventory.json. Review retained resources
in their AWS consoles; permanently delete only after explicit data-loss approval and backups.
Confirm no remaining queues, schedules, endpoint/training jobs, secrets, logs or device certificates;
revoke certificates/destination subscriptions and inspect Billing afterward. There is no deployed
infrastructure to tear down now.
