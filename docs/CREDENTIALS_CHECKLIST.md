# Credentials and configuration checklist

## Optional hosting/compute/SQL setup — 2026-10-10

User deferred credentials; no authenticated AWS verification or deployment this update.
Configure names only in ignored deployment JSON and retain secrets in CLI providers/Secrets
Manager. [Complete setup table](MULTISERVICE_INTEGRATION.md#credential-and-prerequisite-setup-configure-later)
lists purpose, sensitivity, Console steps, IAM, storage, verification and charges for:
ECOROUTE_DEPLOY_CONFIG, image_uri, sql_image_uri, regional_certificate_arn, backend_origin,
eks_version, eks_operator_arn, eks_admin_cidrs, existing_apprunner_customer,
api_gateway_origin, domain_name, hosted_zone_id, hosted_zone_name,
cloudfront_certificate_arn, sql_writer_secret_arn and supported postgres_version.
Hosting also needs deployed FrontendBucket/DistributionId or AmplifyAppId and existing
public VITE API/Cognito configuration. No secret AWS key is required in these files.
RDS needs the official public CA bundle built into its SQL Lambda image and a private admin
session to initialize schema/restricted user; Aurora supports approved Data API initialization.
EKS needs operator apply and HTTPS ingress; App Runner is closed to new customers.
Default Lambda does not need these optional identifiers. All live access, quota, credit,
IAM/bootstrap and publication checks remain pending manual configuration and approval.

Frontend configuration (public identifiers only): VITE_API_BASE_URL, VITE_COGNITO_DOMAIN,
VITE_COGNITO_CLIENT_ID, VITE_COGNITO_REDIRECT_URI in frontend/.env.local. These are exposed in
the browser; NEVER store provider keys, AWS keys, private certificates or tokens in VITE_ values.
Existing Cognito public client must enable authorization-code PKCE, custom read/write scopes and
the exact callback URL. Set CDK callback_urls and frontend_origins (exact HTTPS origins); local
FastAPI uses CORS_ORIGINS=["http://127.0.0.1:5173"]. See frontend/README.md. No setup/deployment
was performed. Historical preview and the illustrative 3D city need no credentials.

Phase7 current status: user deferred further credential setup; no authenticated AWS checks or
deployment performed. Existing rotated OPENAQ_API_KEY authenticated successfully for two bounded
sensor queries (zero observations returned); key stays in ignored local configuration. Public
Open-Meteo service returned192records without a key. No credentials appear in exported examples.

Remaining names/unverified prerequisites: AWS_PROFILE, AWS_REGION, EXPECTED_AWS_ACCOUNT_ID,
CDK bootstrap/deploy IAM, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, approved callback_urls,
JOURNEYS_TABLE, PREFERENCES_TABLE, ROUTE_METADATA_TABLE, IDEMPOTENCY_TABLE, ALERTS_TABLE,
ENVIRONMENT_TABLE, WEARABLES_TABLE, S3_DATA_BUCKET, SQS_INGEST_QUEUE_URL, OPENAQ_SECRET_ARN,
BEDROCK_MODEL_ID, SNS_ALLOWED_TOPIC_ARNS, SMS_ENTITY_ID, SMS_TEMPLATE_ID, SMS_SENDER_ID,
WORKFLOW_STATE_MACHINE_ARN, ML_INFERENCE_FUNCTION_ARN, SAGEMAKER_EXECUTION_ROLE_ARN,
reviewed ML image/model/dataset, IOT_DATA_ENDPOINT and IOT certificate/key paths.
Selected profile/region/account are configured locally but live grants remain unverified;
service-specific identifiers are required only when that integration is enabled.
Do not use root. Keep AWS temporary credentials in the CLI provider, secrets in ignored .env
or Secrets Manager, device keys in protected keystores. Exact creation/IAM/verification steps
remain below and in ML_WORKFLOW.md, WEARABLES.md and PHASE6_ADVISORIES.md.
Budget alerts never hard-cap costs; approve charges before manage_cloud.py deploy --apply.

Phase5: confirmed Noise ColorFit Pro3 Alpha / NoiseFit Assist; OS/export API/Health Connect
capabilities unverified. No hardware credentials are requested. [Wearable setup](WEARABLES.md#credentials-iam-and-exact-enrollment-steps)
lists every required/optional identifier, purpose, sensitivity, Console steps, minimum IAM,
secure storage, verification and billing: Cognito login/IDs; WEARABLES_TABLE/S3_DATA_BUCKET;
IoT ATS endpoint, exact Thing/policy, public certificate and private bridge key; role/binding,
quotas and budget. No Phase5 authenticated AWS action was executed and no IoT credential exists.
IOT_*_PATH variables are private local file paths, not key contents. Prefer protected device
keystore/CSR generation. Never paste a certificate private key, JWT or AWS secret into chat.

Phase 4 update (2026-10-10): dev-admin / devesh_eco and ap-south-1 remain selected. Read-only
diagnostics verified STS, but Lambda access is denied and CDK bootstrap/training quotas are
unverified. There is no SageMaker execution role, approved ML bucket/image or deployed worker.
No paid ML action has been attempted. User confirmed OpenAQ key rotation on2026-10-10 IST;
live authentication, bounded station discovery and five-observation ingestion passed using
local configuration. Never send the replacement in chat. AWS Secrets Manager is not deployed.

See [ML prerequisites and exact Console/CLI steps](ML_WORKFLOW.md#credentials-and-minimum-iam)
for every Phase 4 identifier, sensitivity, mandatory/optional status, IAM boundary, secure storage,
verification and charge implications: expected account/profile/region, ML bucket, execution role,
regional ECR image digest, SageMaker quota, optional workflow/inference ARN and budget alerts.
ML_LOCAL_ROOT is a local path; ML_INFERENCE_FUNCTION_ARN is a non-secret deployed worker ARN.
Keep configuration in ignored .env; cached AWS credentials stay in the AWS credential provider.
External provider secrets belong in Secrets Manager, never dataset/model artifacts or images.

Never paste keys, passwords, session tokens, private certificates or provider tokens into chat.
Current status (2026-10-09): selected profile `dev-admin` authenticates as IAM user
`devesh_eco`. User confirms this account holds the hackathon credits. Region ap-south-1 and
expected account are configured in ignored .env. The old default/root profile belongs to a
different account and is no longer used. STS succeeds; Routes V2, Places V2 and Lambda checks
are denied. Bootstrap, quotas and account service access remain unverified. No deployment.
Cognito IDs/login, budget/alert recipient and scoped workload/deployment permissions are missing.
An OpenAQ key was disclosed in chat: revoke it and configure a replacement locally; the exposed
value was not saved or used. Open-Meteo eligible noncommercial access requires no key.

For the existing profile, run `aws sts get-caller-identity --profile dev-admin --region ap-south-1`.
No new AWS key is required. ROUTING.md contains exact Location policy attachment and verification
steps. The Identity Center guide below is an optional migration to individual temporary sessions,
not a requirement to discard the already configured profile.

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

## Phase 1/2 exact setup gates

1. **Scoped account access:** use dev-admin in ap-south-1. STS is verified; Location and
   Lambda calls are denied and bootstrap cannot be verified. Required diagnostic actions are
   listed in AWS_SERVICES.md; an authorized operator must review the user policy, permission
   boundary and applicable SCP. Identity verification does not imply service authorization.
   `aws lambda get-account-settings --profile dev-admin --region ap-south-1` requires
   lambda:GetAccountSettings; `aws cloudformation describe-stacks --stack-name CDKToolkit
   --profile dev-admin --region ap-south-1` requires cloudformation:DescribeStacks. These only read.
2. **Existing human profile:** AWS_PROFILE=dev-admin, AWS_REGION=ap-south-1 and the verified
   EXPECTED_AWS_ACCOUNT_ID are configured locally. Credentials are sensitive and stay under
   CLI management, not Git. Keep MFA and prefer temporary sessions. Renew using the existing
   authorized login mechanism. No IAM permission changes or paid provisioning are authorized
   merely by configuring a profile. The app rejects root identities for real local routing.
3. **OpenAQ key (mandatory only for OpenAQ, sensitive):** visit https://explore.openaq.org/,
   sign up/login, open account settings/API keys and obtain the API key. Store as OPENAQ_API_KEY
   in ignored local .env or a process environment; no AWS permission is needed for local use.
   Run `python scripts/ingest_air.py --source openaq --stations --max-pages 1` to verify auth and
   actual Delhi coverage without printing the key. Inspect returned station licenses before
   redistribution. Standard plan quotas apply; paid/provider plans require separate review.
4. **Open-Meteo key (optional; sensitive for commercial service):** the free noncommercial endpoint
   needs none. Commercial use: open https://open-meteo.com/en/pricing, choose the appropriate
   plan, obtain customer key, store OPEN_METEO_API_KEY privately. The adapter selects the
   customer air-quality endpoint only when a key is present. Verify via the same CLI model ingest,
   which prints counts/keys only. Paid subscription charges may apply outside AWS credits.
5. **Provider secret ARN (optional until AWS OpenAQ, non-secret identifier; value sensitive):**
   after approved deployment setup, Secrets Manager in Mumbai -> Store a new secret -> Other
   type -> key api_key, enter the provider value locally -> aws/secretsmanager encryption ->
   name ecoroute/openaq -> store. Operator needs secretsmanager:CreateSecret/TagResource (and
   PutSecretValue for rotation); collector needs GetSecretValue on that secret only. Default
   managed encryption avoids an extra customer KMS key; custom KMS requires scoped Decrypt.
   Copy the ARN only into CDK context provider_secret_arn; CDK sets OPENAQ_SECRET_ARN on collector.
   Verify existence with `aws secretsmanager describe-secret --secret-id YOUR_ARN --profile YOUR_PROFILE
   --region ap-south-1` (DescribeSecret permission; no value output). Then invoke only a bounded
   approved ingest job to verify retrieval. Secret-month/API charges apply. OPEN_METEO_SECRET_ARN
   is supported by adapter code but no CDK grant is created for it; add a reviewed exact-ARN
   import/grant before enabling commercial Open-Meteo on AWS. No secrets are created by CDK now.
6. **Cognito IDs and callback URL (mandatory for protected live API, non-secret):** after approved
   Core deployment, use stack UserPoolId/ClientId outputs or Cognito -> User pools -> EcoRoute
   pool -> App integration -> app client. In CDK context callback_urls set an exact HTTPS callback
   for your chosen OAuth test client (localhost callback only for a controlled local client).
   Without callback_urls the client has OAuth disabled, so custom scopes cannot be obtained via
   a basic SRP login. Configure authorization-code flow with PKCE, openid, ecoroute/read/write.
   Operator needs cognito-idp:AdminCreateUser for demo users; app runtime has no Admin permissions.
   Complete login yourself, store short-lived access token only locally, configure pool/client
   in .env and call a protected endpoint. Never use an ID token as an API access token. MAU/email
   costs may apply. No pool, user, token or login has been created/tested against AWS yet.
7. **Deployed outputs (mandatory for AWS mode, non-secret):** copy table/bucket/queue outputs into
   matching .env names only for explicit live integration work. CDK supplies Lambda environments
   automatically. ENVIRONMENT_TABLE is the sixth table; S3_DATA_BUCKET stores raw and curated.
   Local mode needs none. Keep ECOROUTE_PROFILE=local until deployment is verified.
8. **Budget email and credit eligibility (mandatory before deployment, email is personal data):**
   inspect Billing -> Credits for remaining balance/expiry/services. Configure Budgets as described
   in COSTS_AND_BUDGET.md; permissions budgets:ViewBudget/ModifyBudget plus authorized billing
   console access. Store BUDGET_NAME/MONTHLY_BUDGET_USD locally, email in console. SNS -> Topics ->
   OperationalAlerts -> Create subscription -> Email -> enter your address, then confirm email
   yourself; requires sns:Subscribe exact topic. No subscription was created; alarms otherwise
   have no confirmed human recipient. Budget and SNS charges depend on features/delivery.

No secret must be printed to verify presence: Python can load dotenv and print only
`bool(os.getenv("OPENAQ_API_KEY"))`. The ingestion script redacts provider errors and does not
print request headers or customer URLs. Do not run CLI `--debug` when handling credentials.

Offline diagnostics: `python scripts/diagnose.py --region ap-south-1`.
Current IAM profile read-only check:
`python scripts/diagnose.py --aws --profile dev-admin --region ap-south-1`.
Set EXPECTED_AWS_ACCOUNT_ID privately to the account you verified first. This script only reads;
actual service entitlement, bootstrap execution boundary and costs still gate deployment.

## Phase 3 configuration gate

| Configuration | Use / required / sensitivity | Setup, permissions, storage, verification and cost |
|---|---|---|
| AWS_PROFILE=dev-admin; AWS_REGION=ap-south-1; EXPECTED_AWS_ACCOUNT_ID | Required real local routing; identifiers non-secret | Existing CLI profile verified via STS; identifiers in ignored .env, credentials in protected CLI files/cache; STS no direct charge |
| ENABLE_AWS_LOCATION | Optional local flag, required AWS adapter; non-secret | Set true only after the two actions in iam/location-read.json are granted by an authorized IAM operator; see ROUTING.md Console steps and billed demo command |
| ROUTING_PROVIDER; OSRM_BASE_URL | Optional fallback; non-secret | Default aws. Explicit osrm requires an operator-approved HTTPS origin with verified road profile/terms; no AWS IAM needed; provider hosting/request fees may apply; recorded fixture CLI needs no URL |
| LOCATION_DAILY_LIMIT; LOCATION_HOURLY_LIMIT | Spending safeguard; non-secret | Defaults100/30, configure lower locally; API Lambda receives these limits; DDB conditional UpdateItem on environmental table reserves attempts; quotas are not dollar caps |
| OpenAQ replacement key | Mandatory only for OpenAQ; secret | Revoke the chat-exposed key at provider account/API keys, create a replacement, save OPENAQ_API_KEY only in ignored .env; verify with one bounded station-discovery command above; never print the key or paste it into chat |

Preserve an existing .env. No request to paste any secret is part of setup. No key disclosed in
chat is committed or used for integration. The new replacement must be configured locally.
# Phase 6 deferred configuration

User explicitly deferred setup until after phases and selected SMS. No new credential values
are requested in chat. Missing/unverified: reviewed Converse-compatible regional model ID/ARN,
model entitlement/provider terms/quotas, dedicated SNS topic and verified subscriber, India
sender/entity/template IDs, account SMS spending settings, owned binding, workflow outputs,
deployment permissions/bootstrap and actual Cognito IDs. Existing IAM profile is not evidence
of any particular service permission. Root remains prohibited in development.

All names, mandatory/optional status, sensitivity, Console steps, verification commands,
least-privilege IAM, storage and possible charges are in the configuration table in
[PHASE6_ADVISORIES.md](PHASE6_ADVISORIES.md). Local settings go in ignored .env, not committed
source files; CLI credentials stay in temporary IAM/SSO cache; provider secrets remain Secrets
Manager references. No Bedrock/SNS API key is required. Verification and deployment are
separate, and live messages/model invocations need reviewed costs and approval.

Cinematic artwork is bundled in the frontend and needs no runtime credentials or image-generation
API key. Live Cognito/backend/provider configuration remains required as documented above.

## Google routing integration (2026-10-10)
See docs/GOOGLE_MAPS_SETUP.md (repository root) for separate server/browser keys, APIs, Cognito,
restricted secret IAM and verification. Google Routes/Places feed the existing exposure engine;
Journeys displays Maps JavaScript tiles and route overlays. No real Google service call verified.
Google comparisons are request-only; saved route-ID workflows are unavailable for those results.
No AWS resources were deployed. Google charges are separate from AWS credits.

Custom smartwatch preview requires no credentials. It does not connect to the Noise watch, AWS
IoT, health APIs or SNS. Existing authorized bridge/Cognito requirements still apply for real data.
