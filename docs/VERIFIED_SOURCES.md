# Verification evidence — 2026-10-08

Official docs reviewed before scaffold implementation. Account checks cannot establish availability
while STS credentials are invalid. No paid service probe was performed. Recheck before deployment.

| Area | Source and conclusion |
|---|---|
| Location regions and quotas | https://docs.aws.amazon.com/general/latest/gr/location.html — Mumbai routes endpoint listed; CalculateRoutes default 20/s |
| Routes V2 Python API | https://docs.aws.amazon.com/boto3/latest/reference/services/geo-routes/client/calculate_routes.html — geo-routes client, Origin/Destination, alternatives; no legacy calculator |
| Location IAM | https://docs.aws.amazon.com/service-authorization/latest/reference/list_geo-routes.html — CalculateRoutes uses provider ARN with empty account field |
| Lambda limits/regions | https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html and https://docs.aws.amazon.com/general/latest/gr/lambda-service.html — timeout/packaging/concurrency; new accounts can have lower quotas |
| HTTP API limits/regions | https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html and https://docs.aws.amazon.com/general/latest/gr/apigateway.html — 30s integration limit, 10 MB payload |
| Cognito regions | https://docs.aws.amazon.com/general/latest/gr/cognito.html — regional endpoints; account tier still needs validation |
| SageMaker regions/quotas | https://docs.aws.amazon.com/general/latest/gr/sagemaker.html — instance-specific quota review required |
| Bedrock models/regions | https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html — model must be selected before confirming access |
| CDK prerequisites | https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html — Node 22+; Python runtime dependencies independently resolved below |
| CDK bootstrap | https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping-env.html — creates assets/roles; version parameter alone is not deployment permission |
| SSO CLI | https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html — named sso-session/profile and browser login |
| Budgets | https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html — alerts are monitoring, not a spend cap |
| OpenAQ | https://docs.openaq.org/using-the-api/quick-start and https://docs.openaq.org/about/about — v3 API, X-API-Key, provider coverage and license audit needed |
| Watch | https://support.gonoise.com/support/solutions/articles/47001212415-it-takes-a-long-time-to-sync-the-activity-data-to-my-phone- and https://support.gonoise.com/support/solutions/articles/47001212423-calling-feature-in-colorfit-pro-3-alpha — phone sync documented; public developer API not verified |
| Mangum | https://mangum.fastapiexpert.com/ — ASGI adapter; actual AWS event integration deferred |

IAM service-reference pages reviewed (current URLs use service prefixes):
https://docs.aws.amazon.com/service-authorization/latest/reference/list_dynamodb.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_s3.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_sqs.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_scheduler.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_secretsmanager.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_sns.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_cognito-idp.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_sagemaker.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_iot.html,
https://docs.aws.amazon.com/service-authorization/latest/reference/list_budgets.html.
Some older long-form AWS IAM URLs redirected to the index; no evidence was inferred from those.
Step Functions, ECS/RDS detailed deployment IAM remains a future gate because these components
are deferred and no deployable template exists. Runtime action inventory is a design, not a certified policy.

## Python compatibility

Maintainer metadata queried directly from `https://pypi.org/pypi/NAME/json`; installed resolver
results differ slightly from cached web search snippets, so the local lock is authoritative.
Python 3.11.0 / Windows tested. Recommended before cloud packaging: latest patched Python 3.11
or supported 3.12, then repeat the lock/test checks. Ubuntu/Python 3.11.17 passed GitHub CI;
Python 3.12/3.13 and Lambda runtime packaging are not tested yet.

| Package | Resolved version | Maintainer Requires-Python |
|---|---|---|
| FastAPI | 0.143.0 | >=3.10 |
| Pydantic | 2.14.0 | >=3.10 |
| pydantic-settings | 2.15.0 | >=3.10 |
| boto3 / botocore | 1.43.109 / 1.43.109 | boto3 >=3.10 |
| aws-cdk-lib | 2.272.0 | >=3.10 |
| constructs | 10.8.1 | >=3.10 |
| Mangum | 0.22.0 | >=3.10 |
| Uvicorn | 0.54.0 | >=3.10 |
| pytest | 9.1.1 | >=3.10 |
| httpx | 0.28.1 | >=3.8 |
| Ruff | 0.16.10 | >=3.7 |

Full transitive versions in requirements.lock, CDK CLI in package-lock.json. `pip check` and
scaffold tests establish this environment's compatibility only. Starlette emits a deprecation
warning for its httpx TestClient integration; it works in this lock, and a future upgrade should
migrate that test transport. ML/geospatial packages are deliberately not installed before selecting
the algorithms and validating data. Verify their Python/Linux wheels before that phase.

## Phase 1/2 implementation verification addendum — 2026-10-08

- [HTTP API JWT verification](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html):
  implemented issuer/audience and route scopes, with independent Cognito access-token checks in FastAPI.
- [Lambda SQS delivery](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html):
  at-least-once processing, partial batch failures, deterministic curation replay implemented.
- [AWS cross-platform native wheels](https://docs.aws.amazon.com/powertools/python/latest/build_recipes/cross-platform/):
  Python3.11 uses AL2/glibc2.26. PyPI wheel metadata confirmed PyArrow23.0.1 needs glibc2.28;
  PyArrow20.0.0 offers manylinux2014/cp311. Pinned20.x and built182.9MiB Linux asset successfully.
  This supersedes the earlier untested-packaging note; AWS execution is still unverified.
- [Open-Meteo schema](https://open-meteo.com/en/docs/air-quality-api),
  [terms](https://open-meteo.com/en/terms), [plans](https://open-meteo.com/en/pricing):
  adapter selects global CAMS, native coarse resolution, retains units/attribution and null model issue time.
- [OpenAQ schema](https://docs.openaq.org/api/operations/sensor_measurements_get_v3_sensors__sensors_id__measurements_get),
  [rate limits](https://docs.openaq.org/using-the-api/rate-limits),
  [terms](https://docs.openaq.org/about/terms): original measurements, date filters/pagination,
  flagInfo.hasFlags and source licenses preserved. No live OpenAQ assertion without credentials.

Live model collection evidence and distinctions from sensor data: INGESTION.md. Synthetic contract
fixtures are explicitly labelled in tests/test_environment.py; they are not measurements. One
cached repeat reproduced the same raw/Parquet keys without another external request.
