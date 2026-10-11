# AWS readiness, Gemini and SageMaker — 2026-10-11

Latest direction: retain SageMaker for genuine measured-data training; use Gemini instead of
Bedrock for optional grounded explanations. This supersedes the intervening request to exclude
SageMaker. These are code, template and read-only account checks, not a successful deployment.

## Actual checks

Profile `dev-admin` authenticates as IAM user `devesh_eco`, account `112920804206`, region
`ap-south-1`. Python Boto3 and AWS CLI authentication both work. Do not use the root profile.
`scripts/aws_readiness.py` wrote a private report in `work/aws-service-readiness.json`.

* `CDKToolkit` DescribeStacks returned ValidationError: stack does not exist.
* DescribeStacks for EcoRoute stacks is denied: their live existence is unverified, not assumed absent.
* API Gateway, Cognito, DynamoDB, Scheduler, SQS, SNS, IoT things, Step Functions state machines,
  Secrets Manager and SageMaker training-job lists were accessible and empty in Mumbai.
* S3 listed three existing buckets. This change neither reads their objects nor repurposes them.
* ECR repository listing, CloudWatch alarm listing, quota listing, region access inspection,
  bootstrap parameter lookup, own attached-policy listing and IAM simulation were denied.
* Lambda account limit: 10 concurrent executions, all unreserved. Default CDK app now omits
  reserved concurrency because AWS retains 100 units for unreserved use when allocating
  reservations. Existing API throttling, DDB request caps and SQS maximum concurrency remain;
  no function-specific hard cap applies in this default. Request a quota increase before selecting
  `lambda_reserved_concurrency=true` in the deployment JSON.
* Docker CLI is installed but its daemon is unavailable. Local Linux Lambda asset build works.
* Backend `.env`, frontend `.env.local` and this process have no `GEMINI_API_KEY`. The expected
  backend file is `outputs/ecoroute-ai/.env` relative to the Codex workspace. A saved key was not
  located in the checked paths. No Gemini model call or key validation has succeeded.
* Actual local data preparation: 389 environmental records, 5 observed PM2.5 records, 384
  non-measured/non-PM2.5 records, one station series, zero eligible next-hour training samples.
  `work/ml/data_audit.json` reports insufficient history. No model was trained and no metrics exist.

Metadata access does not prove resource creation, PassRole, service entitlement, training quota,
runtime integration or notification delivery. IAM simulations also need actual resources/context,
and can differ from real authorization. Never resolve these issues with AdministratorAccess.

## Console actions now

1. Sign into the credited account using an authorized IAM operator/role. Select Mumbai for
   regional resources. **IAM → Users → devesh_eco → Permissions**: inspect attached policies,
   permissions boundary and any relevant organization restrictions. An operator must perform
   changes that this user cannot authorize; no root access key is needed.
2. **IAM → Policies → Create policy → JSON**: use [readiness-policy.json](iam/readiness-policy.json),
   replace `ACCOUNT_ID` with `112920804206`, name it `EcoRouteReadiness`, and create it. Attach via
   **Users → devesh_eco → Permissions → Add permissions → Attach policies directly**. This policy
   only adds the denied metadata/assessment actions; it does not authorize provisioning, reveal
   secret values or read location/health data. The operator needs `iam:CreatePolicy` and
   `iam:AttachUserPolicy` on the selected policy/user. Do not attach a broader fallback policy.
3. **Service Quotas → AWS services → Amazon SageMaker AI**, Mumbai: find
   **ml.m5.large for training job usage**, inspect the applied quota, and request 1 if it is 0
   and the account plan permits it. Requesting a quota is not launching a training job. Also
   review Lambda concurrent executions. Account-plan restrictions can prevent an increase;
   verify Billing plan/credit consequences before any upgrade.
4. **Billing and Cost Management → Credits**: check balance, eligible services and expiry.
   **Budgets → Create budget → Customize → Cost budget**: propose $10 monthly gross usage,
   excluding credits/refunds, actual alerts at 50/80/100%, forecast alert at 100%; separately
   monitor the account-wide $100 credit ceiling. Configure an email privately. Budgets are
   alerts, not hard spending caps. No budget has been created or verified here.
5. An authorized operator must review a CDK bootstrap/deployment execution policy for the
   selected stacks, then bootstrap after resource/cost approval. Use a custom execution policy,
   not the default broad AdministratorAccess bootstrap. The policy must cover CloudFormation,
   scoped project IAM roles/PassRole, S3/ECR assets, Lambda, API Gateway, Cognito, DynamoDB,
   Scheduler, SQS, SNS, logs/alarms, Step Functions and optional IoT/CloudFront. Resource creation
   often needs service-supported name/tag restrictions; see [the full setup guide](AWS_SETUP_FROM_ZERO.md).
   The new readiness policy is deliberately not this provisioning policy.

```powershell
aws sts get-caller-identity --profile dev-admin --region ap-south-1
.\.venv\Scripts\python.exe scripts/aws_readiness.py --profile dev-admin --region ap-south-1 --expected-account-id 112920804206
```

