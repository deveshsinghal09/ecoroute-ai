# AWS service decisions and IAM boundaries

## Journey review interface — 12 October 2026

Journeys reuses the existing route comparison in browser memory. Opening the tab, selecting an
alternative or viewing its summary invokes no additional AWS service or paid provider request.
Only explicitly comparing or explaining continues to use the existing configured backend.
No new resources or cost assumptions.


## Air-quality interface checks — 12 October 2026

No new AWS resources. Guest route consistency checks run in the browser. Collected dataset reports
continue using Cognito -> API Gateway -> API Lambda -> DynamoDB environmental metadata. Source data
and AWS authorization remain unchanged; a successful metadata query is not proof of route coverage.


Amplify route-contrast build verified publicly. Fresh compare returned429 at the daily allowance;
limits unchanged. Latest UI commit974f7a4 passed both GitHub CI jobs.


## Readability publication - 2026-10-12

Frontend route colors and sidebar contrast published via Amplify-connected main branch; no
backend deployment or new resources. CI container ownership repair uses GitHub runner Docker.


## Chrome renderer follow-up - 2026-10-12

Frontend-only asynchronous renderer fix published through Amplify main branch. No AWS resource
or IAM change; user Chrome graphics acceleration requires a local setting/relaunch.


## Map rendering repair - 2026-10-12

Frontend-only Google Maps change: no AWS resources, permissions, schedules or Lambda updates.
Amplify publication and live Google 2D/3D verified on public site for commit ee09af3.
CLI build-status read denied; deployed assets and actual browser renderer/tilt verified instead.


## Current-hour coverage deployment - 2026-10-11

EcoRouteCore UPDATE_COMPLETE: six Lambda assets updated using existing shared
package; no resources, IAM, schedules or usage allowances added. API Gateway live
Mumbai Drive comparison returned100% PM2.5 coverage for both candidates using
actual Google routes and Open-Meteo model data. No SageMaker job launched.


## Data quality fix - 2026-10-11

Existing environmental table and API role Query grant were reviewed against deployed Core and
CDKToolkit templates. IAM boundary allows Query on EcoRouteData tables in Mumbai. The failure
was a rejected empty sort-key value, reproduced against real DynamoDB. No new service, policy,
scheduled collection or additional recurring service charge; only the existing Lambda code
asset is updated. Real CLI reads returned two cleaned reports (192 and 288 records).
AWS key constraints: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html



Current explanation model: gemini-3.5-flash-lite (verified live through the deployed AWS API).
Secrets Manager JSON accepts api_key, GEMINI_API_KEY or gemini_api_key (exactly one), or plaintext.
Signature metadata is discarded; only approved statement IDs are accepted. The cloud Gemini
allowance is 100/hour AND 100/day globally. Google project/model quotas remain independent.
See PROJECT_STATE.md for the live Mumbai forecast, exposure arithmetic and deployment evidence.


## Bounded request-time pollution and Insights - 2026-10-11

Reuse API Gateway/Lambda, DynamoDB atomic request counters and Secrets Manager Gemini reference.
No additional service, IAM permission, endpoint infrastructure, scheduler, SMS or training job.
Existing S3/SQS ingestion remains intact. Forecast gap filling uses public noncommercial OpenMeteo
API under its terms; cache public grid data in warm process only. Cloud route_air100/day30/hour;
Gemini100/hour AND100/day. Small additional Lambda/DynamoDB requests fit the existing bounded
serverless deployment; Google Routes/Gemini plan charges are external to AWS credits and AWS
Budgets. Explain makes another genuine routing request, using coordinates when already resolved.


## Selected-route frontend state - 2026-10-11

Only React sidebar state/presentation changed; existing API Gateway/Lambda/curated forecast route
response is reused. No AWS stack, IAM, schedule, SMS or training change. Local tests use recorded
road fixtures/artificial UI metrics, with no real provider invocation. Amplify source pushed;
new bundle and live route selection verified. Matching coarse forecasts are preserved rather than invented.


Final allowance release verified: Core UPDATE_COMPLETE, deployed100daily/100hourly, new Amplify
retry messages served and browser comparison returned2routes with full forecast coverage.


## Routing allowance runtime update - 2026-10-11

Existing Core Lambda code/environment and API Gateway exposed headers updated. DynamoDB now
atomically reserves both counters, preventing rejected hourly attempts from consuming daily slots.
Hourly cap100/daily cap100; daily allowance unchanged. Transactions use two bounded Update actions
and existing IAM; transactional write pricing applies. No new service, continuous workflow or
unbounded allowance. Google/ORS and Maps browser billing are independent; AWS Budgets is no cap.


## Outside-Delhi verification follow-up - 2026-10-11

