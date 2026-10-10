# AWS service integration and deployment profiles

2026-10-10. Code and offline templates only. No deployment, authenticated AWS check, paid
training, hosting upload, database connection or message delivery was performed in this update.
Reuse the completed application; there is no new frontend or independent demonstration backend.

## How the services connect

| Services | Meaningful role and dependency | Default |
|---|---|---|
| Lambda, API Gateway, Cognito | Existing FastAPI/Mangum REST API, JWT scopes and per-owner checks; short-lived ingestion/archive/advisory handlers | API defined, not deployed |
| S3, DynamoDB | Existing raw/curated pollution, ML artifacts, private route results, owned journeys/consent/telemetry and idempotency | Defined, not deployed |
| EventBridge Scheduler, SQS, Step Functions | Existing bounded ingestion, partial failure/DLQ processing and multi-stage ML/environment workflows | Schedules disabled; workflows opt-in |
| SageMaker AI | Existing historical-data gate, BYOC training and verified artifact publication; optional on-demand inference Lambda | No training job or endpoint launched |
| SNS, CloudWatch | Existing opt-in, verified SMS destinations; structured logs, alarms and operational topic | SMS disabled; no subscribers added |
| ECS + Fargate | Same FastAPI image with the Core Cognito IDs, seven table names, S3 prefixes and scoped API IAM role; HTTPS ALB | Optional alternative to API Lambda |
| EC2 | Same container/data/authentication on a small AL2023 instance behind HTTPS ALB, IMDSv2, encrypted EBS, SSM and CloudWatch Docker logs | Optional alternative |
| EKS | Same container/data/authentication, bounded managed node group, scoped Pod Identity, restricted Kubernetes API and generated Deployment/ClusterIP Service | Optional; application apply and ingress remain operator steps |
| App Runner | Same container/data/authentication with ECR pull and instance roles, bounded concurrency and public outbound connectivity | Existing eligible customers only |
| Lightsail | HTTPS companion proxy forwards bearer tokens to existing API Gateway; upstream validates Cognito and ownership | Optional proxy, never an AWS-key-bearing backend |
| CloudFront + S3 + Route 53 | Existing Vite build served through signed OAC requests to a private bucket; optional A/AAAA aliases to an existing zone | Optional hosting choice |
| Amplify Hosting | Alternative manual hosting of the exact same Vite build; create/upload/start deployment script | Optional hosting choice |
| RDS PostgreSQL / Aurora PostgreSQL | Existing route scorer -> anonymized S3 aggregate report -> separate encrypted SQS/DLQ -> validated SQL writer Lambda | Optional analytics choice; never primary wearable/location storage |

Location Routes/Places, OpenAQ/Open-Meteo, IoT and Bedrock integrations remain in their existing
modules and workflows. This change does not activate them or change model/measurement claims.
Google route responses remain request-only: the SQL validator also rejects Google reports.
Analytics schemas reject user IDs, geometry, coordinates and health telemetry. See `sql/route_analytics.sql`.
Aggregate reports are retained for 30 days in SQL; source reports keep the existing 7-day S3 policy.
Deletes are performed on successful ingestion, not a guaranteed wall-clock erasure schedule; an
operator must run the same retention DELETE periodically if ingestion is inactive.

## Local, credential-free checks

From the repository root, PowerShell:

```powershell
.venv\Scripts\python.exe scripts/service_plan.py
.venv\Scripts\python.exe scripts/manage_cloud.py plan
.venv\Scripts\pytest.exe tests/test_service_profiles.py tests/test_optional_infra.py -q
.venv\Scripts\ruff.exe check src infra scripts tests
$env:Path = "$PWD\.venv\Scripts;$env:Path"
npm run synth
```

Use `config/deployment.example.json` as the safe default. Create a NON-SECRET JSON in ignored
`work/deployment.json` and set `ECOROUTE_DEPLOY_CONFIG` only when selecting an optional profile.
Do not put passwords, access keys, tokens or certificates in it. It rejects unknown fields.
Allowed selectors: `runtime` = `lambda`, `ecs-fargate`, `ec2`, `eks`, `apprunner`, `lightsail-proxy`;
`hosting` = `none`, `cloudfront`, `amplify`; `analytics` = `none`, `rds`, `aurora`.
Pick one option per category. No NAT Gateway or always-on SageMaker endpoint is defined.