After the operator supplies a reviewed execution-policy ARN and deployment is approved:

```powershell
# Provisioning command: review and approve first. Replace the non-secret ARN placeholder.
.\node_modules\.bin\cdk.cmd bootstrap aws://112920804206/ap-south-1 --profile dev-admin --cloudformation-execution-policies <REVIEWED_EXECUTION_POLICY_ARN>
```

Bootstrap creates an asset bucket, ECR repository and deployment roles/version parameter. It is
not done by the diagnostic. After bootstrap, upload Lambda assets through CDK rather than
creating independent Console Lambda functions/tables that bypass the existing stack relationships.

## Gemini configuration

Save only in the existing ignored backend `.env`, preserving the other values:

```dotenv
ENABLE_GEMINI=true
GEMINI_API_KEY=<your-private-Gemini-key>
GEMINI_MODEL_ID=<supported-gemini-model-id-from-your-project>
ENABLE_BEDROCK=false
```

The Gemini adapter is implemented using the REST generateContent API and existing HTTPX.
Select an available `gemini-...` model; an explicit model ID is required, with no silent model
guess. No frontend VITE variable may contain this key. Restart the backend after saving. The
protected `/api/v1/ai/explain-route` path uses server-owned calculated routes, strips place names,
IDs, geometry/provider prose and health values from model input, accepts only a permutation of
approved statement IDs, and renders deterministic text. Invalid output, outages or a 20/day,
5/hour request cap produce a truthful deterministic fallback. Numerical scores never change.
The current guest Google request-only Insights path remains deterministic because those results
are not saved routes; this change does not add an anonymous AI/health endpoint or fake saved IDs.

For AWS: **Secrets Manager → Store a new secret → Other type of secret**, add `api_key` privately,
use the default AWS-managed encryption key, name it `ecoroute/gemini`, and leave rotation disabled
unless a real rotation function exists. The operator needs `secretsmanager:CreateSecret`; this
costs secret storage/API usage. Supply only its complete ARN and model ID as CDK contexts:
`gemini_secret_arn`, `gemini_model_id`. CDK gives the API role GetSecretValue on that ARN only;
the key itself is never in a template/Lambda environment or browser bundle. A customer KMS key
would additionally need a reviewed decrypt grant. No secret was created by this update.

Google/Gemini billing and quotas are separate from AWS credits. A Google Maps key does not
establish Gemini API access. Restrict a Gemini key to the appropriate API and never paste it in chat.

## SageMaker sequence

1. Deploy the reviewed Data/ML/Core definitions first. ML now defines an immutable private ECR
   repository and a least-privilege SageMaker execution role even before the image is supplied.
   Outputs: `MlBucket`, `TrainingImageRepositoryUri`, `TrainingRoleArn`. Training-role trust is
   restricted to this account's `ecoroute-*` training jobs; permissions cover dataset reads,
   training artifact writes, repository pulls and training logs only. No Studio domain,
   notebook, real-time endpoint or paid training is created by that preparation.
2. Start Docker Desktop, wait until `docker info` succeeds, build [Dockerfile.ml](../Dockerfile.ml),
   authenticate to the output ECR registry locally and push the image. Retrieve its digest and
   supply `ml_image_uri` as the same-region immutable `repository@sha256:...` CDK context.
   ECR operator permissions: GetAuthorizationToken, repository-specific InitiateLayerUpload,
   UploadLayerPart, CompleteLayerUpload, BatchCheckLayerAvailability, PutImage and DescribeImages.
   Review the image with a local container test before cloud use. Scanning/storage can incur costs.
3. Collect sufficient actual measured hourly station history using the existing OpenAQ adapter;
   never substitute Open-Meteo forecasts as training targets. The existing chronological
   preprocessing gate determines sufficiency. Historical retrieval timestamps must support
   feature availability at issuance; relabeling collection dates to bypass the gate is forbidden.
   Re-run `scripts/train.py --prepare-only`, then upload the validated versioned dataset through
   `scripts/upload_ml_dataset.py`. With today's data, STOP here: eligible sample count is zero.
4. Re-synth/deploy the optional ML workflow with the verified image digest. It orchestrates
   validation → one SageMaker training job → metric/artifact verification and registry publish;
   inference is Lambda load-on-demand. Its weekly retraining schedule stays disabled.
5. Generate a job specification using `scripts/sagemaker_plan.py` and review its costs before
   launching a manual workflow. Default: one `ml.m5.large`, maximum runtime 900s, pending wait
   max1800s, network isolation, no Spot/no automatic paid retries. Pending wait is not compute
   runtime. Require approved training quota and role-specific `iam:PassRole` to SageMaker plus
   `sagemaker:CreateTrainingJob/DescribeTrainingJob/StopTrainingJob/AddTags` on project job ARNs.
   Verify actual job status, logs and held-out/baseline metrics before making model claims.

