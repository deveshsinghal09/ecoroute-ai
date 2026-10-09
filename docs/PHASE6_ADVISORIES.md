# Phase 6: explanations, alerts, schools and automation

No frontend. No deployed AWS resources, model calls, notifications, OTPs or paid workflow runs.
User selected SMS and deferred configuration until later. All live switches remain false.

## Implemented contracts and scientific limits

`advisory/explanation.py` uses current Converse, a configurable model ID, approved sentence
catalog and strict JSON statement IDs. Only numerical stored route facts, categorical source
provenance and allowlisted ranking reasons enter the prompt. Place names, provider prose,
geometry, user IDs and wearable data are excluded. Every approved statement must be returned
exactly once; extra fields/claims are discarded. Only server-owned sentences are rendered.
Unavailable/denied/malformed/rate-limited Bedrock uses deterministic fallback. Scores and
percentages remain unchanged; supporting metrics, baseline references, uncertainty and usage
are returned. The prompt template is SYSTEM_PROMPT in explanation.py.

`advisory/alerts.py` initially supports PM2.5 only: WHO 2021 15 ug/m3 over 24 hours, with its
99th-percentile interpretation (3–4 exceedance days/year). This is not an instantaneous
threshold, AQI, Indian regulatory compliance test, diagnosis or guarantee of safety. Observed
windows require 24 distinct nonoverlapping hourly averages from one unambiguous sensor.
Forecast windows require 24 hourly samples from one retrieval vintage; their mean is explicitly
an approximation, preserving coarse-grid warnings. Missing/stale/flagged/incorrect-unit or
truncated data returns unavailable. Values are never invented or filled with zero.

Owned atomic alert claims retain seven days; the first evaluation for source/location/window/
guidance is retained, including its original evidence. Corrections do not silently rewrite it.
Listing is bounded and reports truncation. Notification claims prevent repeated publication;
one-hour owner cooldown is conservative, including ambiguous failures. Explicit preferences
must enable SMS, and only an operator-bound, allowlisted, dedicated single-recipient topic is
accepted. Sandbox verification, account spend limit and India registration IDs are checked.
MessageId means accepted, never delivered; delivered remains false without delivery evidence.
No phone numbers, raw exceptions or health details appear in responses/logs.

School configuration is saved by a successful genuine route comparison. Destination must
match school coordinates; forecast lattice must match those coordinates; departure must fall
inside configured increasing Asia/Kolkata commute times. Contemporary Delhi dates use fixed
UTC+05:30 without a Windows timezone-data dependency. Next-day forecast uses an explicit
UTC-hour-aligned 24h window beginning at the UTC hour preceding India midnight, not a local calendar-day mean. No
school closure is invented; official_closure_status is always not_provided.

## Optional workflow

Scheduler -> encrypted dedicated SQS jobs/DLQ -> gated dispatcher -> Standard Step Functions
-> ingestion/curation -> existing station ML inference -> daily risk -> alerts -> optional SMS.
Ingestion immediately performs existing idempotent curation so risk cannot race raw S3 events;
the existing S3/SQS cleaning worker can safely clean the same raw object. Daily templates get
fresh timestamps and deterministic owner/location/day run IDs. Trusted IAM operators enqueue
jobs; no REST endpoint permits a caller to choose an owner or start an execution.

One-hour station predictions are retained for inspection and route use. An unavailable model
stays unavailable. Daily risk uses appropriately timed provider forecasts; a one-hour model
is never extrapolated into next-day or 24-hour evidence. Failures persist failed stage, reach
the DLQ and fail the state machine. SDK exception text is suppressed; no task retry duplicates
paid calls. Dispatcher uses SQS partial failure responses. Lambda timeout failures can reach
the workflow DLQ even if the private manifest cannot be updated.

The construct is omitted by default; `-c enable_workflows=true` only synthesizes definitions.
Daily schedule is DISABLED; dispatcher ENABLE_ENVIRONMENT_WORKFLOW=false. Stage SMS/Bedrock
flags are explicitly false. API SMS enablement does not enable worker SMS. Four alarms cover
failed executions, stage errors, DLQ and EMF AlertCount. New alarms have no delivery recipient
until configured. Existing operational SNS topic is separate from personal SMS topics.
Restrict execution-history IAM access: AWS-managed history can outlast the application's
seven-day manifest TTL. No NAT gateway, idle ECS or real-time ML endpoint is introduced.

## Configure later, never send secrets in chat