Optional runtime inputs: `image_uri` (account/region ECR `@sha256:` digest),
`regional_certificate_arn` (ECS/EC2), `backend_origin` (verified HTTPS custom origin).
EKS also needs `eks_version`, `eks_operator_arn`, `eks_admin_cidrs` (no /0).
App Runner needs `existing_apprunner_customer=true`; this is a prerequisite declaration, not
evidence AWS grants access. Lightsail needs a public ECR digest-pinned proxy image plus
`api_gateway_origin`; it is not eligible to become Gateway's backend, which would make a loop.

CloudFront custom-domain inputs: `domain_name`, `hosted_zone_id`, `hosted_zone_name`,
`cloudfront_certificate_arn` in **us-east-1**. Without these, use the distribution hostname.
SQL inputs: `sql_writer_secret_arn`, supported `postgres_version` (template default 16.6).
RDS additionally requires `sql_image_uri` built with psycopg and the official CA trust bundle.
Use current regional engine availability checks below before approving that version.

## Credential and prerequisite setup (configure later)

All profile inputs and ARNs are non-secret. Secret contents must stay in CLI credential stores,
Secrets Manager or protected files. Mandatory means only for the selected optional profile.
Existing service credentials remain documented in CREDENTIALS_CHECKLIST.md and phase guides.