User confirmed the deployed Drive comparison now works. Real Mumbai Gateway of India->Marine
Drive preview returned HTTP200/twoGoogle routes (6119m/1191s and4191m/1227s). PM2.5 coverage0,
exposure null/confidence unavailable, correctly reflecting missing collected Mumbai data. Routing
is not Delhi-restricted; pollution-aware ranking needs area/time-matched collection and refresh.
Safe frontend error-message changes are committed/pushed; latest public bundle inspection did
not yet contain them, so no Amplify deployment completion is claimed. No new AWS/IAM changes.


## Deployed routing investigation - 2026-10-11

Public API Gateway/Lambda and actual Amplify browser Drive compare returned valid Google routes
with full curated forecast coverage. Specific user503 remains unconfirmed; API/access log and
Amplify job reads denied. Frontend diagnostic messages improved locally with48tests/build pass;
no backend deployment/new service/continuous workflow/IAM change. Existing approved bounded
Google/API requests used; no SMS, model training or private wearable access.


## Verified environmental AWS chain - 2026-10-11

Existing Data notification alone updated/UPDATE_COMPLETE. Collector Lambda, private encrypted
S3 raw/curated, SQS, cleaner Lambda, DynamoDB metadata and CloudWatch now verified in natural
chain:192forward-forecast records/2partitions plus288modeled date-window records/3partitions.
API Gateway/Lambda routes read curated forecasts for real Google Drive/Walk and ORS Cycle.
No new service/schedule/SMS/training job. Bounded invocation/storage/provider usage falls under
prior approved serverless scope; credit eligibility still depends on account/provider terms.
Budgets are alerts, not spending caps. Temporary scoped diagnostic reads now effective.


## Collector result verification - 2026-10-11

Collector raw Open-Meteo save verified from Console result and CloudWatch. Downstream cleaning not verified: metadata empty, no Worker logs in queried window, diagnostic reads denied. No new resource/deployment or continuous workflow. See INGESTION_RESULT_CHECK.md.


## Activation walkthrough - 2026-10-11

Exact service setup order is in AWS_ROUTE_AIR_SETUP.md. IAM collector invocation is still denied;
existing S3/SQS/Worker/DynamoDB flow needs one-shot verification. No new service/deployment or
continuous workflow is enabled by the guide. Hosted Amplify origin is allowed; local cloud CORS is not.


## Verified Core update - 2026-10-11

Core UPDATE_COMPLETE, Data no changes. Live Google driving/walking and ORS cycling returned200
with real geometry and Open-Meteo weather; cycling elevation and driving traffic metadata verified.
PM2.5 coverage0/full exposure null: no pollution improvement claimed. Backend health/OpenAPI200,
private ML endpoints401 without token. Amplify200/served bundle contains route preferences and
actual local training evidence. No SageMaker job or endpoint. Optional ML role reuse/name changes
and bounded operator/workflow-boundary permission proposals remain defined, not deployed.
See latest PROJECT_STATE.md and LARGE_DATA_TRAINING.md for exact evidence/blockers.


## Route/ML integration update - 2026-10-11

Existing SageMaker role/ECR/S3 preparation reused; local real-data training completed, cloud job
NOT launched. Mumbai training quota=0, iam:GetRole denied, Docker engine unavailable. Exact steps
and official $0.121/h rate in LARGE_DATA_TRAINING.md;15min runtime arithmetic=$0.03025 plus startup,
storage, logs and taxes, not a hard cap. Route weather is opt-in,100/day30/hour/max3cells per
comparison, no schedule. Existing Core updates cover request-only traffic/weather/terrain scoring.
Google/ORS billing is separate from AWS credits. No SMS, hardware or Bedrock verification implied.


## Cognito registration and hosted Maps - 2026-10-11

Core update enables email-verified self-registration; hosted form verified, actual email delivery/login not tested. Amplify browser Maps key absent; Google Maps basemap not verified. Server route providers already passed actual requests.

## Provider secrets connected � 2026-10-11

Core updated with four exact secret references: OpenAQ collector; Google Routes/ORS/Gemini API. Driving/walking/cycling live previews200. OpenAQ ingest and Gemini generation remain untested; full route exposure unavailable pending data. See PROVIDER_ACTIVATION.md.

## Uniform API key secret format � 2026-10-11

Secrets Manager routing credentials can use Console key/value api_key JSON; legacy plaintext retained. Local code verified, Lambda update pending.

## Core live verification � 2026-10-11

Core now CREATE_COMPLETE with API/Cognito/Lambda/Scheduler/StepFunctions/SNS/SQS/CloudWatch resources. Data/ML/IoT reused. Health/auth-failure/CORS live tests passed; schedules disabled. Provider integrations/model/SMS/hardware not verified; CloudWatch log reads denied. Amplify separately user-created; see AMPLIFY_CONNECTION.md.