| Configuration | Requirement / sensitivity / secure storage | Exact setup and verification / IAM | Charges |
|---|---|---|---|
| AWS_PROFILE, AWS_REGION, EXPECTED_AWS_ACCOUNT_ID | mandatory for local live AWS; identifiers non-secret; ignored .env; temporary credentials in CLI cache | IAM profile dev-admin / preferred Mumbai. `aws sts get-caller-identity --profile dev-admin --region ap-south-1`; compare expected account and reject root. Use temporary IAM/SSO credentials, no root keys | STS verification has no service usage charge |
| BEDROCK_MODEL_ID and exact regional ARN | mandatory only for live explanations; non-secret; ignored .env / reviewed CDK context | Bedrock Console -> Model catalog -> inspect model, regional on-demand support, Converse compatibility, provider terms and price. `aws bedrock list-foundation-models --by-inference-type ON_DEMAND --profile dev-admin --region ap-south-1`; `aws bedrock get-foundation-model-availability --model-id REVIEWED_MODEL_ID --profile dev-admin --region ap-south-1`. Read-only IAM ListFoundationModels/GetFoundationModel/GetFoundationModelAvailability; runtime bedrock:InvokeModel exact model ARN | token-billed invocation; first third-party call can initiate Marketplace subscription |
| Model access/quota | model-specific prerequisite; non-secret status | Bedrock provider access instructions; Anthropic may require first-time use-case form. Marketplace Subscribe/ViewSubscriptions/Unsubscribe belong only to enrollment operator when required, with product conditions where supported, not runtime. Console Service Quotas -> Amazon Bedrock -> selected model requests/tokens; read-only servicequotas:ListServiceQuotas. No AdministratorAccess required | review terms before enrollment; diagnostic never invokes a model |
| SNS_ALLOWED_TOPIC_ARNS and owned notification_config | required only for SMS; ARN non-secret, ownership mapping private; ignored .env JSON array / reviewed CDK context | SNS Console -> Topics -> create restricted Standard topic -> subscription SMS -> enter phone privately. Dedicated topic must have exactly one confirmed SMS subscriber. Operator binds exact ARN to Cognito sub in preference table. Runtime sns:Publish/ListSubscriptionsByTopic exact topic | subscription, publish, origination and verification may incur charges |
| Phone verification / origination | phone and OTP sensitive; never Git/chat | SNS -> Mobile -> Text messaging SMS -> Sandbox destination numbers -> add privately -> receive OTP -> verify in Console. Runtime GetSMSSandboxAccountStatus/ListSMSSandboxPhoneNumbers; Console checks opt-out/delivery setup separately | OTP may be billed; sandbox/production status is regional |
| SMS_MONTHLY_SPEND_LIMIT_USD, SMS_MAX_PRICE_USD | non-secret guard; defaults 1 USD/month and 0.05 USD maximum acceptable price/message | SNS SMS preferences -> Account spend limit at most reviewed app allowance. Runtime GetSMSAttributes; operator SetSMSAttributes only for changing preferences. Account read-only SMS APIs require Resource:* (no resource scoping), restricted by aws:RequestedRegion; no sns:* | accounting can lag and spending limits can overshoot; carrier/multipart/registration fees vary |
| SMS_SENDER_ID, SMS_ENTITY_ID, SMS_TEMPLATE_ID | mandatory for +91 in adapter; non-secret approved DLT IDs; ignored .env / Lambda env | AWS End User Messaging SMS -> Registrations -> India sender ID. Complete telecom DLT entity/header/template and telemarketer chain registration, then AWS approval. Register the exact fixed message below; configure SenderID/EntityId/TemplateId attributes | registration/carrier fees may apply; approval may block a short hackathon |
| WORKFLOW_STATE_MACHINE_ARN, jobs queue and trusted owner template | mandatory only for workflow; ARN non-secret, owner sub private; actual deployed outputs only | After approved deployment configure template CONFIGURE_COGNITO_SUB. Operator sqs:SendMessage exact jobs queue or states:StartExecution exact machine. Dispatcher StartExecution exact machine; machine InvokeFunction exact stage worker and SendMessage exact DLQ | manual runs are paid too; disabled schedule does not authorize execution |
| Stage execution role | mandatory only for workflow; non-secret ARN | Lambda trust; scoped log writes, S3 raw/curated GetObject/PutObject, Dynamo Get/Put/Update/Query environment/alerts/preferences, optional InvokeFunction exact verified ML ARN, optional same SNS permissions. No Bedrock needed in worker | normal service usage; no training launched |
| Cognito IDs, tables/bucket, CDK bootstrap | inherited mandatory AWS deployment requirements; non-secret identifiers | Reuse Phases1–5 checklist. `aws cloudformation describe-stacks --stack-name CDKToolkit --profile dev-admin --region ap-south-1` only after account confirmation. IAM deployment permissions remain separate from execution roles | bootstrap/deploy requires separate approval |

Fixed ASCII SMS under 160 characters; register this exact DLT template:

`EcoRoute: a complete PM2.5 daily window exceeds WHO 2021 guidance. Check data confidence and official local advice. Not medical advice.`

