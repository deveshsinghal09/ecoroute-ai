# EcoRoute AWS Console and PowerShell setup

Reviewed 2026-10-10 against the current repository and official AWS documentation.
These are instructions to run later, not a record of cloud actions performed. No AWS
authentication, bootstrap, deployment, training, SMS or account-plan change was performed
while preparing this guide. Previously recorded IAM denials are not repaired by this guide.

## 1. Confirm the credited account, plan and region

1. Sign in to the credited account's Console using the existing IAM identity
   `devesh_eco` or an authorized role. The selected CLI profile is `dev-admin`.
   Do not use the old root-authenticated `hackathon` profile.
2. Open **Billing and Cost Management → Credits**. Check actual balance, expiration
   and eligible services. Keep billing details private; do not send credentials in chat.
3. Check the account-plan information in Billing. Having $100 credits is different
   from having access to every AWS service. The newer Free account plan restricts
   services/features; a Paid plan can charge beyond eligible credits.
4. Select **Asia Pacific (Mumbai), ap-south-1** for the backend. ACM certificates for
   an optional CloudFront custom domain must instead be in `us-east-1`.

Do not upgrade the account or create an AWS Organization just to enable SSO without
checking the consequences. AWS documents that joining/creating Organizations can upgrade
a Free plan and expire its Free Tier credits. An existing authorized IAM login avoids
requiring that change. See [AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
and [Free Tier FAQ](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-FAQ.html).

## 2. Secure the development identity

Console: **IAM → Users → devesh_eco → Security credentials → Assign MFA device**.
Configure MFA privately. Under **Permissions**, an authorized IAM operator can attach
the AWS-managed `SignInLocalDevelopmentAccess` policy if using `aws login`.
This policy enables temporary development login; it does NOT grant application or
deployment permissions. No new root key or application access key is required.

Each friend should eventually have an individual IAM/SSO session, even on this shared
laptop. Git commit authorship does not change the AWS identity or permissions.

Windows PowerShell:

```powershell
aws --version
aws configure list-profiles
aws configure set region ap-south-1 --profile dev-admin
aws login --profile dev-admin
aws sts get-caller-identity --profile dev-admin --region ap-south-1
```

`aws login` requires AWS CLI v2.32.0 or newer. In its browser flow select the credited
account and IAM identity, not root. If the existing profile is an IAM Identity Center
profile, use `aws sso login --profile dev-admin` instead. Configure an existing SSO
assignment with `aws configure sso --profile dev-admin`; its SSO home region can differ
from Mumbai. Do not replace a working profile blindly.

The CLI stores sensitive login caches under `%USERPROFILE%\.aws\login\cache`; SSO uses
its own AWS cache. Keep these files outside Git and restrict access to the Windows user.
[AWS credential provider documentation](https://docs.aws.amazon.com/sdkref/latest/guide/feature-login-credentials.html).

## 3. Prepare this repository and verify Python credentials

```powershell
Set-Location 'C:\Users\DELL\Documents\Codex\2026-10-08\act-as-a-senior-aws-solutions\outputs\ecoroute-ai'
if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
npm ci
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

For a profile created with `aws login`, add the CRT extra matching the repository's
locked Boto3 version. CLI login working alone does not prove Python authentication works:

```powershell
.\.venv\Scripts\python.exe -m pip install 'boto3[crt]==1.43.109'
.\.venv\Scripts\python.exe -c "import boto3; s=boto3.Session(profile_name='dev-admin',region_name='ap-south-1'); r=s.client('sts').get_caller_identity(); assert not r['Arn'].endswith(':root'); print('Python temporary-profile authentication verified')"
```

Boto3 login support requires 1.41.0+ and CRT; the checked-in lock has Boto3 1.43.109.
The extra command changes your local environment, not the dependency lock. SSO does not
require this login-provider extra. [Boto3 credentials](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html).

Set public configuration in the existing ignored `.env`, preserving its current values:

```dotenv
ECOROUTE_PROFILE=local
PROJECT_NAME=ecoroute-ai
AWS_PROFILE=dev-admin
AWS_REGION=ap-south-1
EXPECTED_AWS_REGION=ap-south-1
ECOROUTE_DEPLOY_REGION=ap-south-1
EXPECTED_AWS_ACCOUNT_ID=YOUR_ACTUAL_CREDITED_ACCOUNT_ID
MONTHLY_BUDGET_USD=20
BUDGET_NAME=EcoRoute-Gross-Usage
TARGET_CITY=Delhi
WEARABLE_MODEL=Noise ColorFit Pro3 Alpha
CORS_ORIGINS=["http://127.0.0.1:5173"]
ENABLE_BEDROCK=false
ENABLE_SMS=false
ENABLE_ENVIRONMENT_WORKFLOW=false
```

This is an example with identifiers to replace, not a file to copy over an existing `.env`.
Do not put AWS access keys in it. `ECOROUTE_PROFILE=local` keeps local storage selected;
individual live adapters still need their own enablement and permission checks.

## 4. Set spending alerts before provisioning

Console: **Billing and Cost Management → Budgets → Create budget → Customize → Cost
budget**. Create a monthly recurring **$20 gross-usage proposal**, with actual alerts
at 50%, 80%, 100% and forecast at 100%. Enter your alert email privately. Exclude credits
and refunds from the gross-usage view so credit consumption remains visible; optionally
add a separate net-payable budget. Use an account-wide alert to catch other-region spend.

IAM: budget operator needs `budgets:ModifyBudget`; verification needs
`budgets:ViewBudget` on the chosen budget. Billing Console access is separately controlled
and might need an account operator to enable IAM billing access. Application roles do
not need billing permissions. Basic monitoring does not create application compute;
review any Budget Actions/report charges before selecting them.

```powershell
aws budgets describe-budget --account-id YOUR_ACCOUNT_ID --budget-name EcoRoute-Gross-Usage --profile dev-admin
```

**Budget notifications are delayed alerts, not a hard spending cap.** Credit eligibility,
taxes, SMS and third-party Marketplace terms must be checked separately. The default small
serverless demo has a $5–20/month planning allowance before credits, not a price quote or
guaranteed maximum. Model calls, training, SMS, hosting and optional infrastructure add cost.
[Cost inclusion fields](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_budgets_CostTypes.html).

## 5. Separate diagnostic, deployment and runtime permissions

Console: an authorized operator opens **IAM → Policies → Create policy → JSON**, creates
the reviewed policies, then attaches the appropriate human policy under **Users →
devesh_eco → Add permissions**, or to the role the profile assumes. Do not attach
AdministratorAccess or every service's FullAccess policy.

| Identity/purpose | Permission boundary |
|---|---|
| Human diagnostic identity | `ec2:DescribeRegions`, `lambda:GetAccountSettings`, `servicequotas:ListServiceQuotas/GetServiceQuota`; bootstrap `cloudformation:DescribeStacks` on CDKToolkit and `ssm:GetParameter` on its version path; optional `budgets:ViewBudget` on this budget |
| Bootstrap operator, one-time | Create/update the reviewed CDKToolkit CloudFormation stack, its IAM roles/policies, asset S3/ECR and SSM version parameter; narrowly scoped `iam:PassRole` where needed. This is separate from daily application access |
| Human CDK deployer | `sts:AssumeRole` only the approved CDK deploy/file/image-publishing roles; required stack/asset/version reads. Trust policy and identity policy must both permit the role assumption |
| CloudFormation execution role | Create/update/delete/read actions for resource types in the selected synthesized templates, scoped to project resources/account/region and supported conditions; role creation/policy updates and `iam:PassRole` only intended workload roles/service principals |
| Lambda/container/ML/workflow roles | CDK-generated workload policies below, not developer credentials |

Some read/list/create APIs do not support resource-level scoping and require `Resource: "*"`.
Restrict these documented exceptions with supported conditions; they do not justify wildcard
actions. Do not apply a Mumbai-only condition indiscriminately to global IAM/Budgets/Route53.
**The repository defines workload IAM; a reviewed bootstrap/deployment policy has not been
installed or live-verified.** This remains a deployment prerequisite, not something login fixes.
Use the actual selected templates for policy review; a policy for Lambda is not sufficient
to deploy EKS, SQL or CloudFront as well. See [AWS_SERVICES.md](AWS_SERVICES.md).

For the first diagnostic step, create a customer-managed policy named
`EcoRouteDiagnostics` with the JSON below, replacing ACCOUNT_ID. Attach it to the
development identity. This deliberately does not permit provisioning or application
data reads. Console navigation can need additional scoped list/read permissions; do
not fix a Console navigation denial by granting service-wide full access.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ec2:DescribeRegions", "lambda:GetAccountSettings", "servicequotas:ListServiceQuotas", "servicequotas:GetServiceQuota"],
      "Resource": "*",
      "Condition": {"StringEquals": {"aws:RequestedRegion": "ap-south-1"}}
    },
    {
      "Effect": "Allow",
      "Action": "cloudformation:DescribeStacks",
      "Resource": "arn:aws:cloudformation:ap-south-1:ACCOUNT_ID:stack/CDKToolkit/*"
    },
    {
      "Effect": "Allow",
      "Action": "ssm:GetParameter",
      "Resource": "arn:aws:ssm:ap-south-1:ACCOUNT_ID:parameter/cdk-bootstrap/hnb659fds/version"
    },
    {
      "Effect": "Allow",
      "Action": "budgets:ViewBudget",
      "Resource": "arn:aws:budgets::ACCOUNT_ID:budget/EcoRoute-Gross-Usage"
    }
  ]
}
```

If using a custom bootstrap qualifier or budget name, adjust those two ARN paths.
GetCallerIdentity does not need an explicit IAM Allow. Creating/attaching the above policy
requires an already authorized IAM operator; it cannot grant permission to its own creator.

| Workload | Minimum relevant service actions, on its exact resources |
|---|---|
| API Gateway | Resource permission to invoke the API Lambda; Cognito JWT authorizer needs no user-pool Admin permissions |
| FastAPI Lambda | DynamoDB get/put/query/update/conditional/delete operations actually used by each table; S3 curated read, private route/report write and authorized wearable deletion; own log writes; optional Location, secret read, Bedrock model invoke, dedicated SNS publish and exact inference-function invoke |
| Collector | `s3:PutObject` raw prefix; environment-table GetItem/PutItem/UpdateItem; selected `secretsmanager:GetSecretValue`; own logs |
| Cleaner | ReceiveMessage/DeleteMessage/GetQueueAttributes on ingestion queue; raw GetObject, curated PutObject, environment PutItem; own logs |
| Scheduler | `lambda:InvokeFunction` on its collector/dispatcher only, trusted service `scheduler.amazonaws.com` with source restrictions |
| Step Functions | Invoke only workflow stages; failure DLQ SendMessage; ML .sync job actions and PassRole only the training role; integration-specific EventBridge rule actions |
| SageMaker training | S3 dataset-prefix GetObject/ListBucket, model-output PutObject; exact ECR pull actions and own training logs; trust `sagemaker.amazonaws.com` |
| IoT device | Connect exact client and Publish exact owner/device topic only; certificate/Thing binding and consent validated server-side |
| Wearable validator/archive | Exact wearable table/stream, encrypted private history prefix, failure queue and logs; IoT invokes only the exact rule-authorized Lambda |

Trust is distinct from permissions. API roles trust Lambda; Step Functions roles trust
`states.amazonaws.com`; task roles trust `ecs-tasks.amazonaws.com` when chosen. Secrets
Manager needs `kms:Decrypt` on the exact key only if using a customer-managed encryption key.
IAM itself has no standing usage charge; the resources it authorizes can charge.

## 6. Check region access and quotas

Console: **Service Quotas → AWS services**, select Mumbai and inspect Lambda, SageMaker,
API Gateway, Cognito, Bedrock and any selected optional service. Also check credit/plan
entitlement; an IAM Allow does not override account restrictions, boundaries or SCPs.

```powershell
.\.venv\Scripts\python.exe scripts/diagnose.py
.\.venv\Scripts\python.exe scripts/diagnose.py --aws --profile dev-admin --region ap-south-1
aws lambda get-account-settings --profile dev-admin --region ap-south-1
aws service-quotas list-service-quotas --service-code lambda --profile dev-admin --region ap-south-1
aws service-quotas list-service-quotas --service-code sagemaker --profile dev-admin --region ap-south-1
```

The diagnostic's default is offline; `--aws` makes read-only account checks. SDK endpoint
metadata is not proof of account entitlement. Lambda templates reserve concurrency for
several functions. AWS requires leaving 100 concurrency units unreserved, so a new account
with a low quota may need an increase or a reviewed template adjustment before deployment.
These are reserved, not paid provisioned, concurrency settings.
[Lambda concurrency](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html).
SageMaker `ml.m5.large` training quota must be at least 1 before an approved training job.

## 7. Bootstrap CDK once, after IAM and cost review

Console: **CloudFormation → Stacks → CDKToolkit**, in Mumbai. Reuse a suitable existing
bootstrap; inspect its execution role instead of creating another bootstrap blindly.

```powershell
aws cloudformation describe-stacks --stack-name CDKToolkit --profile dev-admin --region ap-south-1
$env:Path = "$PWD\.venv\Scripts;$env:Path"
.\node_modules\.bin\cdk.cmd bootstrap --show-template
```

An absent stack and AccessDenied are different outcomes. If absent, an authorized operator
first creates/reviews a scoped customer-managed CloudFormation execution policy in IAM.
After approval, substitute its actual ARN:

```powershell
.\node_modules\.bin\cdk.cmd bootstrap aws://YOUR_ACCOUNT_ID/ap-south-1 --profile dev-admin --cloudformation-execution-policies arn:aws:iam::YOUR_ACCOUNT_ID:policy/EcoRouteCfnExecution
```

**Do not run a bare default bootstrap**: its default execution policy is AdministratorAccess.
Use a reviewed permissions boundary as appropriate; a bootstrap boundary does not
automatically install a boundary on every workload role. Bootstrap creates IAM roles,
asset S3/ECR and an SSM version parameter. Stored assets can charge. No additional
cross-account trust is needed for these three GitHub contributors.
[CDK bootstrap options](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-bootstrap.html).

## 8. Configure provider secrets

### OpenAQ observations

Provider account → register/sign in → API keys → obtain a current key privately. Keep the
rotated key already configured if valid. Locally it is `OPENAQ_API_KEY` in ignored `.env`.
For AWS: **Secrets Manager → Store a new secret → Other type of secret → Key/value**,
key **api_key**, value your key; name `ecoroute/openaq`, Mumbai, AWS-managed encryption.
Do not paste it into commands/chat. Copy only the secret ARN.

Runtime expects JSON `{"api_key":"PRIVATE_VALUE"}`, not a plain string. Set
`OPENAQ_SECRET_ARN` for a local AWS-profile collector and the CDK **provider_secret_arn**
context for the deployed collector. Context contains the ARN only. Human verification
uses `secretsmanager:DescribeSecret`; collector uses GetSecretValue only that ARN:

```powershell
aws secretsmanager describe-secret --secret-id ecoroute/openaq --profile dev-admin --region ap-south-1 --query '{Name:Name,ARN:ARN}'
.\.venv\Scripts\python.exe scripts/ingest_air.py --source openaq --stations --max-pages 1
```

The provider test uses one request and the script's active storage profile: keep
`ECOROUTE_PROFILE=local` for a local-only check. DescribeSecret verifies metadata, not
the key; ingestion verifies provider authentication. Secrets Manager storage/reads charge;
provider plan/license/rate limits also apply. [Provider details](INGESTION.md).

### Open-Meteo forecasts

Eligible noncommercial use needs no key. Commercial/customer plans need a key and customer
endpoint; local `OPEN_METEO_API_KEY`, AWS `OPEN_METEO_SECRET_ARN`, same JSON api_key shape.
The current CDK collector directly wires OpenAQ only; a commercial Open-Meteo secret also
needs a reviewed environment + exact GetSecretValue grant. Never label these forecasts
as measured roadside data.

### Optional Google map/routing integration

This is Google Cloud configuration, not an AWS credential. Follow [GOOGLE_MAPS_SETUP.md](GOOGLE_MAPS_SETUP.md):
use separately restricted server Routes API and public browser Maps JavaScript keys.
`GOOGLE_ROUTES_SECRET_ARN` references a Secrets Manager **plain-string** secret in the
current routing adapter, unlike the OpenAQ JSON secret; wire CDK `google_routes_secret_arn`.
Only the browser-restricted key is `VITE_GOOGLE_MAPS_API_KEY`. Enabling this context selects
Google routing instead of the default AWS routing provider. Google billing is separate
and is not paid by AWS credits. No Gemini key is needed for the Bedrock path.

## 9. Enable Amazon Location Routes/Places V2

No separate AWS Location API key, legacy route calculator or legacy place index is needed
for this backend's boto3/SigV4 access. For local requests, attach this scoped policy to
the development identity using **IAM → Policies → Create policy → JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": "geo-routes:CalculateRoutes", "Resource": "arn:aws:geo-routes:ap-south-1::provider/default"},
    {"Effect": "Allow", "Action": "geo-places:Geocode", "Resource": "arn:aws:geo-places:ap-south-1::provider/default"}
  ]
}
```

Configure local `ENABLE_AWS_LOCATION=true`, `ROUTING_PROVIDER=aws`. The approved AWS
deployment uses `--location`, which grants the corresponding API execution-role permissions.
Use the exact billed route/geocoding tests and India examples in [ROUTING.md](ROUTING.md)
only after request-cost review. No free verification invocation is implied by policy attachment.
[Routes IAM resource format](https://docs.aws.amazon.com/service-authorization/latest/reference/list_geo-routes.html).

## 10. Synthesize, review, then deploy the default core

Keep `config/deployment.example.json` with runtime=lambda, hosting=none, analytics=none.
CDK creates Core/Data/ML base resources and service roles. Do not create duplicate Lambda,
API Gateway, S3, DynamoDB, Cognito, queues or CloudWatch resources manually.

```powershell
.\.venv\Scripts\python.exe scripts/build_lambda.py
$env:AWS_PROFILE='dev-admin'
$env:ECOROUTE_DEPLOY_REGION='ap-south-1'
$env:EXPECTED_AWS_ACCOUNT_ID='YOUR_ACTUAL_ACCOUNT_ID'
$env:Path = "$PWD\.venv\Scripts;$env:Path"
npm run synth
.\.venv\Scripts\python.exe scripts/manage_cloud.py plan --location
```

Use existing `cdk.json` **context** entries to supply non-secret configuration: preserve
existing entries and add `provider_secret_arn`, `bedrock_model_arn`, `sms_topic_arns`
(JSON array), `callback_urls` (JSON array), `frontend_origins` (JSON array),
`enable_workflows` or `ingestion_interval_minutes` only when relevant. These are actual
CDK context names, not runtime environment names. Do not store key values there. ARNs
can instead be supplied via CDK command-line context during a reviewed deployment.
The wrapper accepts `--location`, `--iot` and `--deployment-config`, not arbitrary
Bedrock/provider context flags. Use the same selections for synth, deploy and teardown.

Only after reviewing resources, IAM, quotas and charges and obtaining deployment approval:

```powershell
.\.venv\Scripts\python.exe scripts/manage_cloud.py deploy --profile dev-admin --region ap-south-1 --expected-account-id YOUR_ACCOUNT_ID --location --apply --accept-estimated-charges
```

Read actual `work/deployed-outputs.json` after a successful verified deployment. Required
local cloud identifiers come from outputs, not guessed names:

| Output/configuration | Where it is used |
|---|---|
| ApiUrl | Frontend VITE_API_BASE_URL; no /api/v1 suffix |
| UserPoolId, ClientId | COGNITO_USER_POOL_ID/COGNITO_CLIENT_ID; public client ID in browser |
| DataBucket | S3_DATA_BUCKET |
| journeys/preferences/route_metadata/idempotency/alerts/environment/wearables table outputs | JOURNEYS_TABLE, PREFERENCES_TABLE, ROUTE_METADATA_TABLE, IDEMPOTENCY_TABLE, ALERTS_TABLE, ENVIRONMENT_TABLE, WEARABLES_TABLE |
| QueueUrl | SQS_INGEST_QUEUE_URL |
| MlBucket | ML dataset/job configuration; model workflow outputs exist only with a reviewed ML image |
| OperationalAlertsTopic | Operator alarm subscription, distinct from personal SMS topics |

Lambda environment settings/role grants are populated by CDK. A local `.env` edit does
not update deployed Lambda. CloudFormation CREATE_COMPLETE/UPDATE_COMPLETE and live smoke
checks are required before reporting a working backend URL.

## 11. Configure Cognito and connect the frontend

Console: **Cognito → User pools → deployed EcoRoute pool → App clients/App integration**.
Reuse the generated public client, **no client secret**, authorization code + PKCE.
Use scopes `openid`, `ecoroute/read`, `ecoroute/write`. Inspect the generated hosted domain.
Create/invite a test user under **Users**; enable software-token MFA for that user privately.
Self-signup is disabled. Operator user administration needs `cognito-idp:AdminCreateUser`
and any chosen follow-up admin actions on this exact pool; JWT verification needs none.

Set CDK `callback_urls` to the exact frontend callback URI and `frontend_origins` to its
exact HTTPS origin without path/trailing slash, then redeploy only after approval.
OAuth is initially disabled if callback_urls was not supplied. AWS permits localhost
HTTP callbacks for development, but this repository's deployed CORS accepts HTTPS origins
only; do not expect its AWS API to allow localhost HTTP merely by changing VITE settings.
For local UI/backend use the documented localhost CORS; for the cloud demo use a verified
HTTPS hosted frontend and matching callback. No wildcard production CORS.

Populate ignored `frontend/.env.local` (local) or `.env.production` (hosting):

```dotenv
VITE_API_BASE_URL=YOUR_VERIFIED_API_ORIGIN
VITE_COGNITO_DOMAIN=YOUR_FULL_HTTPS_COGNITO_DOMAIN
VITE_COGNITO_CLIENT_ID=YOUR_PUBLIC_CLIENT_ID
VITE_COGNITO_REDIRECT_URI=YOUR_EXACT_REGISTERED_CALLBACK
```

These are public identifiers. Browser tokens stay private/in memory; never put AWS keys,
OpenAQ keys, provider tokens or private device keys in VITE variables. Verify missing-token
401, correct scopes, cross-user isolation and matching CORS before using wearable data.
[Frontend instructions](../frontend/README.md).

## 12. Configure Bedrock explanations

Console: **Amazon Bedrock → Model catalog**, Mumbai. Choose a model that supports regional
on-demand **Converse**. Record its model ID and exact
`arn:aws:bedrock:ap-south-1::foundation-model/MODEL_ID`.
This CDK path does not accept cross-region inference-profile ARNs without a separate review.

```powershell
aws bedrock list-foundation-models --by-inference-type ON_DEMAND --profile dev-admin --region ap-south-1
aws bedrock get-foundation-model-availability --model-id YOUR_SELECTED_MODEL_ID --profile dev-admin --region ap-south-1
```

Human discovery uses ListFoundationModels/GetFoundationModelAvailability (and GetFoundationModel
if inspecting details). Runtime needs **bedrock:InvokeModel** on that exact model, not a
Bedrock API key. Many models now have automatic access; third-party Marketplace activation
can require Subscribe/ViewSubscriptions/Unsubscribe by an enrollment operator and a valid
payment method. Anthropic needs its first-time use-case form. Do not grant these enrollment
permissions to Lambda. Some accounts have additional access restrictions.
[Current model-access requirements](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).

Local: BEDROCK_MODEL_ID + ENABLE_BEDROCK=true after token-cost approval. CDK:
bedrock_model_arn installs the model permission and ID, but **does not enable Bedrock**.
Production ENABLE_BEDROCK requires an explicit reviewed CDK environment change; the same
applies to continuous workflows/SMS flags. Keep default false until the actual invocation
is reviewed and tested. Deterministic grounded explanations work without Bedrock.
Model selection, token pricing and credit eligibility remain unverified; no invocation now.

## 13. Configure alerts, SNS and automated workflows

For operational alarms: **SNS → deployed OperationalAlertsTopic → Create subscription →
Email**; enter address privately and confirm its email. Check **CloudWatch → Alarms/Log
groups** and the actual Lambda/API logs. An alarm without a confirmed recipient cannot
provide email alerts. Do not log health/location/token payloads.

For personal SMS, separately create a dedicated **Standard SNS topic with exactly one
SMS subscriber per user**. Verify the destination under **SNS → Text messaging (SMS) →
Sandbox destination numbers**. OTP verification can charge. Set a reviewed small account
SMS allowance, e.g. $1, and inspect sandbox status:

```powershell
aws sns get-sms-sandbox-account-status --profile dev-admin --region ap-south-1
aws sns get-sms-attributes --attributes MonthlySpendLimit --profile dev-admin --region ap-south-1
```

Runtime: Publish/ListSubscriptionsByTopic exact dedicated topic; GetSMSAttributes,
GetSMSSandboxAccountStatus/ListSMSSandboxPhoneNumbers require resource-wildcard read
exceptions constrained to Mumbai. Operator topic/subscription/verification/SetSMSAttributes
actions are separate. Configure SNS_ALLOWED_TOPIC_ARNS as a JSON array and an operator-owned
topic-to-Cognito-sub preference binding; the user must also opt in. Topic allowlisting alone
does not authorize notification delivery.

For India: **AWS End User Messaging SMS → Registrations → India transactional sender ID**.
Complete actual telecom DLT entity, sender/header, exact content template and applicable
telemarketer registration, then AWS association/approval. Supply SMS_SENDER_ID,
SMS_ENTITY_ID, SMS_TEMPLATE_ID. Do not make these IDs up; approval can block a hackathon.
[India registration](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-sms-senderid-india-support.html).

**Compatibility gate:** the current publisher builds EntityId/TemplateId with the
`AWS.SNS.SMS.` prefix. Current SNS documentation specifies **AWS.MM.SMS.EntityId** and
**AWS.MM.SMS.TemplateId** (SenderID remains AWS.SNS.SMS.SenderID). Correct and test that
mapping before a paid India SMS test. This guide does not claim SMS is ready merely
because credentials are configured. [SNS sending attributes](https://docs.aws.amazon.com/sns/latest/dg/sms_sending-overview.html).
Publish MessageId proves acceptance, not carrier delivery; use delivery-status logs for that.

For workflows: CDK enable_workflows=true defines orchestration, queue and DLQ. Execution
role permissions are generated by the construct. Configure actual WORKFLOW_STATE_MACHINE_ARN
and trusted owner template. A caller may have StartExecution only this machine or SendMessage
only its queue. Scheduler definitions and dispatcher/stage activation remain disabled.
Before changing them, review a single execution, pipeline failure/DLQ behavior, verified model
availability, notification consent and cumulative costs. The worker stages intentionally
do not use Bedrock and have SMS disabled. See [PHASE6_ADVISORIES.md](PHASE6_ADVISORIES.md).

## 14. Configure ML and wearables only when their prerequisites exist

### SageMaker AI

1. Collect sufficiently complete real station history first. Existing audit: 5 measured
   PM2.5 records, zero eligible supervised samples; no trained model or metrics.
2. Confirm SageMaker ml.m5.large training quota >=1 in Mumbai.
3. Start Docker Desktop; build the repository's reviewed ML Docker image. Create an
   immutable private ECR repository, push after cost approval, record its image digest.
   Push needs GetAuthorizationToken (resource wildcard) and scoped BatchCheckLayerAvailability,
   InitiateLayerUpload/UploadLayerPart/CompleteLayerUpload/PutImage on that repository.
4. Supply CDK ml_image_uri as that regional private ECR digest URI. CDK creates the
   SageMaker-trusted role, optional training workflow and on-demand inference worker.
   Read actual TrainingRoleArn/MlWorkflowArn/MlInferenceFunctionArn and MlBucket outputs.
5. Prepare chronological datasets, validate manifests/hashes, upload only approved dataset
   objects, build the existing job plan. Set SAGEMAKER_EXECUTION_ROLE_ARN and
   ML_INFERENCE_FUNCTION_ARN where appropriate; these are non-secret ARNs.
6. Only after per-job cost/data approval start training: one ml.m5.large, 900s maximum
   runtime, 1800s pending limit, no automatic paid retry or real-time endpoint. Maximum
   runtime is not a hard dollar cap. Verify logs, actual metrics and baseline comparisons.

No SageMaker Studio domain is required. Workflow caller needs StartExecution exact machine;
direct operator job launch, if chosen, needs scoped Create/Describe/StopTrainingJob and
PassRole only the training role to SageMaker. Stop jobs/executions when finished; retain
or delete ECR/S3 artifacts deliberately. [ML_WORKFLOW.md](ML_WORKFLOW.md) has exact commands.

### Wearables / IoT Core

The Noise ColorFit Pro3 Alpha / NoiseFit Assist connector is unverified. Credentials do
not make it an MQTT watch. Start with authenticated Cognito HTTPS ingestion: register
the owned device and grant revocable consent. No IoT certificate is required for HTTPS.

For a genuinely supported MQTT bridge only: deploy the optional IoT stack with --iot
after approval; use IoT Core **Settings → Device data endpoint** to obtain IOT_DATA_ENDPOINT:

```powershell
aws iot describe-endpoint --endpoint-type iot:Data-ATS --profile dev-admin --region ap-south-1
```

Register the device/consent first, obtain its owner hash, generate the exact policy with
scripts/iot_device_plan.py. In Console **IoT Core → Manage → Things**, create the matching
eco-DEVICE_ID Thing; under **Security → Certificates**, use a locally generated CSR,
activate the signed certificate and attach only the generated exact-client/topic policy
and matching Thing. Operator needs CreateThing/CreatePolicy/AttachPolicy/AttachThingPrincipal,
CreateCertificateFromCsr and corresponding read checks; bind_iot_certificate.py verifies
and writes the approved registration binding with exact wearable-table GetItem/PutItem.
Enable the disabled rule only for an approved test, following [WEARABLES.md](WEARABLES.md).

IOT_CERT_PATH/IOT_PRIVATE_KEY_PATH/IOT_ROOT_CA_PATH are protected local paths, not key contents.
Never upload private keys to Git or distribute AWS credentials to the watch/app. Test exact
topic and rejected spoofed/duplicate events. Revocation: withdraw consent, deactivate the
certificate, disconnect and detach policy/Thing as appropriate. IoT messages/connections,
rules, Lambda and archives can charge. Simulator events are not physical-watch measurements.

## 15. Optional hosting, compute and SQL are alternatives

Use ignored work/deployment.json referenced by ECOROUTE_DEPLOY_CONFIG, selecting one runtime,
one host and at most one SQL analytics backend. Do not deploy every alternative together.
None needs a separate AWS access key.

| Selection | Console/configuration prerequisites | IAM and verification |
|---|---|---|
| CloudFront + private S3 | hosting=cloudfront; use default distribution hostname, or existing Route53 zone + DNS-validated us-east-1 ACM cert | CDK host resources; publisher S3 PutObject hosting bucket + CreateInvalidation distribution. Actual FrontendBucket/DistributionId outputs, reviewed publish script and HTTPS smoke |
| Amplify manual hosting | hosting=amplify; actual AmplifyAppId from CDK; build same frontend | Scoped CreateDeployment/StartDeployment/GetJob; approved publish script; job success plus live verification, not merely submission |
| Route53 custom domain | domain_name/hosted_zone_id/hosted_zone_name; domain ownership and public zone; certificate validation | ChangeResourceRecordSets exact zone and certificate reads. Zone/queries/domain fees; optional if default hosting hostname is used |
| ECS/Fargate or EC2 | Private Linux amd64 ECR image_uri pinned by digest; DNS-validated Mumbai ACM regional_certificate_arn; matching domain | CDK creates runtime/task/instance roles; exact image pulls/downstream API permissions. EC2 additionally uses SSM. ALB/task/instance/IPv4/storage/logs charge continuously |
| EKS | Reviewed supported eks_version, exact eks_operator_arn, public-network eks_admin_cidrs /32; digest image | DescribeCluster + authorized access entry; apply generated Kubernetes manifest. HTTPS ingress controller/cert/DNS and container log collection are extra prerequisites; cluster/nodes charge continuously |
| App Runner | Existing-customer eligibility, existing_apprunner_customer=true, digest image | CDK ECR-pull + API instance roles; idle memory charges. It is not an option for a newly ineligible customer |
| Lightsail proxy | Public credential-free digest image and api_gateway_origin | Restricted container-service deployment/read permissions; fixed idle charges. This forwards to the existing Cognito API; do not make Gateway forward back to it |
| RDS PostgreSQL | analytics=rds; supported postgres_version, sql_image_uri, sql_writer_secret_arn; restricted SQL user/schema via private admin path | Writer GetSecretValue exact secret, raw-report objects/queue/logs and required ENI actions. Private DB, TLS/CA bundle, instance/storage/backups/interface-endpoint charges |
| Aurora PostgreSQL | analytics=aurora; supported Data API engine version, sql_writer_secret_arn; restricted SQL user/schema initialization | Writer ExecuteStatement exact cluster + GetSecretValue exact writer secret; capacity/storage/I/O costs. No API database admin credentials |

SQL writer secret: **Secrets Manager → Other secret → username=ecoroute_writer,
password=privately generated value**; copy ARN only to deployment JSON. The restricted
database user must exist with the same password and only migration-defined grants. CDK's
separate master secret is for approved initialization, not the worker. RDS needs a private
admin connection; Aurora may use an approved Data API initialization path. Availability,
orderable engine version, quotas and permission checks are still required. Do not expose
the database publicly to avoid creating an admin path.

Container rollout is two-stage: initially keep API Gateway on Lambda, verify new runtime
HTTPS/Cognito, then configure verified backend_origin and redeploy Core. Frontend hosting
is also staged if its hostname was initially unknown: create host, copy actual URL into
Core callback/CORS, deploy those settings, build the frontend with actual public IDs and
publish/verify. Never put AWS/provider secrets into a build.

Full optional configuration, cost allowances and scripts: [MULTISERVICE_INTEGRATION.md](MULTISERVICE_INTEGRATION.md).
Use [AWS Pricing Calculator](https://calculator.aws/) for the actual region/capacity quote.
Leave optional always-on runtimes/SQL off for this credit-limited demo; no NAT is required
by the default architecture. CloudFront/S3 or Amplify is the light hosting choice.

## 16. Verify and clean up

After approved deployment verify CloudFormation status, health HTTP200, protected APIs401
without JWT, valid scopes/user isolation, provider provenance/units, genuine routed geometry,
private bucket access, logs/alarms, DLQ and disabled notifications. Evaluate real ML metrics
only after a successful trained-model audit. Use the existing demo/contract tests before
claiming integration. Recorded data/local tests are not cloud verification.

Stop/disable schedules, executions, training and IoT publishing before teardown. With the
same config/--iot choices used for deployment, after deciding what data to preserve:

```powershell
.\.venv\Scripts\python.exe scripts/manage_cloud.py teardown --profile dev-admin --region ap-south-1 --expected-account-id YOUR_ACCOUNT_ID --apply --confirm-retaining-teardown
```

This is a **retaining** teardown, not a zero-cost purge: protected S3/DynamoDB/Cognito,
bootstrap/ECR, database snapshots/secrets and external DNS/domain resources can remain.
Optional SQL deletion protection must be handled deliberately; remove EKS ingress-created
resources before destroying a cluster. Inspect resource inventory and Billing afterwards.

Minimum configuration to do first: credited account/plan → non-root temporary profile/MFA
→ budget → diagnostic IAM/quotas → reviewed deployment IAM/bootstrap → OpenAQ secret and
Location permissions → approved Core deployment → Cognito/frontend configuration. Bedrock,
ML, IoT, SMS and optional hosting/runtime/SQL follow only when their prerequisites are ready.