| Name / requirement | Purpose, sensitivity, required for | Exact setup and secure storage | Minimum verification IAM / billing |
|---|---|---|---|
| AWS_PROFILE, AWS_REGION, EXPECTED_AWS_ACCOUNT_ID | Temporary IAM/SSO identity, Mumbai deployment; identifiers public, credentials sensitive; all AWS actions | Use approved IAM Identity Center permission set -> AWS access portal -> account; `aws configure sso --profile dev-admin` and `aws sso login --profile dev-admin`. Existing authorized profile may be reused. `aws configure set region ap-south-1 --profile dev-admin`. Keep credentials in CLI provider, never source files/root | `sts:GetCallerIdentity`; `aws sts get-caller-identity --profile dev-admin`; selected account must match credits. No paid resource from STS |
| CDK_BOOTSTRAP and deployment permission set | Asset publication/CloudFormation execution; all selected stacks | CloudFormation console -> check CDKToolkit. Bootstrap is a separate approved action; provision scoped execution policies and a permissions boundary. CLI `aws cloudformation describe-stacks --stack-name CDKToolkit --profile dev-admin --region ap-south-1` | `cloudformation:DescribeStacks`; later scoped CloudFormation/ECR/S3/IAM PassRole and service create/update/delete permissions for reviewed template. Do not demand AdministratorAccess. Asset storage/registry can charge |
| image_uri / sql_image_uri | Immutable deployed Docker artifact; runtime/RDS | ECR console -> Private registry -> create named repository with scan on push and immutable tags; approved operator builds/pushes, copies image digest. Store URI only in ignored deployment JSON. Existing image must be Linux amd64 | Push role: ECR GetAuthorizationToken (Resource=*), scoped InitiateLayerUpload/UploadLayerPart/CompleteLayerUpload/BatchCheckLayerAvailability/PutImage/DescribeImages on that repo. Runtime pull: scoped BatchGetImage/GetDownloadUrlForLayer/BatchCheckLayerAvailability plus token. ECR storage/scans/compute charge |
| regional_certificate_arn and backend_origin | HTTPS ALB and Gateway routing; ECS/EC2 | ACM Mumbai -> Request public certificate for a domain you control -> DNS validation. Copy ARN; create CNAME/alias to ALB and verify matching hostname. Do not use ALB hostname with a mismatching certificate. Store origin/ARN in JSON | acm:DescribeCertificate; DNS change only chosen zone; verified GET health and invalid-token 401. Public ACM certificate generally no standalone fee; ALB/IPv4/DNS charge |
| eks_version, eks_operator_arn, eks_admin_cidrs | Supported Kubernetes version, authorized operator, restricted API; EKS | EKS console -> available versions; IAM -> approved operator role; use your public network /32. Copy into JSON. No kubeconfig token in repo. `aws eks update-kubeconfig --name <ClusterName> --profile dev-admin --region ap-south-1` writes local protected kubeconfig | eks:DescribeCluster; access entry explicitly grants cluster administration to supplied operator. Restrict who can assume it. Version/quota checks below; EKS cluster/node/EBS/IPv4 costs apply |
| existing_apprunner_customer | Service eligibility; App Runner | App Runner console in selected account -> verify existing-customer access. Cannot be fixed by supplying an API key. Store Boolean only after verification | apprunner:ListServices/DescribeService and reviewed service/pull/runtime roles. Service has idle capacity charges |
| api_gateway_origin / public proxy image | Credential-free Lightsail proxy; Lightsail | Obtain existing Core API URL, build proxy container and publish approved public image **without `.env`**; configure origin and digest only. Lightsail console -> Containers lists deployed service HTTPS endpoint | lightsail:GetContainerServices; reviewed Create/UpdateContainerService permissions and image publication. Public image exposes code, not secrets; service charges even disabled |
| hosted_zone_id/name, domain_name, cloudfront_certificate_arn | Optional custom frontend domain, Route 53 | Route 53 -> registered/externally owned domain -> public hosted zone -> copy ID/name; ACM **N. Virginia us-east-1** -> DNS-validated domain cert. Existing zone imported; no automatic domain registration | route53:GetHostedZone/ChangeResourceRecordSets scoped to zone; acm:DescribeCertificate. Zone/query/domain costs, certificate guidance as above |
| FrontendBucket / DistributionId / AmplifyAppId | Upload current frontend to selected host | Read actual CDK output; configure public `VITE_API_BASE_URL`, Cognito domain/client/callback in frontend/.env.production, run build. Update Core exact origins and PKCE callbacks. Store public identifiers in config only; never VITE provider/AWS secrets | CloudFront publish: s3:PutObject scoped hosting bucket + cloudfront:CreateInvalidation distribution. Amplify publish: amplify:CreateDeployment/StartDeployment/GetJob on app branch. Upload URL temporary secret is used without logging. Hosting/build/transfer charges |
| sql_writer_secret_arn | Restricted SQL user password; RDS/Aurora; contents sensitive | Secrets Manager -> Store a new secret -> Other type -> username/password for `ecoroute_writer`; use locally generated password. First deploy creates isolated database/admin secret; initialize user and `sql/route_analytics.sql` through a protected private admin session (RDS) or approved Data API admin statement (Aurora). Worker never reads admin secret. Store only writer ARN in JSON | Worker: secretsmanager:GetSecretValue exact writer ARN; Aurora rds-data:ExecuteStatement exact cluster, no admin secret. SQL GRANT only SELECT/INSERT/DELETE on route_reports. Secret/database/endpoint charges |
| SQL_CA_BUNDLE / build/rds-ca.pem | TLS hostname validation; RDS container only; public trust anchor | Download reviewed [official global RDS CA bundle](https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem) into ignored build/rds-ca.pem, build docker/analytics.Dockerfile. Worker uses sslmode=verify-full, deployed path /opt/rds-ca.pem | No AWS credential to retrieve public CA. Verify real private DB connection after initialization; build/push/storage can charge |
| Budget amount and recipients | Alerts before using $100 credits; budget recipients personal | Billing and Cost Management -> Budgets -> Create budget -> Cost budget -> monthly reviewed amount (proposal $20) -> actual alerts 50/80/100%, forecast 100%. Store subscription/config in AWS, never chat | budgets:CreateBudget/UpdateBudget/ViewBudget; billing permission needed. Verify account credit expiry/service eligibility in Billing -> Credits. Budget alerts do **not** hard-cap costs |

## Region, IAM and quota verification before deployment

The template/SDK schemas were checked locally and against official documentation. Offline
endpoint/template support is not proof of account access, Free Tier eligibility, capacity or quota.
Mumbai remains the default. Route 53 and CloudFront are global; their custom certificate is us-east-1.
Check service enrollment, commercial-region availability and these read-only queries **after**
you configure the approved CLI profile. CLI output may contain non-secret account identifiers.

```powershell
aws service-quotas list-service-quotas --service-code fargate --profile dev-admin --region ap-south-1
aws service-quotas list-service-quotas --service-code eks --profile dev-admin --region ap-south-1
aws service-quotas list-service-quotas --service-code ec2 --profile dev-admin --region ap-south-1
aws service-quotas list-service-quotas --service-code rds --profile dev-admin --region ap-south-1
aws rds describe-db-engine-versions --engine postgres --engine-version 16.6 --profile dev-admin --region ap-south-1
aws rds describe-db-engine-versions --engine aurora-postgresql --engine-version 16.6 --profile dev-admin --region ap-south-1
aws eks describe-cluster-versions --profile dev-admin --region ap-south-1
```

