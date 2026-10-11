# Provider activation — 2026-10-11

All four provider secrets discovered via metadata ListSecrets in Mumbai, without reading
their values. Google is actually named ecoroute/google-route (singular); exact ARN used.
Ignored work/aws-deploy.context.json includes all four exact ARNs and gemini-2.5-flash.
Core UPDATE_COMPLETE connects Google/ORS/Gemini to API Lambda and OpenAQ to collector role.
Values remain in Secrets Manager; Lambda stores only ARNs. Guest preview enabled with atomic
hourly/daily request budgets; private records remain Cognito-protected. Schedules stay disabled.

Real India Gate → Connaught Place preview tests returned200 for all modes:

| Mode | Routes | First distance | First duration |
|---|---:|---:|---:|
| Driving | 1 | 3370 m | 616 s |
| Walking | 2 | 2824 m | 2428 s |
| Cycling (ORS) | 2 | 3430.1 m | 781.1 s |

All returned actual provider LineStrings (129/146/103 points for first routes), request-only
results, no saved personal journey. Concentration coverage absent: full PM2.5 exposure is null,
not zero. Do not claim lowest-pollution route or exposure reduction yet. Timings/provider
alternatives vary; this is one bounded demonstration, not a benchmark. First smoke report
selected incorrect duration/exposure field names; corrected bounded rerun recorded actual
duration_s and estimated_pm25_exposure_ug_h_m3. Six total preview requests in this verification.

59targeted tests passed; Linux Lambda asset rebuilt183.7MiB; security template review passed.
Gemini generation and OpenAQ retrieval still not live-tested. Collector InvokeFunction is
denied for CLI user. Secret existence/configuration alone does not validate credentials.

## One manual forecast ingestion

Use an authorized Console identity; Mumbai → Lambda →
EcoRouteCore-Collector9EBA7CF5-3QqSZI3RLYxS → Test → Create new event.
Event name: DelhiForecastOnce. Use this actual request, not synthetic measurements:

```json
{
  "source": "open_meteo",
  "request": {"latitude": 28.6139, "longitude": 77.209}
}
```

Save → Test once. It may make billed Lambda/storage/provider calls within demo usage;
do not enable recurring schedules. Report success/failure and returned raw_key, not secrets.
Collector success only proves raw persistence; S3 notification → SQS → worker → Parquet/metadata
must also be verified. Open-Meteo produces model/forecast values, not roadside observations.

OpenAQ ingestion additionally needs actual location_id/sensor_id, fresh UTC start/end and
available PM2.5 coverage. Do not invent IDs or use forecast grids as measured records.

Next: create Cognito test user/login/scopes for private APIs and Gemini explanations.
Do not place OpenAQ/Gemini/server routing keys in Amplify variables. Frontend API/Cognito
configuration remains correct and no frontend rebuild is required solely for secret activation.