## Mapping cleanup correction — 2026-10-11

Core DELETE_FAILED on mapping deletion. Regional execution-role mapping lifecycle permission prepared, not installed. Data/ML/disabled IoT unchanged.

Latest: Core ROLLBACK_FAILED due mapping metadata-read denial. Prepared regional
lambda:GetEventSourceMapping Resource* permission; workflow project naming fixed. No live API.


Latest Core attempt passed stage tagging; access-log setup denied logs:CreateLogDelivery.
Prepared seven explicit regional account-level logging actions for CFN execution only;
not installed yet. This exception is documented in AWS_CONSOLE_BOOTSTRAP.md. No working API.


Latest: Cognito configuration progresses; Core stage creation fails apigateway:TagResource.
Prepared Mumbai stage-only compatibility permission; explicit documented HTTP actions were
already present. Not installed yet; no working API. See PROJECT_STATE.md for failed retries.


Latest follow-up: EcoRouteIoT CREATE_COMPLETE with explicit ecoroute_wearable_measurements
rule; deployed template confirms disabled. No hardware or MQTT event tested. Data/ML remain
deployed; Core/Hosting rolled back. Latest Cognito bootstrap policy correction not installed.


Latest deployment (2026-10-11): Data and ML preparation stacks CREATE_COMPLETE; bootstrap
UPDATE_COMPLETE. CloudFront creation blocked by account verification; Core rolling back after
Cognito MFA configuration permission denial. No working API/frontend URL or training job.
Current Console template fixes MFA permissions with project-tag constraints; see PROJECT_STATE.md.
IoT attempt failed on CreateTopicRule; explicit project RuleName added, disabled and not yet
verified by deployment. Failed stack resources are not counted as functioning services.


## Local Health Connect bridge — 2026-10-11

This phone-data integration introduces no AWS service, IAM grant, resource or paid workload.
Local FastAPI accesses the trusted LAN phone server; React receives owner-authorized summaries.
Existing AWS IoT/Cognito/S3/DynamoDB definitions are preserved but are not used by the new
read-only bridge. No health record is uploaded. An expiring local loopback pairing key handles
only these three read endpoints while Cognito is deferred. This LAN integration cannot run
inside Lambda/Fargate against the user's private phone IP; future cloud use needs a secure
outbound companion bridge and existing ownership/consent controls. No public tunnel is added.

Current setup (2026-10-11): user reports creating the USD50/month budget. No application service
or bootstrap was deployed by us. [Scoped Console bootstrap](AWS_CONSOLE_BOOTSTRAP.md) defines one
private asset S3 bucket/ECR repository, five CDK roles, six managed policies and SSM version.
No customer KMS key, paid training, endpoint, SMS or active schedule is included. App stack roles
receive a project/account/Mumbai workload boundary when its exact ARN is supplied. Execution
policy exceptions for generated IDs/global/OAC APIs are documented; no wildcard actions appear
in the new managed policies. Final offline checks/IAM simulations pass; current actual grants
still deny resource creation. Budget creation is user-confirmed, not CLI-verified.

Latest live assessment (2026-10-11): the attached diagnostic policy now enables metadata reads;
CDKToolkit and all five selected project stacks are absent. No project resource was deployed.
SageMaker ml.m5.large training quota is0; no job/endpoint/warm pool was launched. Budget reads
remain denied, and billing/credit gates are pending. Read-only verification incurs no compute
provisioning charge and does not grant workload/deployment permissions. Optional exact-budget
read policy and Console actions are in [AWS_READINESS_AND_GEMINI.md](AWS_READINESS_AND_GEMINI.md).

## Additional profiles — 2026-10-10

All requested services have existing integration code or new optional profiles; none was
provisioned in this update. New ComputeStack supports the same FastAPI backend on ECS/Fargate,
EC2, EKS with Pod Identity or existing-customer App Runner. Lightsail is an authenticated HTTPS
proxy to Core API Gateway, with no embedded AWS keys. HostingStack serves the existing build
via private S3/CloudFront OAC and optional existing-zone Route 53 aliases, or manual Amplify.
AnalyticsStack processes existing aggregate route reports using SQS/DLQ/Lambda into RDS or
Aurora with separate restricted writer secrets. IAM, region/engine/quota checks, deployment
boundaries, remaining operator steps and recurring cost estimates are documented in
[MULTISERVICE_INTEGRATION.md](MULTISERVICE_INTEGRATION.md). Lambda remains the default;
schedules, training and real notifications stay disabled. Earlier no-idle-compute decisions
below describe the default profile; optional paid alternatives do not supersede that default.

