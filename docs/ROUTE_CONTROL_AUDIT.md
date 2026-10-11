# Route controls audit — 12 October 2026

The control logic was verified locally against recorded road geometry, explicit test-only scoring inputs, mocked provider schemas and browser request/response tests. Fresh cloud verification stopped at HTTP 429 (`location_daily_budget_exhausted`). The allowance was not increased or bypassed. The backend fixes were subsequently deployed to EcoRouteCore on 12 October (UPDATE_COMPLETE); the frontend is being published through the existing Amplify main-branch integration. Fresh provider verification still awaits the routing allowance reset.

## What each control actually changes

| Control | Effect | Why a result might stay unchanged |
| --- | --- | --- |
| Drive | Google `DRIVE`, traffic-aware duration and genuine driving geometry | Provider may return one alternative, or traffic estimates may match |
| Walk | Google `WALK`, pedestrian geometry and duration | Same origin/destination does not guarantee a distinct visible corridor; no traffic-predicted walking speed |
| Cycle | openrouteservice `cycling-regular`, genuine cycle routes | Coverage/credentials/allowances can prevent a route; no car-route substitution |
| Departure | Time-matched pollution and weather; Google traffic prediction for Drive | Nearby times can fall within the same forecast hour, or traffic can be similar |
| Fastest | Smallest provider duration among valid candidates | Can also be the lowest-exposure and balanced route |
| Lowest exposure | Smallest complete PM2.5 concentration-time index among detour-eligible candidates | Same coarse PM2.5 cell often makes the shorter trip also the least exposed |
| Balanced | Normalized time, exposure, weather and climbing costs with selected weights | Identical input values, a tie, or the detour limit can make weight changes irrelevant |
| Maximum detour | Additional **travel time**, relative to fastest; excludes candidates from recommendations | If every candidate is inside every chosen limit, selection need not change; manually viewed alternatives remain visible and are marked when outside the limit |
| Pollution priority | Exposure's weight in Balanced; remaining weight goes to travel time | Does not change measured/model pollutant concentrations; affects ranking only |
| Weather preference | Open-Meteo midpoint/time sample; heuristic cost for rain, heat/cold and wind | Neighboring routes can share weather grid/time. This is a preference heuristic, not a medical or pollution forecast model |
| Lower climbing preference | Cycling-only, modeled ascent per route kilometre | Flat routes or equal ascent costs provide little/no ranking distinction; elevation requested only when weighted |
| Avoid tolls/highways/ferries | Google driving route modifiers | A route with none of those features can be unchanged; provider avoidance is a preference, not a guarantee |
| Avoid steps | Cycling provider `options.avoid_features=["steps"]` | If no returned route uses mapped steps, it need not change |
| Station forecast | Approved one-hour station model near supported stations, through a protected API | Needs Cognito, an approved model, inference worker and time/location coverage; experimental Beijing training does not prove current local navigation support |

Priority sliders now disable for Fastest and Lowest exposure. Their unused weather/climbing weights are not sent as active costs; driving/cycling avoidance settings still apply. Balanced settings are retained when switching back. Missing enabled factors produce an explicit fallback rather than invented values.

## Departure decision

Departure was retained because it has a real effect. The default is now **Leave now**, calculated at submission (+60 seconds for request transit), rather than a timestamp frozen when the page opened. **Plan a departure** exposes an optional date/time within the backend's existing 48-hour window. Walking/cycling departure selects forecast times; their duration is not a prediction of future traffic.

Existing live verification records from 11 October, Gateway of India → Marine Drive, contain:

| Mode / time | HTTP | Fastest duration | Estimated exposure |
| --- | --- | --- | --- |
| Drive | 200 | 489 s | 9.5219 µg·h/m³ |
| Walk | 200 | 2428 s | 47.2786 µg·h/m³ |
| Cycle | 200 | 781.1 s | 15.2098 µg·h/m³ |
| Drive, departure shifted one hour | 200 | 462 s | 8.8807 µg·h/m³ |

These are historical verification results, not current readings. Recorded exposure arithmetic passed and pollution was forecast/model data, not roadside measurements. Earlier factor verification recorded Google traffic metadata, Open-Meteo weather forecasts and openrouteservice modeled ascent. Evidence is in ignored local `work/live-route-pollution-modes.json` and `work/route-factors-live-verification.json`; it must not be mistaken for today's blocked live check.

## Corrections

- A zero pollution weight previously still required full pollution coverage for Balanced. Fixed locally: only nonzero-weight factors must be available. PM2.5 values and total exposure remain unavailable when unsupported; Lowest exposure still requires complete exposure.
- Changed settings now mark existing results as needing a new comparison. Existing readings do not pretend to reflect newly changed settings. Explanations require an updated comparison.
- Out-of-limit alternatives display an explicit extra-time warning. Added a 0% detour option.
- The factors panel explains what affects ranking, what affects readings, and shows weather/climbing status from the last returned comparison.

## Validation and repeatable checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

From `frontend`:

```powershell
node node_modules/@playwright/test/cli.js test --config playwright.maps.config.ts
node node_modules/@playwright/test/cli.js test dashboard.spec.ts sidebar-layout.spec.ts account-panel.spec.ts
```

After the cloud routing allowance resets, this opt-in smoke check makes up to three comparisons on the public Mumbai landmarks above. Existing provider charges/limits apply; it stops on HTTP 429. It does not require a token or AWS CLI credentials for guest comparisons, and does not save full geometry. Alternative routes are not guaranteed.

```powershell
.\.venv\Scripts\python.exe scripts/check_route_controls.py --live --api-base-url https://j1lgox7e00.execute-api.ap-south-1.amazonaws.com --output work/route-controls-live-summary.json
```

Without `--live`, the script makes no network calls. Today's one attempted comparison returned 429; no fresh mode success is claimed. Existing global route budgets use UTC windows (daily reset corresponds to 05:30 India time); respect `Retry-After` when supplied. No AWS resources, IAM permissions, budgets or provider keys were changed.

## Official provider references

- [Google traffic-aware departures](https://developers.google.com/maps/documentation/routes/config_trade_offs): driving route selection and duration can use the requested departure.
- [Google geographic coverage](https://developers.google.com/maps/coverage): India lists driving and walking support, with bicycle directions unavailable in the published table. Motorbike/two-wheel routing is not bicycle routing.
- [openrouteservice routing options](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options): step avoidance applies to cycling profiles.
- [openrouteservice restrictions](https://openrouteservice.org/restrictions/): alternative-count/distance restrictions can limit candidate diversity.