Permissions: service-quotas:ListServiceQuotas/GetServiceQuota and the corresponding
rds:DescribeDBEngineVersions, eks:DescribeClusterVersions; these read-only catalog APIs may
require Resource=*. Also check ALB count, ENIs, public IPv4, RDS instance class/orderability,
Aurora Serverless v2 and Data API region/engine compatibility, Amplify app count, Route 53 zone,
CloudFront distributions, Lambda reserved concurrency and existing SageMaker training quotas.
Do not increase quotas, enable subscriptions or bootstrap automatically.

Runtime roles reuse only Core's scoped API actions, including exact optional provider secrets,
Location provider ARNs, Bedrock model, SMS topics and ML inference ARN. Separate task execution,
EC2 instance, App Runner ECR pull, EKS node/control-plane and Pod Identity roles serve their
specific purpose. EKS node managed policies are AWS-recommended infrastructure policies;
Pod Identity has only app permissions, and IMDS hop limit 1 prevents pod use of the node role.
EC2 Docker needs IMDSv2 hop limit 2 for its instance role, with no public port except ALB HTTPS.
RDS Lambda's ENI actions require Resource=*; secret/object/database permissions are scoped.
S3 notification custom resources need notification read/write permission on the existing bucket.
No separate AWS access keys are distributed to frontend, Lightsail or mobile devices.

## Runtime/hosting handoff and verification

Container selection initially leaves Gateway on the existing Lambda. This prevents a circular
dependency between Core Cognito/environment and a new runtime URL. Deploy/smoke-test the chosen
runtime **only after approval**, then set `backend_origin` to verified HTTPS and redeploy Core.
Gateway JWT scopes remain in force, and FastAPI validates JWTs again even at the direct origin.
Do not point Gateway to Lightsail, which forwards back to Gateway. Async handlers remain Lambda.

EKS deployment is intentionally two steps: CDK creates cluster/nodes/Pod Identity, then:

```powershell
.venv\Scripts\python.exe scripts/render_eks.py --outputs work/deployed-outputs.json
# With approved cluster and operator kubeconfig only:
kubectl apply -f work/eks-backend.json
kubectl -n ecoroute rollout status deployment/backend
kubectl -n ecoroute port-forward service/backend 8001:8000
```

ClusterIP is private. Public HTTPS ingress requires an installed, correctly scoped AWS Load
Balancer Controller, ACM certificate and DNS; these are **not installed by this change**.
Container logs require a separately configured collector for CloudWatch; cluster audit logs
are enabled with 7-day retention in CloudWatch. App Runner creates its own automatic service
log groups; configure their retention after deployment. Until ingress is configured/verified,
do not set an EKS backend_origin.
This is explicitly a deployment prerequisite, not a claim that the cluster/app is running.

Hosting publishes the existing build using `scripts/publish_frontend.py --target cloudfront`
or `--target amplify` (plan only). After approved setup, supply --profile, --expected-account-id,
--apply and --accept-estimated-charges. It checks non-root identity. CloudFront uploads private
objects and submits invalidation; Amplify uploads ZIP without exposing its temporary URL and
reports AWS job submission status. Neither submission means the website passed live validation.
Verify all protected APIs return 401 without a token, account ownership is isolated and CORS
accepts only your exact origin. Local simulation/offline tests are not live verification.

## Cost proposal and cleanup

No new paid service is required for the default hackathon profile. For roughly 10,000 API calls,
small datasets/logs and no paid model/SMS usage, keep the existing **$5–20/month planning allowance**
before credits. This is not a measured bill or guaranteed price. Review AWS Pricing Calculator
in Mumbai and actual credit eligibility first. Alternative totals are **additional** and exclude
tax, model/token jobs, egress, logs, snapshots, ECR and other workload-dependent costs:

