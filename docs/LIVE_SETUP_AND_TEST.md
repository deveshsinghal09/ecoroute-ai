# Cognito, routing, ingestion and alerts

## Create the first Cognito user

Use an authorized Console identity in Mumbai; do not create a new pool/client.
1. Cognito → User pools → select pool ID ap-south-1_mLkYYyq3G.
2. Users → Create user. Use your own email/user name.
3. Choose Don't send an invitation. Set a temporary password locally with at least14characters,
   uppercase/lowercase letters, a number and a symbol. Never send it to chat.
4. Create user. Open https://main.d3txif33djiy59.amplifyapp.com/.
5. Open the Settings panel → Sign in with Cognito, enter credentials, set permanent password.
6. Select Live services. Read my alerts should return an authenticated response, possibly an
   empty list. Empty data is valid; do not invent an alert or user records.
7. Tokens remain in memory; reloading requires another sign-in. Don't use an ID token as API
   authorization. PKCE/OAuth code exchange requests openid, ecoroute/read, ecoroute/write.

Operator user-management permissions may include cognito-idp:AdminCreateUser, AdminGetUser,
ListUsers/DescribeUserPool and, only if resetting locally, AdminSetUserPassword, scoped to
arn:aws:cognito-idp:ap-south-1:112920804206:userpool/ap-south-1_mLkYYyq3G.
No AdministratorAccess or app-client secret required. Automatic sign-up stays disabled.
Login page200/form verified; actual successful user login remains untested.

## Allow bounded pipeline testing with the CLI

Current dev-admin user is devesh_eco. Collector invocation still AccessDenied. An authorized
IAM operator can attach an inline policy to that user:
IAM → Users → devesh_eco → Permissions → Add permissions → Create inline policy → JSON.
Paste the contents of config/iam-integration-checks.json, review and name
EcoRouteIntegrationChecks. This is separate from CDKToolkit; no bootstrap update needed.

The policy permits invocation of ONE collector function, Query of environmental metadata
partition keys only and FilterLogEvents on two ingestion log groups. It grants no secret-value
reads, personal health/journey table access, Cognito user administration or SNS Publish.
Operator needs iam:PutUserPolicy on the exact user; don't grant that action to the CLI agent.
Invocation can incur Lambda/provider/storage costs; this checker invokes once and leaves
recurring schedules disabled. Remove inline policy after integration checks if not needed.

From the repository directory:

```powershell
.\.venv\Scripts\python.exe scripts/check_live_services.py --pipeline
```

This invokes Open-Meteo collection once for Delhi, then polls up to60seconds for matching
QUALITY#open_meteo metadata written by the cleaning worker. The S3→SQS→Lambda path runs
naturally, not via a disconnected direct cleaning invocation. Result raw_saved only is not
curation proof; curated_metadata_verified confirms matching worker report, not every object
content or delivery exactly once. It uses actual provider values, never synthetic pollution.

## Authenticated API and no-notification alert check

After successful login, you may run the checker with a Cognito ACCESS token entered only in
its hidden local terminal prompt. Never put it in command arguments, Git, output files or chat.
If copying from browser Network inspection, use only your own request's Authorization value
and omit the Bearer prefix when pasting locally. Do not share that inspection screenshot.

```powershell
.\.venv\Scripts\python.exe scripts/check_live_services.py --authenticated
```

It checks ready, stations, forecast, quality, alerts and two identical alert evaluations with
notify=false. It prints counts/status only, not user records or tokens. A real alert breach
may store deduplicated alert state, but never invokes SNS. If data has no complete24h window,
evaluation must remain unavailable; if below guidance, no alert is expected. Live dedup is
only proven if the first evaluation creates a real breach and the second does not.
Local alert tests cover missing data, dedup/rate limiting and disabled notification paths.

Source is forecast/model at cams_global:28.8000:77.2000 (~45km resolution), not a roadside
sensor. Guidance is WHO2021 PM2.5 24h concentration guideline15ug/m3, not AQI/medical advice.
No SMS sandbox/destination subscription/SNS publish grant is enabled by these checks.

## Routing and remaining tests

Drive/walk/cycle previews already verified200 with genuine geometry and travel times. Test
after ingestion to check coverage/exposure arithmetic; lack of geographic differentiation
must be disclosed. Public preview remains request-only. OpenAQ measurement ingestion needs
actual station/sensor IDs and time range; stored key alone does not prove coverage/access.
Gemini retrieval/generation remains untested. Do not enable all workflows/schedules before
data/auth checks pass. SMS channel needs separately verified opt-in configuration/approval.

## Actual verification in this setup turn

Public health200; missing/invalid tokens401 for wearable/latest and alerts; CORS204 exact
origin. Cognito authorization page200 with login form; deployed client code flow, scopes and
callback verified in template. Checker/auth/advisory tests32passed, Ruff passed. First pytest
command named nonexistent test_auth.py; no tests ran then; corrected test selection passed.
Pipeline attempt explicitly denied InvokeFunction. No credentials/authentication success,
data ingestion, notification delivery, model training or changed IAM policy claimed.

Official sources:
- https://docs.aws.amazon.com/cognito/latest/developerguide/how-to-create-user-accounts.html
- https://docs.aws.amazon.com/cognito/latest/developerguide/using-pkce-in-authorization-code.html
- https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-define-resource-servers.html