Frontend integration adds no AWS service/resource or hosting deployment. Existing HTTP API and
Lambda receive optional exact-origin CORS configuration through frontend_origins; existing Cognito
PKCE public-client flow is reused. No IAM credentials belong in the frontend. Account costs are
unchanged until an approved deployment/provider invocation; no cloud actions occurred here.

Phase7: no AWS service provisioned or called with authenticated credentials. Core/Data/ML and
optional IoT/Step Functions resources remain definitions. Offline synthesis/security checks verify
private S3, disabled schedules, absence of idle compute and scoped policies; they do not prove
account IAM grants, service availability, alarm delivery or resource creation. Live external
services actually used: Open-Meteo, OpenAQ and OSRM fallback (not Amazon Location).
ECR Public was subsequently used anonymously to pull Docker's official Python base images for
successful CI builds; no ECR repository or other resource was created in the user's AWS account.

DEMO_READINESS.md documents the US$5–20/month small-demo planning envelope, assumptions,
US$10 budget proposal and required separate ML/Bedrock/SMS estimates. No budget was created.
scripts/manage_cloud.py defaults to a no-network plan. Deployment is an explicit approved action;
retaining teardown inventories resources but leaves protected data/Cognito/bootstrap billable.
CloudWatch error/latency alarms remain synthesized and tested structurally, not exercised in AWS.

Phase7 optional assembly inventory (`enable_iot=true`, `enable_workflows=true`, no ML image):
7 DynamoDB tables,2 S3 buckets,6 SQS queues,8 Lambda functions (including the CDK S3 notification
helper),8 explicit log groups,14 CloudWatch alarms,2 disabled Scheduler schedules,1 Step Functions
state machine,1 disabled IoT TopicRule,1 HTTP API,1 Cognito pool/client/domain and1 operational
SNS topic. This is a **template count, not deployed resources**. The optional SageMaker training/
container worker requires a separately reviewed ML image; its workflow is covered by structural
tests, not included in this assembly. Secrets Manager credentials are references, not created
secret values. Bedrock/Location are permissioned API integrations rather than dedicated idle
compute resources. The optional operational SNS topic has no verified subscriber/delivery.

