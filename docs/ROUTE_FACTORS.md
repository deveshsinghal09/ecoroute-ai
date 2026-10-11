# Route recommendation factors

Road candidates always come from a real routing provider; ML predicts station PM2.5, not road geometry.
The route selector calculates exposure and preference scores deterministically. Gemini explains;
it does not forecast PM2.5, invent traffic, decide geometry or replace measurements.

| Input | Used for | Limitations |
| --- | --- | --- |
| Google traffic-aware duration | Driving traversal/exposure timing and fastest route | Already included in time; no second congestion penalty. `staticDuration` is historical-traffic baseline, not free-flow. |
| PM2.5 observations/provider forecasts/approved station model | sum(concentration µg/m³ × travel hours) | Missing coverage leaves full exposure null. Same coarse cell cannot demonstrate street differences. |
| Open-Meteo temperature/rain/wind forecast | Optional preference heuristic | Representative route midpoint/time, coarse model-dependent grid; not a medical score. No humidity/rain sensor claims. |
| ORS modeled ascent/descent | Optional cycling ascent per km preference | Resolution unspecified, not physical effort; absent elevation stays unavailable. |
| Google avoid tolls/highways/ferries | Driving candidate generation preference | Best effort, not a guarantee; not accepted for walking/cycling. |
| ORS avoid steps | Cycling route generation | Map coverage dependent; no wheelchair/step-free walking certification. |
| Maximum time detour | Exclude candidates beyond fastest × (1+detour%) | Based on time, not distance; may leave one candidate. |

Balanced score is min-max normalized among detour-eligible routes:
`(1-e-w-t)*duration + e*exposure + w*weather_preference_cost + t*ascent_m_per_km`.
Defaults `e=.5,w=0,t=0`; nonnegative weights sum to at most one. Ties use duration. No street-level
learning claim: this ranks returned candidates, not a global optimum. Any eligible route missing
pollution or an enabled weighted input makes the balanced objective unavailable and selects the
fastest with an explicit reason. Lowest-exposure category requires complete exposure independently
of weather. Frontend exposes controls in Route factors & forecasts and source limitations.

Weather is separately opt-in with `ENABLE_ROUTE_WEATHER=true` / CDK `enable_route_weather=true`.
Queries occur only when `weather_weight>0`; maximum three request-coalescing cells per comparison,
100/day and 30/hour across the existing atomic AWS budget table. Warm-worker cache 15min/64cells,
not durable forecast vintage or exact native-grid identification. Provider outages/schema/unit changes
leave weather unavailable. Metadata names collection/forecast time, grid location, units and formula.
Public API is for noncommercial use under [Open-Meteo terms](https://open-meteo.com/en/terms);
commercial deployment needs a reviewed plan/key adapter before activation. No provider text drives
the scoring formula.

Optional future factors need real, licensed datasets before scoring: sidewalks/cycle lanes,
road accessibility, verified closures, rain flooding, localized roadside monitoring and user-validated
preferences. No crime/safety, accident or medical risk scores are currently implemented.

New protected `POST /api/v1/routes/predict` extends CompareRequest with `station_ids` (1–20) and optional
`model_version` (24 hex). It returns a standard full-geometry comparison plus `station_forecasts`,
`model_versions`, `horizon_hours=1`. Missing model/observations produce503; missing JWT401, wrong
scope403, invalid weights/mode/preferences422. This does not expose ML to unauthenticated users.
Existing `/routes/predict-departure-times` remains for up to three departures.

Production model readiness is independent of a completed experimental training report. See
[large dataset experiment, actual metrics and cloud prerequisites](LARGE_DATA_TRAINING.md).
