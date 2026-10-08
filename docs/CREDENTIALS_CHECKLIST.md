# Credentials and configuration checklist

Never paste keys, passwords, session tokens, private certificates or provider tokens into chat.
Current missing items: valid temporary AWS login, expected account ID, numeric monthly budget,
credit amount/expiry/eligibility, alert recipient, OpenAQ key, confirmed watch model/app/phone OS.
Existing default AWS profile is invalid and points to us-east-1. It was not modified.
Project name is ecoroute-ai; proposed region ap-south-1; target Delhi; all live flags remain false.

## 1. AWS human identity — required before any authenticated AWS integration

Configuration: AWS_PROFILE=ecoroute-dev; SSO start/issuer URL, SSO region, account ID and permission-set
name. Identifiers are non-secret (account ID is still best kept out of public reports). Cached SSO
tokens are sensitive. There is no app AWS secret key to request.

An authorized AWS account/organization operator must perform the following if SSO is not available:

1. Open **IAM Identity Center** in the AWS Console, select its intended home region, and enable or
   select an existing **organization instance** for AWS account access. An account instance alone
   does not provide the same multi-account permission-set assignments.
2. Under **Users**, create an individual user for each friend; require MFA through the identity
   provider. Create an EcoRoute developers group and add these users.
3. Under **Permission sets**, create a custom read-only diagnostic permission set with the actions
   in AWS_SERVICES.md. Do not choose AdministratorAccess. Assign the group to the selected AWS
   account under **AWS accounts → Assign users or groups**. Later add scoped service permissions
   only for adapters being enabled.
4. Under **Settings**, copy the AWS access portal URL and note Identity Center's home region.
   This can differ from workload region Mumbai. Account operator permissions include the necessary
   sso:CreatePermissionSet, PutInlinePolicyToPermissionSet, CreateAccountAssignment,
   ProvisionPermissionSet and identitystore user/group actions, plus organization setup rights if
   enabling for the first time. Developers do not need these provisioning rights.
5. In your own Windows account, run `aws configure sso --profile ecoroute-dev`. Enter the portal URL,
   actual SSO region, `sso:account:access` registration scope, selected account/permission set,
   default client region `ap-south-1` and output `json`.
6. Run `aws sso login --profile ecoroute-dev` and finish browser authentication yourself.
7. Verify locally with `aws sts get-caller-identity --profile ecoroute-dev --region ap-south-1`.
   Confirm the account and assumed role; never use an ARN ending in `:root` for development.

Storage: AWS CLI profile in `%USERPROFILE%\.aws\config`, temporary cache managed by CLI in the
user profile. Keep that directory outside Git and protect it with the OS account. Log out with
`aws sso logout` when the shared session ends (this can end other cached SSO sessions too).
SSO/STS authentication has no direct service charge; later API operations may be billed.
If SSO cannot be configured, use an organization-approved role/profile with temporary credentials
via a credential broker or credential_process; all three of access key, secret and session token
must be configured locally. Never create root keys or turn this into a request for long-lived IAM keys.

## 2. Prerequisite matrix

Each row is a gate before enabling that component. Resource creation steps are for a later approved
deployment; do not click Create now. Console paths can vary slightly by account experience.
Runtime action scopes are detailed in AWS_SERVICES.md.