Phase5 meaningful additions: DynamoDB wearables table (on-demand, stream, TTL/throughput caps),
Core archive Lambda/failure queue/2 alarms, private S3 wearables/* lifecycle7d, optional IoT
Rule/validator/failure queue/2 alarms. Existing Cognito/API, bucket, journey and pollution services
are reused. Rule disabled; no certificate, Thing, Identity Pool, paid compute or deployment.
WEARABLES.md contains exact ownership/topic policy and separate API/validator/archive permissions.
ListStreams requires Resource* with regional condition; data reads/writes/stream ARNs and
Lambda invocation source are otherwise scoped. No health subscriptions or public exports.
Official Mumbai pricing: messages USD1.05/million, connected minutes USD0.092/million,
rules/actions each USD0.158/million. Three bridges/minutely <=5KB messages for30days estimates
USD0.189 IoT-only; other service charges excluded. Budget warnings never hard-cap charges.

Phase 4 uses SageMaker only for bounded, explicitly approved training and optional batch
transform; no always-on endpoint. A custom pinned container trains RF/HGB and exports trusted
model artifacts. S3 stores versioned datasets, training output and verified manifest registry.
Step Functions meaningfully validates inputs, waits for training and publishes verified outputs;
its weekly EventBridge schedule is disabled and guarded by explicit approval configuration.
An optional container Lambda performs on-demand inference for the lean API Lambda.
CloudWatch receives structured worker logs and failure alarms. No resources are deployed.

OpenAQ rotation follow-up: real local station discovery and5-observation ingestion succeeded
without authenticated AWS calls. The existing S3/DynamoDB adapters remain local-only; no
Secrets Manager secret, S3 object, training job or additional AWS charge was created by this check.

Separate execution roles scope S3 to datasets/*, models/training/* and models/registry/* as
needed; ECR pull to the exact repository; SageMaker jobs to ecoroute-*; PassRole to the exact
execution role with iam:PassedToService; invocation/start to exact function/workflow ARNs.
ECR GetAuthorizationToken requires Resource* and has a regional condition. Training trust is
restricted by source account/job ARN. ML_WORKFLOW.md contains the full service IAM mapping.

Verified public Mumbai offer: ml.m5.large Training and BatchTransform USD0.121/hour each
(2026-10-10 check). Fifteen minutes is USD0.03025 compute arithmetic, excluding other costs.
Actual account quota is unverified; documented default training quota is zero. Encryption,
private buckets, network-isolated training, disabled schedules, bounded concurrency/runtime,
hash/package/schema verification and lifecycle retention apply. Budgets alert, never hard-cap.

Core/Data/ML templates are **implemented and synthesized / not deployed**. Primary region ap-south-1; official documentation
and SDK checks are evidence of service support, not proof of account entitlement or quota sufficiency.
Runtime permissions below apply to separate roles and exact project ARNs. They are not one combined
developer policy. Account/region/resource placeholders must be resolved before deployment.

Phase 3 adds optional scoped Routes/Places calls to the API Lambda, owned route pointers/cache
in the existing route_metadata table, geometry in private routes/* objects and redacted aggregate
reports in reports/routes/*. API role has GetObject/PutObject on routes/*, PutObject on
reports/routes/* and UpdateItem on the environmental budget table. Location is disabled by
default; `-c enable_location=true` opts its two runtime IAM actions into local synthesis.
Existing CloudWatch Lambda/API error and latency alarms cover routing; no new paid resource
has been deployed. Selected developer identity is dev-admin / IAM user devesh_eco. STS passed,
Location and Lambda checks denied; this is not a verified deployment-ready account.

| Service and decision | Meaningful work and dependents | Minimum runtime permissions / resource scope | Cost and security implications |
|---|---|---|---|
| API Gateway HTTP API: core | HTTPS ingress for FastAPI; depends on Lambda/Cognito | JWT callers need scopes, not IAM keys. API service needs resource-policy lambda:InvokeFunction scoped by API execution ARN | Request billing; throttle, bounded bodies, access logs without tokens; no API keys as user auth |
| Lambda: core | API, ingestion and event handlers; depends on storage/queues | Separate execution roles; logs:CreateLogStream, logs:PutLogEvents on precreated log groups plus only downstream actions listed here | Requests and GB-seconds; cap concurrency/retries; no VPC initially |
| Location Routes V2: core real routing | Candidate paths consumed by API | geo-routes:CalculateRoutes on arn:aws:geo-routes:ap-south-1::provider/default | Per-request tier/features; no route calculator needed; never log precise trips; respect caching/attribution terms |
| Location Places V2: conditional geocoding | Resolves text origin/destination before routing | geo-places:Geocode on arn:aws:geo-places:ap-south-1::provider/default | IntendedUse=Storage for persisted coordinates; billed Storage-tier requests; coordinates avoid these calls; no legacy place index |
| S3: core | Raw/curated observations, model and forecast artifacts | Ingest s3:PutObject raw prefix; trainer s3:GetObject input and PutObject output; API GetObject forecast prefix; ListBucket only with required prefix condition | Storage, requests, egress/version retention; block public access, TLS, encryption; deletion role separate |
| DynamoDB: core | Latest cell/forecast index, jobs, user exposure metadata | dynamodb:GetItem, Query, PutItem, UpdateItem on selected tables/indexes; DeleteItem only deletion worker; no Scan | On-demand units + storage; conditional writes and owner isolation; TTL is not instant deletion |
| EventBridge Scheduler: core ingestion | Invokes collector; raw S3 events feed SQS | Scheduler execution role lambda:InvokeFunction on collector Lambda; trusted by scheduler.amazonaws.com with source restrictions | Invocation billing/free allowance depends on account; bounded schedule frequency; no custom event bus needed initially |
| SQS + DLQ: core ingestion | Buffer, retry isolation, dead-letter recovery for Lambda | Producer sqs:SendMessage; consumer ReceiveMessage, DeleteMessage, GetQueueAttributes on exact queue | Request billing (including polling/retries); SSE, bounded retries, poison-message quarantine |
| Cognito User Pools: core before public users | User identity for HTTP API JWT authorizer | JWT verification itself requires no Cognito IAM permission; runtime has no Admin* actions. User OAuth operations use user tokens | Tier/MAUs plus email/SMS costs; PKCE public client, scopes, no SMS MFA in initial demo |
| CloudWatch: core AWS operations | Handler logs, alarms consumed by operators | logs actions above; optional cloudwatch:PutMetricData uses Resource * with namespace condition | Logs/metrics/alarms can exceed compute bill; 7-day logs, no location/health payload logs |
| Secrets Manager: conditional core | Stores selected provider secret for ingestion | secretsmanager:GetSecretValue on exact secret; kms:Decrypt only if customer-managed KMS key chosen | Secret-month + API calls; cache secret briefly, never log value; local env before deployment |
| SNS: later notifications | Opt-in exposure alerts from worker; operational alarms | sns:Publish on exact topic; subscriptions managed separately; scoped service-principal topic policies | Requests and delivery, especially SMS; email-first operational alerts, consent and unsubscribe for users |
| Step Functions: later ML | Durable validate/train/evaluate/publish workflow | Caller states:StartExecution exact state machine; workflow lambda:InvokeFunction or sagemaker:CreateTrainingJob/DescribeTrainingJob/StopTrainingJob, restricted iam:PassRole; .sync integration may additionally need EventBridge rules | State transitions/Express compute; grant integration-specific permissions after ASL exists; avoid unnecessary orchestration |
| SageMaker AI: optional batch ML | Reproducible managed training/batch inference when local insufficient | Training role S3 input/output + ECR image reads/logs; launcher CreateTrainingJob, DescribeTrainingJob, StopTrainingJob and iam:PassRole only selected role to sagemaker.amazonaws.com; transform actions only if used | Instance-hours/storage; quotas may be zero; maximum job runtime; no standing endpoints/Studio domain |
| Bedrock: optional explanations | Explains existing scores, not forecasts | bedrock:InvokeModel on selected model/inference-profile resources; streaming permission only if used | Model token billing/access terms; exact model/region pending; omit health/location identifiers and avoid cross-region profiles without consent |
| IoT Core: optional compatible bridge | mTLS MQTT via disabled Rule to validator; physical Noise connector unverified | iot:Connect exact client/attached Thing; Publish exact owner/device topic only; Lambda permission exact rule ARN/account. No Subscribe/Receive | Connection/messages/rules billed; per-device keys stay on bridge, consent plus cert revocation; WEARABLES.md |
| ECS Fargate: deferred | Continuous/native-heavy API if profiling justifies | Task role same downstream permissions as API; execution role logs + ECR pulls | vCPU/memory continuously allocated; networking/ALB/IPv4 extra; no public database |
| ECR: deferred except CDK bootstrap asset repository | Container images for Fargate or future Lambda/ML containers | Pull: ecr:GetAuthorizationToken (*) and BatchGetImage/GetDownloadUrlForLayer/BatchCheckLayerAvailability on repo; push role separate | GB-month/storage scanning choices; immutable tags and lifecycle cleanup |
| RDS PostgreSQL/PostGIS: deferred | Complex spatial joins if measured need exists | App uses database role/grants; rds-db:connect only with IAM DB auth and exact dbuser ARN; no RDS control actions for API | Instance/storage/backup/networking; private subnets, secrets or IAM DB auth, migrations and pooling |
| IAM / Identity Center / STS: prerequisite | Individual temporary developer sessions and service roles | sts:GetCallerIdentity requires no explicit allow; assume only approved roles; role trust scoped to services/accounts | No IAM charge; no root development, no shared access keys, no AdministratorAccess request |
| CloudFormation / CDK / SSM: deployment prerequisite | Versioned infrastructure and bootstrap metadata | Diagnostic cloudformation:DescribeStacks, ssm:GetParameter on bootstrap path. Deployment permissions depend on reviewed template | CloudFormation resource costs, bootstrap S3/ECR assets persist; CDK is local tooling |
| AWS Budgets: prerequisite proposal | Spend visibility for account/project | budgets:ViewBudget to inspect; budgets:ModifyBudget for scoped budget creation/update; billing-console access separately | Notifications are not a hard cap; see COSTS_AND_BUDGET.md |

## Deployment role is distinct from runtime

No deployment policy has been installed. Bootstrap can create privileged roles; do not run
default bootstrap assuming it is harmless or use AdministratorAccess as its execution policy.
An account operator should review `cdk bootstrap --show-template`, supply a project-scoped
CloudFormation execution policy and a permissions boundary, and allow the developer to assume
only project deploy/file-publish/image-publish roles. Restrict iam:PassRole by exact role ARN
and iam:PassedToService. Scope create/update/delete/read actions to resource types actually
present in the future synthesized template; use tag/region conditions where supported.
No broad wildcard grant is implied by this action inventory. Some list/create actions require
Resource *; document each exception and restrict through supported conditions.

## Read-only diagnostic permissions

`ec2:DescribeRegions` and `servicequotas:ListServiceQuotas` need Resource *.
`cloudformation:DescribeStacks` can target `arn:aws:cloudformation:ap-south-1:ACCOUNT:stack/CDKToolkit/*`.
`ssm:GetParameter` targets `arn:aws:ssm:ap-south-1:ACCOUNT:parameter/cdk-bootstrap/hnb659fds/version`.
`budgets:ViewBudget` targets the selected budget ARN (global service; do not apply Mumbai-only
endpoint restrictions blindly). STS failure is not repaired by granting these permissions.
SCPs, permissions boundaries and session policies may still deny access.

## Quota gates

Location CalculateRoutes documented default 20 requests/s, adjustable. Start with at most 2 route
requests/s and bounded alternatives. HTTP API maximum integration timeout 30s and payload 10 MB;
Lambda synchronous payload is 6 MB, default regional concurrency often 1,000 but new accounts may
be lower. Lambda max duration 900s, zip uncompressed 250 MB; this is why ML training is separate.
DynamoDB item limit 400 KB; use S3 for series/geometry. Confirm account concurrency, Location rate,
queue throughput and selected SageMaker instance quota in Service Quotas before real use.
Model availability and quotas are model-specific for Bedrock and instance-specific for SageMaker.
Do not request quota increases or enable optional regions automatically.

## Implemented Phase 1/2 role boundaries

These exact action groups are generated in infra/stacks.py with per-resource ARNs:

- API: logs CreateLogStream/PutLogEvents; DynamoDB GetItem/PutItem for journeys/preferences/
  idempotency, GetItem alerts, DescribeTable for readiness, Query environmental metadata;
  S3 GetObject curated/* only. DynamoDB transactional writes use PutItem authorization.
- Collector: logs; S3 PutObject raw/*; DynamoDB GetItem/PutItem/UpdateItem environment table;
  optional GetSecretValue only the imported OpenAQ secret ARN; SendMessage to failure DLQ.
- Cleaner: logs; S3 GetObject raw/* and PutObject curated/*; DynamoDB PutItem environment;
  SQS ReceiveMessage/DeleteMessage/ChangeMessageVisibility/GetQueueAttributes/GetQueueUrl
  on the processing queue (CDK grant), no secret access.
- Scheduler: InvokeFunction collector only; source-account/default-schedule-group trust restriction.
- S3: queue resource policy permits SendMessage from the specific bucket. TLS enforced.
- Cognito authorizer: user-scoped access JWT, no runtime Admin* permissions or private client secret.

Data has 6 on-demand tables capped 10 read/10 write request units each (throttling safeguards,
not a billing cap),2 queues and1 bucket; ML has1 bucket. Core has 3 business Lambdas,1 HTTP API,
Cognito pool/public client/domain/resource-server scopes,4 log groups,6 alarms,1 SNS topic,
1 disabled schedule. Data additionally has CDK's S3-notification custom-resource helper function
and generated policies; its managed logging role is a documented deployment-only exception.
No paid ML/IoT workloads or Location calls have been enabled.

Account blockers: default root STS identity succeeded, but Lambda GetAccountSettings returned
SubscriptionRequiredException; EC2 DescribeRegions and CloudFormation DescribeStacks returned
OptInRequired. Quota listing alone does not resolve entitlement. Verify account activation and
actual Lambda concurrency before deployment (reserved API 3 + collector 1 + cleaner 2 needs enough
regional concurrency above AWS's required unreserved pool). Do not interpret root as service access.
# Phase 6 service additions — templates only, none deployed

| Service | Meaningful work / dependency / scoped IAM | Cost/security controls |
|---|---|---|
| Bedrock Converse | Explain stored route metrics by arranging approved statement IDs; API role InvokeModel exact regional foundation ARN | Disabled; configurable reviewed model; 20/day,5/hour,256 output tokens; no health/GPS/provider prose; deterministic fallback |
| SNS | Opt-in environmental SMS through operator-bound dedicated single-recipient topic; Publish/ListSubscriptionsByTopic exact ARN | Disabled; verified sandbox numbers, India DLT and account spend checks; no delivery claim from MessageId; account read-only APIs Resource:* restricted by region |
| Lambda | Reused API plus optional stage/dispatch workers; exact S3 prefixes and existing tables, optional verified ML ARN | On-demand, reserved concurrency, short bounds; no NAT/idle service; temporary execution roles |
| Step Functions | Optional ingestion/curation -> station prediction -> daily risk -> alert -> optional notification; InvokeFunction exact worker, SendMessage exact DLQ | Standard,12min timeout,no task retries; trusted operators only; no auto training or real-time endpoint |
| Scheduler/EventBridge | Optional daily forecast job into SQS; scoped SendMessage | DISABLED; configure trusted owner/template and approve costs before enablement |
| SQS | Encrypted bounded async jobs, partial failures and DLQ | Jobs1day,DLQ7days,2 receives; dispatcher gate false |
| DynamoDB/S3 | Reuse pollution datasets, private preferences/schools, seven-day owned alert/workflow state | Existing encryption/TTL/caps; atomic claims, bounded reads; retained data not zero-cost |
| CloudWatch | Failed runs, errors, DLQ and EMF AlertCount | One-week worker logs, no identities; four optional alarms, notification actions require configuration |

Incremental planning allowance5 USD/month, including SMS1 USD and Bedrock1 USD, is a proposal,
not approved spending or a verified Mumbai quote. Model/carrier/registration rates and credits
need review. Budgets and SNS accounting limits do not guarantee an instantaneous hard cap.
Current AWS usage in Phase6: none. See PHASE6_ADVISORIES.md for formulas and official sources.

Frontend cinematic revision: bundled artwork and browser rendering add no AWS services. No hosting
resources have been provisioned; eventual static-hosting storage/transfer charges need separate review.

## Google routing integration (2026-10-10)
See docs/GOOGLE_MAPS_SETUP.md (repository root) for separate server/browser keys, APIs, Cognito,
restricted secret IAM and verification. Google Routes/Places feed the existing exposure engine;
Journeys displays Maps JavaScript tiles and route overlays. Live provider verification is recorded below.
Google comparisons are request-only; saved route-ID workflows are unavailable for those results.
No AWS resources were deployed. Google charges are separate from AWS credits.

Custom 3D smartwatch preview: browser-only rendering, no new AWS service, resource, invocation,
notification or cloud cost. Real wearable integration remains subject to existing bridge setup.

## Public map and travel modes — 2026-10-10

Guest Google routing and optional ORS cycling are external provider integrations; AWS credits do not cover their billing. Existing Lambda/API Gateway runs scoring. CDK adds an opt-in public preview route while preserving JWT private routes, and scoped Secrets Manager references for each server key. No new resource was deployed or AWS API invoked in this change. Existing global provider budgets and Gateway throttles apply; browser map loads need Google quotas separately.

## Local live-provider verification — 2026-10-11

Configured Google server and ORS cycling keys were connected to existing FastAPI adapters.
Three bounded public-landmark HTTP comparisons succeeded: Google driving/walking and ORS cycling.
Google Places also resolved a Mumbai landmark; the browser drew three actual Google alternatives
with two pins without sign-in. Existing curated forecasts supplied exposure; no measured pollution
ingestion or model training occurred. No AWS action, deployment, SNS delivery or Bedrock invocation
was performed. This validates external-provider/local runtime integration, not deployed AWS services.
Google map loads, Routes/Places requests and any paid ORS usage bill separately from AWS credits.
Exact current provider/account invoices were not queried; existing budgets/quotas remain necessary.

## Local wearable adapter — 2026-10-11

Web Bluetooth consent/notifications and Android ADB/nRF inspection use local device/browser facilities.
They do not invoke AWS IoT Core, Lambda, Cognito, DynamoDB, S3 or SNS. No paid cloud service or role
was added/deployed. Existing protected GET /wearables/latest can populate the watch from approved
backend records when Cognito/device consent are configured; this change does not verify cloud ingestion.
Live Noise health data remains blocked by undocumented vendor packet semantics. Standard-sensor
tests are synthetic and cannot establish physical watch compatibility. See LIVE_WATCH_SETUP.md.

## Current AWS preparation — 2026-10-11

No AWS resource was provisioned in this update. Read-only account checks verified named IAM
identity and service metadata for many services; deployment/IAM/quota/ECR/CloudWatch checks have
specific denials recorded in [the current runbook](AWS_READINESS_AND_GEMINI.md). Project stack
existence is unverified where DescribeStacks is denied; CDKToolkit is confirmed missing. Three
existing S3 buckets were listed and were not repurposed or read.

SageMaker is retained by latest user instruction. ML now includes an immutable retained ECR
repository, bounded image retention and least-privilege job execution role before an image is
supplied. No paid job/endpoint/domain exists from this work. Five local measured PM2.5 records
give zero eligible training samples. Lambda app default omits reservations to support quota10;
API/DDB/SQS controls remain, with no per-function concurrency ceiling. The active offline
assembly includes Data, ML, Core, IoT and private S3/CloudFront Hosting; optional ECS/EKS/EC2/
Lightsail/AppRunner/RDS/Aurora/Amplify profiles are not running services.

Gemini replaces optional Bedrock explanations when explicitly configured; Gemini is a Google
service called server-side, not an AWS service and not a SageMaker substitute. Secrets Manager
reference, sanitized facts, approved text validation, request caps and fallback are integrated.
No key/model invocation was verified. Google guest Insights remains deterministic. IAM ECR token
retrieval requires Resource:* with a Mumbai condition; separate image access is repository-scoped.

## Route-control audit — 12 October 2026
No resources provisioned or AWS authenticated actions performed. One public API Gateway/Lambda route check returned 429 for the existing daily request allowance; no further mode/provider calls were attempted. Existing S3/DynamoDB forecast data and request-time Open-Meteo/weather adapters remain the source path; route weights affect deterministic ranking, not pollutant values. Local scoring and UI fixes require publication before they affect the deployed API. Existing cost limits were preserved.
- Deployment follow-up: existing EcoRouteCore stack updated successfully; six Lambda code assets only. API health/access protection/CORS verified. No new services, IAM changes or additional recurring service classes introduced.
