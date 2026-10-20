# EcoRoute AI: one complete, verified comparison

Evidence captured 20 October 2026. This is a dated real API result, not a promise of current conditions when replayed. No synthetic pollution data was used. No commits, deployment, training jobs, or SMS sends were performed for this review.

## The question we answer

“Which of the returned road routes gives me a useful travel-time versus estimated-exposure choice?” We compare real provider candidates. We do not claim to find the global optimum across every road, or a medically safe route.

## 1. Reproduce the journey

- City overview → start **India Gate, New Delhi** → destination **Connaught Place, New Delhi**.
- Drive, Balanced, 25% maximum extra travel time; default exposure weight 0.5, time weight 0.5. Weather and terrain weights zero for this example.
- Consent to processing; choose a departure within the next 48 hours. This captured run departed **20 October 2026, 22:39:42 IST** (17:09:42 UTC).
- Compare once. Select each colored alternative, then inspect Air quality and Insights. Fresh results will differ from this capture.
- The guest endpoint POST /api/v1/routes/preview returned HTTP 200. Google route geometry is request-only; this review retains numerical evidence rather than saved Google road geometry.

## 2. Actual returned comparison

| Route | Minutes | Distance km | Time-weighted PM2.5 µg/m³ | Travel-time coverage | Exposure µg·h/m³ | Change vs fastest |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 6.38 | 2.702 | 111.50 | 100% | 11.86236 | +0.00% |
| 2 | 6.42 | 2.830 | 111.50 | 100% | 11.92431 | +0.52% |
| 3 | 7.93 | 3.370 | 111.50 | 100% | 14.74278 | +24.28% |

Route 1 is both fastest and lowest estimated exposure in this run, so Balanced also selects it. There is no demonstrated cleaner-but-slower alternative here. Route 3 costs about 1.55 extra minutes and 24.28% more estimated exposure than Route 1. Do not present this as a pollution reduction achieved by changing streets.

The 25% detour ceiling is 383 × 1.25 = **478.75 seconds**. All three candidates qualify (383, 385, 476 seconds). A 20% ceiling would exclude Route 3 from recommendation because 476 > 459.6 seconds; this latter calculation is an illustration using the same returned candidates, not a second live request.

Fastest minimizes provider travel time. Lowest exposure minimizes the complete concentration-time total among detour-eligible candidates. Balanced uses min-max normalized time and exposure over eligible candidates. With default weights, score = 0.5 × normalized time + 0.5 × normalized exposure; smaller is better. Because concentrations match in this example, the two objectives agree. Traffic is already incorporated in Google driving duration; it is not counted again as a separate benefit.

## 3. Where the data comes from

| Input | Evidence in this run | What it does not mean |
|---|---|---|
| Roads, distance, driving duration | Google Routes; fixture=false; traffic-aware; collected 20 October 2026 16:59:42 UTC | The cinematic city artwork is not the routing map |
| PM2.5 | Open-Meteo / Copernicus CAMS, forecast, 111.5 µg/m³ | Not an OpenAQ station measurement, not AQI |
| Geographic support | cams_global:28.8000:77.2000; approximately 45 km | Not block-by-block or roadside sensing |
| Forecast timestamp | 20 October 2026 17:00 UTC | Forecast validity time, not sensor collection time |
| Download timestamp | 20 October 2026 16:59:43 UTC | Does not establish model issue time |
| Temporal detail | Hourly API output; underlying model interval 3 hours | Hourly output does not create hourly independent model observations |
| Model run and uncertainty | Model run not supplied; confidence low; no calibrated interval | No invented confidence percentage |

The sample locations are roughly 20 km from the returned grid centre. All alternatives share the same coarse cell. Short geometric sections improve travel-time bookkeeping, not the atmospheric model's spatial resolution. Source attribution and licensing metadata are retained; Open-Meteo/CAMS attribution and applicable service terms remain required.

## 4. Show the calculation

For each valid segment i:

**E = Σ [PM2.5ᵢ (µg/m³) × segment durationᵢ (seconds) ÷ 3,600].**

The first Route 1 section lasts 35.4325758124 seconds:

111.5 × 35.4325758124 ÷ 3,600 ≈ **1.09743 µg·h/m³**.

Summing its 11 sections gives **11.8623611111 µg·h/m³**. Since this run has the same concentration throughout, it also equals **111.5 × 383 ÷ 3,600**. All three full segment sums were recomputed during the live check and matched the returned exposure totals.

**Coverage = usable segment seconds ÷ total journey seconds.** 100% coverage means a usable modeled value covers all travel time; it does not mean clean air or high spatial accuracy. With missing/flagged values, do not replace gaps with zero or compare a partial sum as if it were a complete trip. The full estimate remains unavailable. The frontend's Check route data verifies arithmetic and coverage in the returned response; it does not fetch fresh measurements.

## 5. AWS: working, provisioned, and gated

Verified 20 October 2026 in Mumbai using the configured non-root dev-admin identity. Stack status alone is not an end-to-end test.

