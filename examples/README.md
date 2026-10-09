# API examples

Import the two Postman files as a collection and local environment. Keep access_token private;
never export a populated token. Set owned resource IDs from authenticated responses. Do not run
the entire collection blindly: it includes consent changes and deletion requests.

delhi-recorded-response.json is an **actual historical result**, captured on2026-10-09 UTC
(2026-10-10 IST), from the public India Gate→Connaught Place benchmark. The response member is
the full RouteComparison JSON, validated against the exported response schema. The surrounding
example_kind/captured_at/not_current_data metadata is file metadata, not part of the API response.
This is real OSRM road geometry plus real Open-Meteo modeled/forecast values, not AWS Location
verification, roadside sensors, synthetic pollution or current conditions. Coarse grid warnings
and source timestamps must stay visible. Geometry includes all returned coordinates and segments.
Route IDs have expired and cannot be used to retrieve records from another installation.

At the recorded departure, fastest and lowest estimated exposure coincide; no pollution-related
route improvement is demonstrated. Use this file to develop response parsing, not to guide a
live journey. Source attribution: OpenStreetMap contributors/OSRM for roads;
Open-Meteo and CAMS for environmental forecasts. Provider documentation and license limitations
are in docs/INGESTION.md and docs/ROUTING.md.