Use **SageMaker AI → Training → Training jobs** and **CloudWatch → Log groups →
/aws/sagemaker/TrainingJobs** to monitor approved jobs. Stop a running job through Training jobs
if needed; completed jobs do not keep an endpoint running. Retained S3/ECR artifacts still cost storage.
Do not create a SageMaker Studio domain or notebook just to obtain the execution role.

## Concrete deployment proposal — not approved or executed

Selected config: [hackathon.aws.json](../config/hackathon.aws.json). Lambda backend, private S3/
CloudFront static hosting, DynamoDB, no idle database/container service. Use `enable_workflows=true`
and `enable_iot=true` contexts to define the connected workflow and IoT rule; schedules, SMS,
training and the IoT Rule remain inactive until their individual prerequisites are verified.
Amazon Location IAM integration is opt-in; Google Drive/Walk and ORS Cycle remain the working local
providers, requiring separate exact secret ARNs before public cloud guest routing.

Actual synthesized assembly: five stacks (Data, Core, ML, IoT, Hosting); 8 Lambda functions
(includes CDK's S3-notification helper), 7 DynamoDB tables, 3 private S3 buckets, 6 SQS queues,
14 CloudWatch alarms, 8 log groups, 2 disabled schedules, one API Gateway HTTP API/Cognito
pool, SNS operational topic, disabled IoT rule, environmental state machine, CloudFront/OAC
distribution and immutable ECR repository plus scoped roles. No reserved concurrency,
VPC/NAT, ECS/RDS service, SageMaker endpoint or training job is in this active assembly.
Stale optional templates remaining in cdk.out are excluded by its manifest, not deployed.
No Secrets Manager secret resource is created: complete references must be supplied separately.

After real secret ARNs and frontend origins exist, put only these non-secret settings in an
ignored `work/aws-context.json`: `gemini_secret_arn`, `gemini_model_id`,
`google_routes_secret_arn`, `cycling_secret_arn`, `provider_secret_arn`, `frontend_origins`,
`callback_urls`, optional `ml_image_uri`, `enable_guest_routes`, `ingestion_interval_minutes`.
The deployment wrapper accepts `--context-file work/aws-context.json --workflows`; it rejects
unknown keys and secret values in secret-reference fields. URL arrays from CLI context are
decoded before validation. Use the identical context for synth/deploy/teardown, so the optional
ML workflow and user-pool URLs do not silently differ. This is not a file for API keys.

Planning allowance: **$5–20/month** for a small serverless demo, assuming 10k HTTP requests,
100k Lambda invocations averaging512MB/1s, <1GB each data/static assets, <1GB internet delivery,
<0.5GB logs, small DDB items, one environmental collection/hour and a few workflow executions.
This includes a planning margin for the new roles/repository, alarms, private hosting and up to
four provider secrets, not a verified final regional bill or a guaranteed cap. Secrets alone
are about $0.40/secret-month plus retrievals; retained buckets/repositories, logging/alarms and
polling can cost money without an active user. No NAT Gateway or idle compute is in the proposal.
SageMaker training is additional: `current Mumbai ml.m5.large hourly rate × actual billable hours`
plus ECR, S3, logs and workflow costs. At a reviewed hypothetical $0.20/hour, 15 minutes of
compute would be $0.05; this arithmetic is **not a current Mumbai price quote**. Obtain the
official regional quote and request a separate first-job allowance before launching training.
SMS, custom-domain registration and external Google/ORS/Gemini charges are excluded. Bedrock disabled.

Optional ECS/Fargate, EKS, EC2, Lightsail, App Runner, Amplify and RDS/Aurora remain alternatives,
not services to run simultaneously. They require separate justification, permissions and cost
approval. A Route53 custom domain needs a real owned zone/domain and certificate identifiers.
No AWS secret, certificate, Cognito user, subscription or deployment was created here.

## Cleanup and verification

After approved deployment, use stack outputs to configure Cognito and exact HTTPS CORS/callbacks,
then verify health, JWT failures, real ingestion/curation and owned records before publishing the
frontend. Noise wearable health data remains blocked by undocumented vendor packets; IoT cannot
make that data available. SMS still needs an opt-in binding, verified destination, spending checks
and India sender/entity/template registration before a real send.

The retaining teardown is `scripts/manage_cloud.py teardown --apply --confirm-retaining-teardown`
with the same explicit profile/account/region, deployment config, IoT context and any ML image
context used for deployment. Stop schedules/jobs/executions and revoke device access first.
S3, DynamoDB, Cognito, ECR and bootstrap assets are retained intentionally; this is not a permanent
purge or a guarantee of zero charges. Do not delete existing unrelated S3 buckets.

Sources: [Gemini REST](https://ai.google.dev/api/generate-content),
[Gemini key security](https://ai.google.dev/gemini-api/docs/api-key),
[AWS Lambda concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html),
[CDK bootstrap policies](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping-customizing.html),
[SageMaker execution roles](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html),
[SageMaker pricing](https://aws.amazon.com/sagemaker/ai/pricing/),
[Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/).