| Configuration / use | Required? / sensitive? | Obtain or create (Console/provider) | Permissions | Secure storage | Verification | Charges? |
|---|---|---|---|---|---|---|
| PROJECT_NAME, ECOROUTE_PROFILE, TARGET_CITY | Required; no | Set ecoroute-ai, local, Delhi in local config; no Console resource | None | Ignored .env or process environment | /healthz and configuration validation | No |
| AWS_REGION, EXPECTED_AWS_REGION | Required for AWS; no | Console region picker → Asia Pacific (Mumbai); set both ap-south-1 | ec2:DescribeRegions to verify account region enablement | Local config; later CDK parameters | Diagnostic compares selected and expected region; account DescribeRegions | Read check no; regional resources yes |
| EXPECTED_AWS_ACCOUNT_ID | Required before diagnostic account reads; non-secret identifier | Console top-right account menu → Account ID; confirm with STS | STS identity needs no explicit allow | Local environment; not committed | Exact account match; root rejected | No |
| MONTHLY_BUDGET_USD, BUDGET_NAME, BUDGET_ALERT_EMAIL | Required before paid use; email personal | Billing and Cost Management → Budgets → Create budget; steps below | budgets:ViewBudget/ModifyBudget on selected budget; billing UI access | Local config; approved CDK parameters, email not public | DescribeBudget and Console notifications/subscribers | Alerts proposal no; check current Budgets pricing |
| Credit balance, expiry and eligible services | Required before relying on credits; billing-private | Billing → Credits; Free Tier page → account plan/usage; record expiry and restrictions privately | Account operator's billing/credits read permissions | Private cost note, not Git/chat secrets | Compare current billed usage and credit application | Reading Console no; credits may not cover every fee |
| ENABLE_AWS_LOCATION | Optional locally; required for real routes; no secret | Later enable flag after role policy; Location Console → Routes can inspect feature options; no legacy calculator or API key required for server SigV4 | geo-routes:CalculateRoutes on provider/default ARN | Local config / workload role | Phase 1 schema test, then one approved route request and inspect returned geometry | Yes, even read routing requests may bill |
| OPENAQ_API_KEY, ENABLE_OPENAQ | Optional fixture mode; required for selected real provider; key secret | Visit https://explore.openaq.org → create account/sign in → account settings → API key; review limits and data license | No AWS permission locally; ingestion GetSecretValue later | User environment/ignored .env; later Secrets Manager ecoroute/dev/openaq | After adapter exists, HTTPS GET https://api.openaq.org/v3/locations?limit=1 with X-API-Key header; log only status/count, never headers | Provider quotas/plan may apply; not called in Phase 0 |
| WEATHER_API_KEY, ENABLE_WEATHER | Optional; key secret | Provider not selected. Choose source with historical forecast availability/license first; obtain developer API key in that provider account only after review | None locally; selected secret GetSecretValue later | Local environment / Secrets Manager | Presence-only now; provider-specific authenticated probe deferred | Provider-dependent; no contract or paid plan chosen |
| POLLUTION_SECRET_ARN | Required only for AWS ingestion of keyed provider; ARN not secret, value secret | Secrets Manager → Store a new secret → Other type → provider key → encryption key → name ecoroute/dev/openaq; no placeholder secret provisioned | Operator CreateSecret/TagResource; workload GetSecretValue exact ARN, KMS decrypt if CMK | Secret value only in Secrets Manager; ARN in runtime config | DescribeSecret metadata; later ingestion smoke test without printing value | Secret-month + reads |
| S3_DATA_BUCKET | Required AWS data phase; name no, data may be sensitive | Approved CDK creates; S3 → Buckets → selected bucket → Properties/Permissions; record name | Operator scoped s3 create/config; runtime prefix GetObject/PutObject | Non-secret CDK output/runtime config | HeadBucket with permitted bucket access; encryption/public-access settings; synthetic round trip after approval | Storage/requests/egress |
| DYNAMODB_TABLE_NAME | Required AWS state phase; no | Approved CDK creates; DynamoDB → Tables → table → Overview | Operator scoped CreateTable/DescribeTable and config; runtime item/query actions | Runtime config | DescribeTable, TTL settings; conditional write test with synthetic item after approval | Capacity/storage |
| SQS_INGEST_QUEUE_URL | Required AWS ingest; no | Approved CDK creates queue + DLQ; SQS → queue → Details URL | Operator CreateQueue/SetQueueAttributes; runtime producer/consumer actions | Runtime config | GetQueueAttributes, verify DLQ/visibility; later synthetic message | Requests/polling |
| COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID | Required before public private-data endpoints; no | Cognito → User pools → Create user pool/app → public client (no secret), auth-code+PKCE; approved callback URLs/scopes before enabling; copy IDs from overview/app client | Deployment CreateUserPool/CreateUserPoolClient and scoped configuration; client OAuth no developer IAM keys | Config; user tokens only secure client storage | Validate issuer JWKS, audience, expiry, access-token scopes; reject other-user access in tests | MAUs/tier/email/SMS |
| Scheduler schedule / Lambda / HTTP API IDs | Required AWS deployment, not local; no | Generated by reviewed Python CDK; inspect CloudFormation Outputs and service Console, not manual parallel infrastructure | Deployment role scoped to synthesized resources; scheduler PassRole constrained to execution role | CDK outputs/config | Resource status, scheduled synthetic task, JWT smoke tests after approval | Invocation/request/log charges |
| SNS topic ARN and subscriptions | Optional user alerts; subscriber email personal | SNS → Topics → Standard → create approved topic → Subscriptions → Email → confirm email yourself | Operator CreateTopic/Subscribe; publisher Publish exact topic | ARN in config; subscribers in SNS | Confirmed subscription, approved test publish | Delivery dependent; SMS disabled initially |
| WEARABLE_MODEL, phone OS, companion app/version | Required before watch integration; no | Watch Settings/About and installed companion app info; user reported Noise Pro 3 Alpha | None | Local project notes without serial identifiers | Inspect actual available export/bridge capability; official API not verified | No AWS charge |
| WEARABLE_CLIENT_ID/SECRET, ENABLE_WEARABLE | Optional; secret sensitive; currently unavailable | No verified Noise developer portal/API: do not create or extract tokens. If a documented vendor API becomes available, register there and approve exact scopes/callbacks | Provider OAuth scopes; secret access only in adapter role | Secret Manager / local environment; tokens never Git | Provider-specific OAuth/import test only after capability verification | Provider-dependent |
| IOT_ENDPOINT, IOT_THING_NAME, IOT_CERT_PATH, IOT_PRIVATE_KEY_PATH, IOT_ROOT_CA_PATH | Optional supported hardware only; private key secret | IoT Core → Manage → All devices → Things → Create → certificate; download unique device private key securely once; attach narrowly scoped IoT policy; endpoint under Settings | Operator CreateThing/CreateKeysAndCertificate/CreatePolicy/AttachPolicy/AttachThingPrincipal/DescribeEndpoint; device Connect/Publish policy | Device secure storage; local private files outside repo, env contains paths only | TLS MQTT connect + synthetic publish on exact device topic after approval; test rejection of other topics | Connections/messages/rules |
| SAGEMAKER_EXECUTION_ROLE_ARN | Optional managed ML; no secret | Approved IAM role with trust sagemaker.amazonaws.com; SageMaker AI → Training → jobs later; no Studio domain needed | Launcher training actions + scoped PassRole; role S3/ECR/log access | CDK config | Role trust, S3 policy, instance quota; one bounded job only after estimate/approval | Yes instance time/storage |
| BEDROCK_MODEL_ID | Optional; no secret | Bedrock → Model catalog → selected model → regional availability/access terms; prefer same-region model | bedrock:InvokeModel selected model/profile; model/provider access prerequisites may differ | Non-secret config | List/catalog availability is not invocation entitlement; approved minimal call later | Tokens; Marketplace terms may apply |
| CDK_BOOTSTRAP_QUALIFIER, CDK_TOOLKIT_STACK_NAME | Required before later CDK deployment; no | CloudFormation → CDKToolkit → Outputs/Resources; SSM Parameter Store → /cdk-bootstrap/qualifier/version | DescribeStacks, ssm:GetParameter; bootstrap operator policy reviewed separately | Non-secret environment/config | Diagnostic stack health + parameter; absence is not permission to bootstrap | Bootstrap S3/ECR storage can bill |
| Database URL/password | Optional deferred PostGIS; password secret | No DB now. Later local Docker secret or approved RDS PostgreSQL private DB and least-privilege DB role | SQL grants; optional rds-db:connect; scoped secret read | Secret Manager/local environment, never connection URL in logs | TLS connection/migration/spatial query after approval | RDS instance/storage/backups |
| GitHub identity and collaborator access | Required for team publishing; token secret | Owner already authenticated via gh secure keyring; repo Settings → Collaborators → add Mayank2142 and DEVESH859; invitations must be accepted | Repo administration to invite, write for code; CI contents:read | Git Credential Manager/gh keyring, separate OS sessions | gh repo view; collaborator invitation status; git log author | Private Actions quotas may bill if exceeded |