| Service / integration | Status and evidence | Gate / remaining proof |
|---|---|---|
| API Gateway + API Lambda | Live health200 and Delhi comparison200 | No new deployment needed for the existing compare path |
| Environmental collector → S3 raw → SQS → cleaner → curated S3 + DynamoDB metadata | One fresh collector invocation; metadata reports192 cleaned records and2 curated files, cached=false | Verifies curated pipeline outcome, not every possible provider/outage |
| DynamoDB | Seven tables in deployed Data stack; pipeline metadata query succeeded | Do not imply every private CRUD path was tested today |
| Cognito + protected APIs | Pool/client/authorizer provisioned; wearable and alerts endpoints reject absent/invalid tokens401 | A real successful user login and authorized private request still need an interactive check |
| CloudWatch | Core has12 alarms and7 log groups; IoT has2 alarms and1 log group | Alarm existence verified; alarm firing and notification delivery not exercised |
| Secrets Manager | Server provider access succeeds indirectly through live routing | No secret values read; individual secret policies not exhaustively re-audited |
| Amplify | Existing frontend hosting; last confirmed publication includes Delhi label | Browser-map billing error was last reported; recheck after Google billing activation |
| EventBridge Scheduler + Step Functions | Core contains2 schedules and1 state machine | Definitions default disabled; current scheduler reads denied. No execution claimed |
| SNS | Operational topic provisioned; improved consent/SMS implementation exists locally | No SMS recipient/DLT setup; no send or delivery verified; local changes not deployed |
| SageMaker AI / ECR / ML S3 | ML stack exists with ECR repository, bucket and execution role | No paid training launched in this review; no verified live Delhi station model |
| AWS IoT Core | Rule and validator resources provisioned | Hardware bridge not enrolled/validated; definition disabled; current rule-state read denied |
| Bedrock / Gemini | Explanation integration exists | No model invocation tested in this review; deterministic fallback must remain labeled |
| Amazon Location | Optional route/places adapter | This run used Google Routes, not Amazon Location |
| OpenAQ | Observation adapter exists | Not the source for this result; no new successful OpenAQ check claimed |
| ECS/Fargate/EKS | Not required for the demonstrated serverless path | ECS/Fargate work paused; EKS excluded |

Core and Data are UPDATE_COMPLETE; ML and IoT are CREATE_COMPLETE. The API Lambda configuration read and Scheduler get_schedule checks returned AccessDeniedException, so these are verification gaps, not confirmed service failures.

The curation evidence object is:
`raw/source=open_meteo/date=2026-10-20/af75c7a57b9d8103d229ffd2b333760f696a855890cd7f95bd7f837fc74172a9.json`.

The route-scoring lookup and persisted ingestion pipeline are related but distinct: this comparison used freshly fetched area forecasts. Its samples contain no persisted raw_key. Do not claim that these exact route values came from the just-created Parquet objects.

## 6. What you need to configure

**For the visible map:** activate billing on the Google project owning the browser key, enable Maps JavaScript API, and allow the Amplify domain in website restrictions. Put the browser key only in VITE_GOOGLE_MAPS_API_KEY in Amplify; redeploy only if the key changes. Google billing is separate from AWS credits. The working backend routing key and browser map key are separate.

**For private-feature proof:** sign in through Cognito on the deployed website, then check an owned private endpoint. Never send a password, token or verification code in chat.

**For optional AWS read-only audit:** IAM → Users → devesh_eco → Permissions. Have the account administrator allow lambda:GetFunctionConfiguration on the exact EcoRoute API Lambda ARN, scheduler:GetSchedule on the two EcoRoute schedule ARNs and iot:GetTopicRule on the EcoRoute wearable rule ARN. These only permit inspection; do not add AdministratorAccess. Stack Resources displays the exact identifiers. No extra access keys are needed.

**Not required for this route demo:** SMS/DLT, physical wearable integration, SageMaker training or Bedrock activation. Keep them visibly gated. If SMS is later activated, follow ALERTS_SETUP.md; it requires consent, verified recipient binding and approved India setup. Do not enable continuous jobs or paid training simply to make a service list longer.

## 7. Suggested reviewer narration

“Here I compare India Gate to Connaught Place. Google supplies real road routes and traffic-aware travel time. Open-Meteo supplies a CAMS area forecast. Every minute in these three routes has forecast coverage, but the grid is about 45 kilometres, so we cannot resolve individual streets. We multiply concentration by hours spent in each section and add them. The quickest route takes 6.38 minutes and has an exposure index of 11.86; the longer alternative takes 7.93 minutes and has 14.74. They share the same pollution forecast, so the difference comes from time. Lambda and API Gateway serve this comparison, and we separately verified the S3/SQS cleaning pipeline into DynamoDB metadata. ML, hardware telemetry and SMS are clearly gated rather than presented as live.”

## Publication

Frontend explanation and this guide approved for publication after local verification. Backend, SNS and infrastructure changes are excluded.

## Evidence and limits

Shareable numerical evidence: [dated comparison summary](evidence/delhi-review-2026-10-20.json). Three sample sections per route are retained; the full-sum check was performed in memory on all sections.

Local machine evidence: work/reviewer-live-check.json, work/reviewer-aws-inventory.json and work/reviewer-aws-details.json. No public token or secret is needed to view this guide. No guarantee of a particular judging score is possible; reproducibility and honest boundaries are the basis for the demonstration.

## Local verification performed

- Python routing tests:40 passed (real recorded road fixtures; synthetic pollution cases are tests only).
- Frontend unit tests:74 passed.
- Maps/browser integration suite:29 passed with Google SDK/API mocks; verifies UI behavior, not live Google browser billing.
- Production build passed; existing large smartwatch chunk warning remains.
- The new calculation panel was checked at390px and1280px widths. No route API schema or ranking changes.

Repeat offline checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_routing.py -q
cd frontend
npm test
npm run build
npx playwright test --config playwright.maps.config.ts google.maps.ts
```

The existing `scripts/check_live_services.py --pipeline --profile dev-admin` performs a real billable collector invocation; it is not part of the offline tests. Do not repeatedly invoke it just to replay this report.
