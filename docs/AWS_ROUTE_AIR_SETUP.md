# AWS setup walkthrough: real routing and air-quality comparisons

Updated 11 October 2026. Use the existing account112920804206 and Mumbai ap-south-1.
Do not create another stack/pool/bucket or replace existing secrets to follow this guide.
No private key, password, verification code or token belongs in chat or Git.

1. Open https://main.d3txif33djiy59.amplifyapp.com/ for AWS integration testing. The local website
   currently uses the AWS API while the API permits the Amplify browser origin only. This causes
   local CORS failures. Local sign-in also redirects to Amplify. Hosted testing avoids that mismatch.
   Local-only routing can use VITE_API_BASE_URL=http://127.0.0.1:8000 after restarting; it reads local
   environmental data, not automatically the AWS datasets. Never use wildcard production CORS.

2. In AWS Console, confirm account112920804206; select Asia Pacific (Mumbai), ap-south-1.
   IAM is global. Use an authorized IAM administrator for granting the narrow operator policy.
   The configured development CLI identity is non-root dev-admin/devesh_eco. The latest collector
   invocation check was AccessDeniedException; no pollution ingestion succeeded in that check.

3. Open config/iam-integration-checks.json in the repository and copy its ENTIRE JSON contents.
   Console IAM -> Users -> devesh_eco -> Permissions -> Add permissions -> Create inline policy
   -> JSON. Paste the JSON, review, name EcoRouteIntegrationChecks, create/save. It grants only
   one collector invocation, environmental metadata Query and two ingestion-log reads. It does not
   grant secret-value reads, personal wearable/trip access, SMS sends or AdministratorAccess.
   If the create-policy operation is denied, the authorized administrator must perform it; attaching
   another read-only policy will not provide InvokeFunction. No need to change CDKToolkit for this.

4. Secrets Manager, Mumbai: verify existing names ecoroute/openaq, ecoroute/gemini,
   ecoroute/google-route and ecoroute/openrouteservice. These are already connected by exact ARNs.
   The standard format is Key/value pairs: key api_key, value your provider key, entered only in
   Console. Do not copy the value into VITE_ settings. Open-Meteo's noncommercial public forecast
   endpoint requires no key. The stored OpenAQ key still needs a genuine sensor/coverage test;
   secret existence is not proof of validity. Google/ORS server routing was verified in prior live tests.

5. Console Lambda -> Functions -> EcoRouteCore-Collector9EBA7CF5-3QqSZI3RLYxS -> Test.
   Create a PRIVATE event named DelhiForecastOnce. Paste this JSON, save and run once:

   ```json
   {"source":"open_meteo","request":{"latitude":28.6139,"longitude":77.209}}
   ```

   This is actual forecast collection, not fabricated measurements. A successful raw_key means
   raw JSON was saved; it does not by itself prove cleaning. One call can incur small Lambda,
   storage and queue charges under the approved demo scope. Leave recurring schedules disabled.
   AWS procedure: https://docs.aws.amazon.com/lambda/latest/dg/testing-functions.html