Operator binding record: pk=Cognito sub, sk=notification_config#sms; JSON payload includes
id=sms, topic_arn and expires_at; top-level expires_at is numeric TTL. Operator PutItem is
restricted to the preference table. Local equivalent uses store.put_record with kind
notification_config, owned sub, identifier sms and seven-day TTL. PUT /alerts/preferences
with alerts_enabled=true/channel=sms supplies explicit opt-in; allowlist alone supplies none.
Phone stays in SNS, not source files. Disable preferences to revoke future notifications;
delete operator binding/subscription and disable flags to remove channel access.

Copy placeholder-only .env.example to ignored .env for local settings. Never edit committed
code for secrets. AWS runtime uses execution roles; external provider secrets remain Secrets
Manager references from earlier phases. Bedrock/SNS need no provider API key. No authenticated
AWS call was attempted in Phase6, respecting deferred setup. Model/region availability, access,
quotas, bootstrap, destination registration and permissions remain unverified. SDK operations
were checked offline against pinned boto3/botocore 1.43.109. CDK supports exact regional model
ARN only; cross-region inference profiles need separate residency/IAM review.

## Costs and approval

Current AWS service usage: none. Proposed incremental Phase6 allowance: **5 USD/month**, with
SMS at most 1 USD and Bedrock at most 1 USD, pending user approval and regional pricing review.
Budget alerts do not hard-cap costs; credits do not prove Marketplace/tax/telecom eligibility.

- Bedrock default 20/day and 5/hour; output capped at 256 tokens; no retries/provisioned throughput.
  Illustrative 600 calls/month * 4,000 input/256 output tokens = 2.4M input + 0.1536M output.
  Multiply by the selected model's current regional prices. No model or Mumbai price is assumed
  while selection is undecided. These are planning estimates, not measured tokens.
- One location/day: about 150 successful task transitions/month plus queues/dispatch/logging.
  At the published US East example of 0.025 USD/1,000 Standard transitions, about 0.00375 USD
  before free-tier eligibility; Mumbai needs calculator confirmation. Conservative planned
  compute: 5 tasks * 180s * 0.5GB * 30 days = 13,500 GB-seconds, plus invocations. Most stages
  should finish much sooner. This is a workload estimate, not an account hard cap.
- Four metric alarms, logs and inherited S3/Dynamo/SQS/API usage may dominate a tiny demo.
  Reserve roughly 1–5 USD/month for small Phase6 usage, subject to actual regional calculator
  quote. Base infrastructure/training are separate. SMS depends on country/carrier/segments/
  origination; verify India price and DLT fees before enabling. No per-SMS rate is invented.
- Stop new work by disabling schedule/dispatcher/SMS/Bedrock flags. Review active executions,
  queue/DLQ and retained data. Purges, stopping runs and deleting retained resources require
  deliberate operator action; RETAIN does not mean zero storage charges.

## Offline verification and REST examples

```powershell
.\.venv\Scripts\python.exe scripts/check_advisory.py
.\.venv\Scripts\python.exe -m pytest tests/test_advisory.py tests/test_environment_workflow_infra.py -q
.\.venv\Scripts\python.exe scripts/smoke_local.py
$env:NODE_OPTIONS='--max-old-space-size=512'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe scripts/build_lambda.py
$env:PATH=(Resolve-Path .venv/Scripts).Path+';'+$env:PATH
npx cdk synth --no-lookups -c enable_workflows=true
```

Use a privately obtained Cognito access token with read/write scope, never Git/chat.
POST /ai/explain-route: {"route_ids":["OWNED_32_HEX_ROUTE_ID"]}.
POST /alerts/evaluate: {"source":"open_meteo","location_id":"cams_global:28.8000:77.2000",
"end_at":"FUTURE_AWARE_UTC_HOUR","notify":false}; requires real fresh complete data.
GET /alerts and /workflows/status expose only authenticated-owner records.
POST /schools/compare-routes: school_id/name/position/forecast_location_id, commute_start/end,
and nested existing CompareRequest as route; destination must equal position and
consent_to_store=true. GET /schools/forecast?school_id=OWNED_ID gives confidence and gaps.
Complete executable JSON schemas are in /docs and /openapi.json.

## Official references checked 2026-10-10

[Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html),
[API compatibility](https://docs.aws.amazon.com/bedrock/latest/userguide/models-api-compatibility.html),
[model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html),
[regional catalog](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html),
[WHO guidance](https://www.who.int/publications/i/item/9789240034228),
[WHO table](https://cdn.who.int/media/docs/default-source/who-compendium-on-health-and-environment/who_compendium_chapter2.pdf),
[SNS sandbox](https://docs.aws.amazon.com/sns/latest/dg/sns-sms-sandbox.html),
[India registration](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-sms-senderid-india-support.html),
[India template IDs](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-sms-senderid-india-specify-ids.html),
[Publish response](https://docs.aws.amazon.com/sns/latest/api/API_Publish.html),
[Bedrock pricing](https://aws.amazon.com/bedrock/pricing/),
[Step Functions pricing](https://aws.amazon.com/step-functions/pricing/),
[SMS pricing](https://aws.amazon.com/sns/sms-pricing/).