| Option | Cost expectation before credits |
|---|---|
| EKS | Standard-support cluster $0.10/hour = $73 at 730h, plus node/EBS/IPv4/logs; exceeds a $20 allowance by itself |
| ECS/Fargate + ALB | Always-on task + ALB/hour/LCUs + public IPv4; reserve roughly $30–70/month for review, not a regional quote |
| EC2 + ALB | Instance/EBS + ALB/hour/LCUs + IPv4; roughly $40–90/month planning allowance |
| App Runner | Provisioned memory idle plus active vCPU/memory; existing-customer eligibility required; quote chosen capacity and traffic |
| Lightsail micro proxy | Published micro container base $10/month at scale 1; unused/disabled services still accrue charges until deleted |
| RDS | Instance/storage/backup + Secrets Manager + **two-AZ interface endpoint**; roughly $35–80/month planning allowance |
| Aurora | Minimum 0.5 ACU in this template, maximum 1; capacity/storage/I/O/secret/Data API; roughly $50–120/month planning allowance |
| CloudFront/S3 or Amplify | Usage-based hosting/storage/requests/transfer; roughly $1–10/month light-demo allowance, verify account offers |
| Route 53 | Typically $0.50/hosted zone/month for first zones plus DNS queries; domain registration extra |
| NAT Gateway | None defined. Adding NAT would incur recurring gateway/hour, processed-data and IPv4 charges even with low traffic |

Planning ranges are deliberately not rate claims. [EKS pricing](https://aws.amazon.com/eks/pricing/),
[Lightsail pricing](https://aws.amazon.com/lightsail/pricing/), [Fargate pricing](https://aws.amazon.com/fargate/pricing/),
[ALB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/), [RDS pricing](https://aws.amazon.com/rds/postgresql/pricing/),
[Aurora pricing](https://aws.amazon.com/rds/aurora/pricing/), [Amplify pricing](https://aws.amazon.com/amplify/pricing/),
[CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/), [Route 53 pricing](https://aws.amazon.com/route53/pricing/).
Credits are not a hard cap. Avoid running these alternatives together simply to show service names.

Approved deployment uses the existing guarded wrapper with the selected non-secret config:

```powershell
.venv\Scripts\python.exe scripts/manage_cloud.py plan --deployment-config work/deployment.json
# Only after reviewing actual regional costs/template/permissions and obtaining approval:
.venv\Scripts\python.exe scripts/manage_cloud.py deploy --deployment-config work/deployment.json --apply --accept-estimated-charges
```

One-command **retaining teardown**, only after deciding what user data to preserve:

```powershell
.venv\Scripts\python.exe scripts/manage_cloud.py teardown --deployment-config work/deployment.json --apply --confirm-retaining-teardown
```

Use the SAME configuration that created optional stacks and the same --iot choice. Stop jobs,
executions and schedules first; remove EKS workloads/controller-created load balancers before
cluster teardown. Protected RDS/Aurora need deletion protection disabled by an approved operator
first; snapshots, admin/writer secrets, retained frontend/data/ML buckets, tables, Cognito,
bootstrap/ECR and external DNS/domain resources may remain and charge. The wrapper captures
resource inventory and does not silently purge data or promise a zero-dollar account.

## Official API references checked

* [App Runner availability](https://docs.aws.amazon.com/apprunner/latest/api/API_StartDeployment.html): closed to new customers; existing accounts need eligibility verification.
* [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) and [association](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-association.html).
* [Lightsail container deployments](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services-deployments.html).
* [CloudFront OAC/private S3](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).
* [Amplify CreateDeployment](https://docs.aws.amazon.com/amplify/latest/APIReference/API_CreateDeployment.html) and [StartDeployment](https://docs.aws.amazon.com/amplify/latest/APIReference/API_StartDeployment.html).
* [Aurora Data API region/engine matrix](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.Aurora_Fea_Regions_DB-eng.Feature.Data_API.html): Mumbai supports eligible PostgreSQL 16.1+ engines; actual orderability/version must be checked.
* [RDS PostgreSQL TLS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html).
* [App Runner VPC networking](https://docs.aws.amazon.com/apprunner/latest/dg/network-vpc.html): connector egress requires appropriate routes/endpoints; the optional profile uses default public egress.
* [EKS endpoints/quotas](https://docs.aws.amazon.com/general/latest/gr/eks.html), [App Runner endpoints/quotas](https://docs.aws.amazon.com/general/latest/gr/apprunner.html), [Lightsail endpoints/quotas](https://docs.aws.amazon.com/general/latest/gr/lightsail.html) include Mumbai. Local botocore metadata also lists Mumbai for ECS/EKS/EC2/App Runner/Lightsail/RDS/Amplify/SageMaker/Data API; that is not an account entitlement test.
* [psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html): the SQL container's CPython 3.11 Linux amd64 wheels (including psycopg-binary 3.3.6) were actually downloaded/resolved; pinned in docker/analytics.lock. Docker daemon and live private database were not available, so image execution/connection are not claimed.