## 3. Exact local configuration before Phase 1

From the repository directory in PowerShell:

```powershell
Copy-Item .env.example .env
# Edit .env locally: ECOROUTE_PROFILE=local, PROJECT_NAME=ecoroute-ai,
# TARGET_CITY=Delhi, AWS_REGION=ap-south-1, EXPECTED_AWS_REGION=ap-south-1.
# Keep all ENABLE_* flags false. Blank values use safe app defaults.
aws configure sso --profile ecoroute-dev
aws sso login --profile ecoroute-dev
$env:AWS_PROFILE = 'ecoroute-dev'
$env:AWS_REGION = 'ap-south-1'
$env:EXPECTED_AWS_REGION = 'ap-south-1'
$env:EXPECTED_AWS_ACCOUNT_ID = '<your account ID>'
# Set MONTHLY_BUDGET_USD and BUDGET_NAME only after selecting your alert threshold.
.\.venv\Scripts\python.exe scripts/diagnose.py --aws --profile ecoroute-dev --region ap-south-1
```

Diagnostics intentionally reads **process environment**, not .env. The application reads .env.
Do not paste secrets into PowerShell command history; edit ignored .env in a local editor or use
your OS secret tooling. AWS temporary credentials should remain in the CLI provider chain.
Offline Phase 1 development can proceed without AWS, OpenAQ or watch credentials. Real-data work
must wait for each relevant gate. Do not run cdk bootstrap/deploy, enable models or start training yet.
