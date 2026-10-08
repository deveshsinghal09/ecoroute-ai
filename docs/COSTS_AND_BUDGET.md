# Cost estimate and AWS Budget proposal

2026-10-08. **No budget or resource created. User authorizes up to reported US$100 credits for the project; specific deployment approval remains required.**
User reports a Free Tier hackathon account with **US$100 AWS credits**. This is the user-authorized overall credit ceiling, not a spending target or proof that a specific deployment was approved. Balance is not independently verified; expiry, eligible services and
cash-spend tolerance are unknown. Do not assume AWS usage is free or credits cover all charges.
AWS bills may show USD-equivalent usage and local taxes/conversion; confirm actual billing currency.

## Low-traffic monthly planning scenario

Assumptions: one Mumbai environment, 10,000 API calls, 1,000 Location requests, 50 testers,
100,000 total Lambda invocations at 512 MB and 1 second average, 1 GB S3, 10,000 PUT/100,000 GET,
100,000 DynamoDB reads/writes of small items, 3,000 ingest tasks, 0.5 GB logs, one provider secret.
These are hypothetical sizing inputs, not measurements. Ranges below are conservative allowances,
not verified Mumbai SKU quotes; exact pricing and request tier must be repriced before deployment.

| Component | Planning allowance USD/month | Cost driver |
|---|---:|---|
| API Gateway HTTP API | 0.01–0.10 | 10k requests Ã— regional request rate |
| Lambda API + ingest | 0.85–2.00 | 50k GB-seconds + 100k requests; reference x86 compute around $0.0000166667/GB-s and $0.20/million requests, region/architecture dependent |
| Amazon Location | 0.50–2.00 | 1k requests Ã— selected route pricing bucket; advanced features may change billing |
| S3 | 0.10–0.50 | GB-month + object operations, versions/egress additional |
| DynamoDB on-demand | 0.10–0.50 | rounded read/write request units + storage; do not apply provisioned free allowance blindly |
| Scheduler + SQS | 0.01–0.20 | invocations plus send/receive/delete and polling |
| CloudWatch | 0.50–2.00 | ingestion, retention, alarms and custom metrics |
| Secrets Manager | 0.40–0.60 | one secret-month and reads; cache appropriately |
| Cognito + SNS email allowance | 0–1.00 | account tier/MAUs and notification delivery; no SMS |
| Bootstrap storage / small data transfer | 0.10–1.00 | assets, object versions and internet transfer |
| **Core subtotal** | **2.57–9.90** | Before tax, external providers, credits and any free allowances |

Use a **$10–15/month planning envelope** for this bounded demo, not a guaranteed maximum.
For example 100,000 route requests instead of 1,000 multiplies the Location line by 100.
Public abuse, retries, logging and continuous polling can exceed this estimate.

Deferred-service incremental allowances: Step Functions $0–1 for small workflows; bounded
SageMaker training $1–10 per experiment depending on instance/duration (not an approved SKU);
Bedrock $0–5 only with chosen model/token cap; a small IoT demo $0–1 depending on messages/connections.
These are excluded from the subtotal. Fargate plus ALB/networking can add tens of dollars per month;
RDS similarly introduces continuous compute/storage costs. ECR adds storage/optional scanning.
Obtain exact region/instance/model quote before enabling any deferred service.

## Budget proposal and steps (not executed)

Propose a monthly USD **10** gross-usage cost budget, as an early-warning threshold within the $100 overall credit ceiling, with
actual-spend alerts at 50%, 80%, 100% and a forecast alert at 100%. Also create an account-wide
budget (not just region/tag filtered) to catch unexpected-region resources. If account is shared
with other projects, choose a separate total threshold rather than silently using $10 for all work.
Project tag filters are supplementary and require cost-allocation-tag activation/propagation.

Authorized billing operator: Console → Billing and Cost Management → Budgets → Create budget →
Customize → Cost budget → monthly recurring → fixed amount → USD/selected amount. Use unblended
cost, review advanced cost inclusions, and **exclude credits/refunds** for the gross-usage alert
so credits do not hide resource consumption. Optionally maintain a second net-payable view.
Add each actual/forecast threshold and an email subscriber; review and create only after approval.
Inspect notification settings and recipient address. Direct budget email does not require SNS;
an SNS integration instead requires a topic policy permitting budgets.amazonaws.com to publish.
Set BUDGET_NAME and MONTHLY_BUDGET_USD locally to match. Verify using DescribeBudget and Console.

Budgets notifications lag usage and **do not hard-cap costs**. An email reaching 100% does not stop
resources. Budget Actions, if later selected, also have latency and are not universal spend caps.
Use application rate limits, Lambda reserved concurrency, bounded schedules/retries, per-user
request limits, retention and explicit service disable switches. A deny policy on provisioning
does not stop already-running billable resources. Pause ingest and remove unnecessary deployed
resources in a reviewed teardown; retain or delete user data deliberately.

Sources: [Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[API Gateway](https://aws.amazon.com/api-gateway/pricing/),
[Location](https://aws.amazon.com/location/pricing/), [DynamoDB](https://aws.amazon.com/dynamodb/pricing/),
[S3](https://aws.amazon.com/s3/pricing/), [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/),
[Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/),
[Budget behavior](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

## Concrete Phase 1/2 deployment proposal (not executed)

Resources are inventoried in AWS_SERVICES.md. No routing requests, ML jobs, NAT Gateway,
Fargate, RDS or IoT traffic are in this template. Reuse the $10-15/month conservative allowance
for <=10,000API calls, hourly model collection for one Delhi cell, <=1GB environmental data,
small user tables and <=0.5GBlogs; provider costs/taxes are separate. The allowance is not a
verified regional quote. Six CloudWatch alarms, SQS polling, retained/bootstrap assets and any
Secrets Manager secret can cost money even at very low API traffic. Reprice using the official
pricing links before requesting deployment approval, then state the selected assumptions.

Keep a $10 monthly gross-cost early-warning budget plus an account-wide $100 ceiling-warning
budget (actual alerts50/80/100% and forecast100%). Credit expiry or ineligible services can
cause a cash bill below $100. Confirm billing-console credit balance/eligibility and alert email;
neither is verified. Alerts do not stop resources. Do not consume credits merely to show usage.

A NAT Gateway is intentionally absent: at a hypothetical $0.045/hour,730hours alone would be
$32.85/month before data processing/public IPv4; this is arithmetic illustration, not a Mumbai
SKU quote. Lambda outside a VPC can reach provider APIs without that recurring gateway.

## Phase 3 cost update (2026-10-09)

No AWS resources deployed or measured bill obtained. Routing reuses the existing API Lambda,
data bucket and route_metadata/environment tables; no NAT Gateway, ECS service or database server.
Uncached coordinate comparison uses one CalculateRoutes request; two textual endpoints add
up to two Geocode requests (Storage intended use). Three-departure analysis can require five
requests. Default application budget is 100 calls/day and 30/hour, including failed attempts;
cache reuse 5min reduces repeats but does not cap spending elsewhere in the account.

Add `route calls × current Mumbai Core rate + stored geocodes × current Mumbai Storage rate`
to the existing small-demo estimate above, plus incremental S3/DynamoDB/API/Lambda/log usage.
Exact regional unit prices, credit eligibility/expiry and taxes remain deployment prerequisites;
the old planning envelope is not an all-inclusive quote. Review the [Location price page](https://aws.amazon.com/location/pricing/)
and [billing categories](https://docs.aws.amazon.com/location/latest/developerguide/routes-pricing.html)
when preparing the concrete deployment approval. Budget alerts do not hard-cap costs.
