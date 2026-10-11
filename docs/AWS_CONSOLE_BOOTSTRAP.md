# EcoRoute one-time Console setup — 2026-10-11

Latest: logging fix installed; Core rollback failed reading Lambda event mapping. Current file
adds lambda:GetEventSourceMapping on Resource* with Mumbai condition to Compute execution
policy only. Update CDKToolkit with current file; expect Modify EcoRouteExecuteCompute only.
Core workflow explicit name fixed in code, no new IAM permission needed. After update, agent
must inspect/recover ROLLBACK_FAILED; do not manually delete mapping/pools or other stacks.


## Latest correction: HTTP API access log delivery

Stage tagging fix is installed and passed. AWS now denies logs:CreateLogDelivery.
Current file adds seven explicit log-delivery/resource-policy administration actions,
Resource* with RequestedRegion=ap-south-1, to EcoRouteExecuteCompute only. AWS documents
these account-level permissions for HTTP API logging; runtime roles do not receive them.
Update existing CDKToolkit with current file; expect only Compute policy modification,
keep parameters/options, acknowledge IAM and wait UPDATE_COMPLETE. No paid plan or additional
service is enabled; log retention/settings remain unchanged.
Source: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-logging.html


## Latest correction: API Gateway stage handler

Cognito fix is installed. Core now fails at API Gateway stage tagging despite documented
HTTP IAM actions being present. Current file adds apigateway:* ONLY for Mumbai stage collection
and stage paths (/apis/*/stages, /apis/*/stages/*), conditioned on Mumbai. This compatibility
exception covers the live handler's TagResource requirement missing from published action
catalog; no wildcard across every API resource/service. Optional-tag removal failed in a real
retry and was reverted. Template lint passes; deployment not yet verified.
Update existing CDKToolkit with current file, expect Modify EcoRouteExecuteCompute only,
retain settings, acknowledge named IAM and wait UPDATE_COMPLETE. CLI cannot change policy.


## Current correction after partial deployment

Data/ML deployed after the SSM fix. Core failed on Cognito SetUserPoolMfaConfig. Current
regenerated file adds GetUserPoolMfaConfig/SetUserPoolMfaConfig to EcoRouteExecuteCompute,
restricted to Mumbai user pools tagged Project=ecoroute-ai. Update existing CDKToolkit by
replacing its template with this file, retain parameters/options, review Modify
EcoRouteExecuteCompute (no replacement), acknowledge IAM, submit and wait UPDATE_COMPLETE.
Core failed-stack recovery must wait for rollback; do not independently recreate resources.

CloudFront separately requires AWS account verification. Open AWS Support Center and create
an account/billing case for CloudFront verification; include the exact error and request ID
in PROJECT_STATE.md. No Support case was sent by the agent; no plan upgrade is authorized.


## Latest: update the completed bootstrap

CDKToolkit CREATE_COMPLETE/version32 is now CLI-verified. The first app change set failed
because the CloudFormation execution role could not read the bootstrap version through
ssm:GetParameters. The regenerated file adds only GetParameter/GetParameters on that exact
SSM parameter to EcoRouteExecuteStorage; no new service, parameter writes or wildcard grants.
No EcoRoute application stack exists yet.

In Mumbai CloudFormation, select existing CDKToolkit, choose Update stack / Make a direct
update, Replace current template, Upload a template file, then select the regenerated
work/EcoRouteBootstrap.console.json. Keep existing stack name/parameters/options, acknowledge
named IAM resources and submit. Review the change: EcoRouteExecuteStorage policy update only.
Wait for UPDATE_COMPLETE, then resume the already-approved application deployment. Use an
authorized IAM operator; the CLI developer cannot modify these bootstrap managed policies.


Budget creation is user-confirmed. Latest reviewed amount is USD50 monthly with actual
50/80/100% and forecast100% email alerts, no actions. CLI budget verification still returns
AccessDeniedException. User's Console reports a Free plan, USD119.88 credits and displayed
plan end Dec12,2026; individual credit eligibility/expiry remain separate. Original USD100
project ceiling and approved USD5–20/month serverless scope remain unchanged.

## Current blocker

The dev-admin profile is the verified IAM user devesh_eco in account112920804206, Mumbai.
EcoRouteReadiness works, but resource creation/role creation/PassRole still simulate denial.
CDKToolkit and all five EcoRoute stacks are absent. An authorized Console operator must perform
the one-time IAM/bootstrap setup; login or a read policy cannot authorize it automatically.
Do not grant AdministratorAccess or every service's FullAccess to the development user.

The prepared file is:

`C:\Users\DELL\Documents\Codex\2026-10-08\act-as-a-senior-aws-solutions\outputs\ecoroute-ai\work\EcoRouteBootstrap.console.json`

It contains no secrets. It derives from the repository-locked AWS CDK CLI2.1145.0 bootstrap
template, replaces the broad execution/lookup/deploy permissions and limits the environment
with CloudFormation account/region rules. The CDK variant marker prevents accidental overwrite
by a later default bootstrap. Generated local files are ignored; the reviewed generator is tracked.

## Console steps

1. Use an authorized IAM operator/role in account **112920804206**. Select **Mumbai/ap-south-1**.
2. Open **CloudFormation → Stacks → Create stack → With new resources (standard)**.
3. Choose **Choose an existing template → Upload a template file**, select the JSON above,
   and choose **Next**. Console template upload may create/use its own regional template S3 bucket.
4. Set **Stack name = CDKToolkit**. Keep the remaining default parameters. Storage encryption,
   private access, same-account trust and qualifier have already been fixed in the template.
5. On stack options, keep ordinary defaults; leave the optional execution role blank only if
   the current authorized operator already has the required provisioning permissions below.
   Alternatively choose the operator's already reviewed provisioning role. Do not invent a role ARN.
6. Review the resources and acknowledge **IAM resources with custom names**, then submit.
   This is within the previously approved bounded bootstrap scope; no new training approval is implied.
7. Wait for **CREATE_COMPLETE**. If it fails, copy the first relevant FAILED Events reason only,
   without credentials. Review retained policies before any retry; do not delete other stacks/buckets.
8. Reply with the actual stack status. The backend/app stacks are deployed afterward using existing CDK.

The Console operator needs CloudFormation CreateStack/DescribeStackEvents/DescribeStacks;
IAM CreateRole/PutRolePolicy/CreatePolicy/AttachRolePolicy/AttachUserPolicy and corresponding
read/tag operations on these named bootstrap roles/policies/user; S3 create/configure the CDK
asset bucket and template upload access; ECR create/configure the CDK asset repository; and
SSM PutParameter for /cdk-bootstrap/hnb659fds/version. These are one-time administrative
permissions, separate from the limited daily developer policy. If denied, an already authorized
account IAM operator must grant/run this setup; the current CLI user cannot self-grant it.
Account plan, organizational restrictions and available service quotas can still block actions.
Do not upgrade the plan or change organization membership as an automatic workaround.

## What this setup creates

| Resource | Purpose / cost |
|---|---|
| One private, versioned CDK S3 asset bucket, bucket policy | Lambda assets; storage/request charges when used, no public write |
| One private CDK ECR asset repository | Future container assets; storage/scanning when used |
| Five CDK roles and their scoped policies | File/image publishing, limited lookup, project deployment and CloudFormation execution; IAM has no standing usage fee |
| Four named execution managed policies | Storage, compute/auth, automation/hosting and constrained workload IAM |
| EcoRouteWorkloadBoundary | Maximum permissions for application roles, layered with existing narrower CDK workload policies |
| EcoRouteCdkDeployer attached to devesh_eco | Assume only four specific CDK roles plus metadata and exact-budget reads; no direct CloudFormation execution-role assumption |
| One SSM bootstrap-version parameter | CDK deployment prerequisite |

No Lambda/API/Cognito/DynamoDB/IoT/SageMaker application resource is created by this file.
No customer-managed KMS key, paid training job, endpoint, SMS or active schedule is created.
An empty bootstrap has negligible storage usage, with request/storage costs once assets are
uploaded; it is included in the USD5–20/month planning allowance, not a guaranteed hard cap.
Global IAM, CloudFront and Budgets permissions do not incorrectly require a Mumbai endpoint.

## Permission limits and verified checks

All new policy actions are explicit and were checked against the official AWS IAM action catalog.
Application resources use EcoRoute stack-derived names/account/Mumbai scope. IAM role creation
requires the exact workload boundary; the execution policies cannot change that boundary,
change the human's policies, modify CDK bootstrap roles or create a user. The boundary denies
unrelated S3/DynamoDB/secret access through its limited Allow set and contains no training-job
permission. It does not replace Cognito ownership/consent enforcement or grant permissions itself.

Documented exceptions: UUID-based API Gateway resources use Mumbai /apis paths; existing
Cognito/CloudFront management uses account resources plus Project tags. CloudFront OAC
configuration/creation lacks resource-level IAM support. Lambda mapping creation uses Resource*
with lambda:FunctionArn constrained to EcoRoute functions. Token, stream-list and metadata APIs
without resource-level support have explicit actions/regional conditions. These exceptions are
execution-role configuration capabilities; they do not grant direct private application reads
to the development user. Tighten generated-ID resource grants after real deployment verification.

Actual checks: 8 AWS IAM simulations under controlled request contexts matched expected
Allow/implicitDeny decisions; this did not install/grant any policy. Offline five-stack CDK synth
passed with all12 application roles bounded, zero reserved Lambda concurrency, disabled collection/
workflow schedules and IoT rule. CFN-lint reports no errors/warnings for the final bootstrap.
AWS ValidateTemplate itself is AccessDenied, so live server validation/provisioning is pending.
Structural app security review passed with zero findings. These checks do not prove runtime access,
service entitlement, deployment success, actual notification delivery or model performance.

## CLI continuation after verified bootstrap

```powershell
Set-Location 'C:\Users\DELL\Documents\Codex\2026-10-08\act-as-a-senior-aws-solutions\outputs\ecoroute-ai'
aws cloudformation describe-stacks --stack-name CDKToolkit --profile dev-admin --region ap-south-1 --query 'Stacks[0].StackStatus'
aws ssm get-parameter --name /cdk-bootstrap/hnb659fds/version --profile dev-admin --region ap-south-1 --query 'Parameter.Value'
aws budgets describe-budget --account-id 112920804206 --budget-name EcoRoute-Gross-Usage --profile dev-admin --query 'Budget.{Limit:BudgetLimit,Period:TimeUnit,Filters:CostFilters,CostTypes:CostTypes}'
```

Before app deployment, rebuild the current Linux Lambda asset, verify enabled Free-plan
services and review current package/Cognito/callback/CORS/provider context. Use the exact
boundary context; the wrapper rejects omission for this custom bootstrap before creating app resources.
The generated work/aws-deploy.context.json initially contains that ARN only. Add non-secret
provider secret ARNs and exact HTTPS CORS/callback URLs only after those resources/URLs exist.
Never put key values in it or a VITE variable. A secret must be named beneath ecoroute/ to fit
the boundary; the actual Lambda identity still needs the narrower exact-secret CDK grant.

```powershell
# Provisioning step, run after verifying bootstrap/permissions/plan and current configuration.
# Bounded deployment approval already exists; paid jobs/SMS/continuous workflows remain excluded.
.\.venv\Scripts\python.exe scripts/manage_cloud.py deploy --apply --accept-estimated-charges --profile dev-admin --region ap-south-1 --expected-account-id 112920804206 --deployment-config config/hackathon.aws.json --iot --workflows --context-file work/aws-deploy.context.json
```

SageMaker ml.m5.large quota0 still blocks training, not execution-role/ECR preparation. Sufficient
real measured history, Docker/image review, quota1 and separate training-job approval remain required.
Gemini provides explanations only. Live Noise health telemetry remains dependent on an authorized
supported bridge and real readings; IoT resources alone cannot decode an undocumented watch protocol.

## Regeneration and retaining cleanup

```powershell
.\.venv\Scripts\python.exe -m pip install --target work/bootstrap-tools -r requirements-bootstrap.txt
.\.venv\Scripts\python.exe scripts/prepare_aws_bootstrap.py --account 112920804206 --region ap-south-1
$env:PYTHONPATH = "$PWD\work\bootstrap-tools"
.\.venv\Scripts\python.exe -c 'from cfnlint.runner import main; main()' -t work/EcoRouteBootstrap.console.json -r ap-south-1
```

These commands are offline generation/validation, not provisioning. Tools are not added to the
application/Lambda runtime. Do not run plain cdk bootstrap over this custom stack. Later app
teardown deliberately retains user-data buckets/tables/pools; bootstrap assets and these managed
policies are also retained. Retaining IAM policies attached to the user requires a reviewed
detach/delete step by an authorized operator when deployment access is no longer needed.
Do not delete bootstrap while deployed stacks still depend on it. No cleanup ran in this update.

Official references: [CDK customization](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping-customizing.html),
[CDK security](https://docs.aws.amazon.com/cdk/v2/guide/best-practices-security.html),
[permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html),
[Lambda action scopes](https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html),
[CloudFront tagged creation](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_CreateDistributionWithTags.html),
[S3 ownership deletion permission](https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeleteBucketOwnershipControls.html).
