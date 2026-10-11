# Connect the deployed Amplify frontend

Verified frontend: https://main.d3txif33djiy59.amplifyapp.com/
Verified API: https://j1lgox7e00.execute-api.ap-south-1.amazonaws.com

Amplify Console → ecoroute-ai → Hosting → Environment variables → Manage variables.
Set these public identifiers for main, save, then redeploy main so Vite rebuilds the bundle:

| Variable | Value |
|---|---|
| VITE_API_BASE_URL | https://j1lgox7e00.execute-api.ap-south-1.amazonaws.com |
| VITE_COGNITO_DOMAIN | https://ecoroute-112920804206-ap-south-1.auth.ap-south-1.amazoncognito.com |
| VITE_COGNITO_CLIENT_ID | 3ch3rgjq9opu8f7p0e7buf9gii |
| VITE_COGNITO_REDIRECT_URI | https://main.d3txif33djiy59.amplifyapp.com/ |

Keep the browser Google Maps key configured with exact hosted referrer restrictions.
Never put Gemini/OpenAQ/server Google Routes keys or AWS credentials into VITE variables.
Those belong in backend Secrets Manager references, which remain unconfigured in this deployment.

The CLI user cannot list/manage Amplify apps. This Console step has not been performed by the
agent; the public bundle previously lacked the AWS API domain. Local ignored frontend/.env.local
was updated with these public identifiers, preserving existing keys; it is not deployed by Git.

Public health and docs work; journey/wearable APIs require Cognito access tokens/scopes.
Self-sign-up is disabled. No test user was created and no successful login has been verified.
Guest routing is not enabled in this deployment; do not claim the map alone proves routing.
Live provider credentials/model readiness must be configured before environmental features work.

Verified 2026-10-11: health200, OpenAPI200, unauthenticated wearable/latest401 and ready401,
Amplify-origin OPTIONS204 with exact Allow-Origin. Schedules disabled in deployed template.
CloudWatch alarms/log groups defined, but access-log read denied to CLI; delivery not verified.

Original CloudFront hosting stack remains rolled back with retained private bucket. Amplify
is a separately user-created host; CDK hosting teardown does not delete the Amplify app.
Inspect retained old Cognito pools before cleanup; do not delete user records blindly.