6. From the repository root run:

   ```powershell
   .\.venv\Scripts\python.exe scripts/check_live_services.py --pipeline --profile dev-admin
   ```

   This makes one collector call and verifies the existing S3 -> SQS -> Worker -> Parquet/DynamoDB
   chain. Desired result: pipeline=curated_metadata_verified. Raw-only is incomplete. If denied,
   verify Step3 was attached to devesh_eco in the correct account. If the collector failed, inspect
   its CloudWatch log; do not paste full provider responses/keys in chat. If cleaning is pending,
   inspect the Worker function/SQS trigger and DLQ without purging messages. Never make S3 public.
   In S3, inspect ecoroutedata-airdatad62c85d3-aqvlom4hqoks: raw/source=open_meteo/date=.../*.json
   and curated/source=open_meteo/date=.../*.parquet. Dates include forecast target dates.
   Metadata table: EcoRouteData-environmentA2E95CAF-18GSQK8N0H0Q; partitions FILES#open_meteo and
   QUALITY#open_meteo. Do not manually insert pollution rows to make the UI show values.

7. On Amplify open Connection settings -> Live services -> Sign in with Cognito -> Sign up.
   Complete email verification, then sign in. Existing pool ap-south-1_mLkYYyq3G has self-signup
   enabled; no additional pool/client required. Cognito Console -> this pool -> App clients ->
   3ch3rgjq9opu8f7p0e7buf9gii -> Login pages/managed-login settings. Preserve authorization code,
   PKCE/public-client behavior, scopes openid/ecoroute/read/ecoroute/write, and callback
   https://main.d3txif33djiy59.amplifyapp.com/. If this differs, record fixes in CDK callback_urls
   before another deployment. Never enable an app-client secret for the SPA. Positive user login
   remains unverified until a real account signs in; do not share passwords or email codes.

8. Amplify Console -> ecoroute-ai app -> Hosting/environment variables. Keep these public values
   (Google browser key is configured only by its owner):

   ```env
   VITE_API_BASE_URL=https://j1lgox7e00.execute-api.ap-south-1.amazonaws.com
   VITE_COGNITO_DOMAIN=https://ecoroute-112920804206-ap-south-1.auth.ap-south-1.amazoncognito.com
   VITE_COGNITO_CLIENT_ID=3ch3rgjq9opu8f7p0e7buf9gii
   VITE_COGNITO_REDIRECT_URI=https://main.d3txif33djiy59.amplifyapp.com/
   ```

   VITE_GOOGLE_MAPS_API_KEY must be the restricted browser key, not the server key. After changing
   environment variables, redeploy the branch; editing local .env files does not update Amplify.
   Google Cloud Console -> APIs & Services -> Library: Maps JavaScript API for the browser;
   Routes API and Places API(New) for the server. Google billing must be enabled. Browser key
   website restriction: https://main.d3txif33djiy59.amplifyapp.com/* (and exact local development
   origins if needed). Provider billing is separate from AWS credits. Server keys stay private.

9. On the website choose Live services -> Journeys. For the first data-covered example use
   India Gate, New Delhi -> Connaught Place, New Delhi. Select Drive/Walk/Cycle, departure now or
   within available forecast coverage, preference Balanced/Lowest exposure/Fastest, maximum detour,
   consent to location processing, then Compare routes. Click a returned route to select it.
   Genuine routes are from Google for Drive/Walk and ORS for Cycle; alternatives are not guaranteed.
   Air Quality displays the selected route's time-weighted PM2.5 concentration in ug/m3, not AQI.
   Exposure is sum(concentration * travel hours), ug*h/m3; it is not medical dose. Missing coverage
   remains unavailable. Coarse forecasts do not prove street-level pollution differences. If all
   routes share one grid, differences largely reflect duration/departure, not a cleaner street.

10. For another city, collect its actual coordinates using the same collector request and verify
    coverage. Road routing can support other places where providers operate, but current pollution
    collection does not automatically cover every place users select. For observed OpenAQ data,
    verify real station/sensor IDs, units, geography and freshness first; use the existing paginated
    ingestion interface. Never substitute generated or foreign historical data for current Delhi data.

11. After the one-shot flow passes, review an hourly/daily refresh proposal. Existing EventBridge
    schedules are disabled intentionally. Hourly per-location collection means720collector events
    in a30day month plus downstream work; costs depend on storage, logs, retries and plan. Enable
    only the intended schedule after explicit continuous-workflow cost approval. AWS Budgets alerts
    do not hard-cap charges. Preserve disabled ML/SMS/IoT schedules until their prerequisites pass.

12. Other features have independent blockers: SageMaker needs quota>=1, pinned ECR image, scoped
    job permissions, approved costs and suitable Delhi history (LARGE_DATA_TRAINING.md). It is not
    necessary for provider forecast exposure comparisons. SMS needs SNS verified destinations,
    supported origination setup and opt-in; no real recipients are notified by these checks.
    The Noise watch needs a supported data bridge, not merely IoT credentials. Google request-only
    Insights currently uses a deterministic explanation; Gemini invocation on that path requires
    additional application wiring. More AWS permissions alone will not finish those code/hardware gaps.

First action: attach EcoRouteIntegrationChecks, then run the collector verification. No paid
training, SMS, new resource provisioning or recurring workflow was started by preparing this guide.
