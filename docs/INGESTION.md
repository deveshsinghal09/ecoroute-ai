# Environmental ingestion and data engineering

## Providers verified against official documentation

Reviewed 2026-10-08. [Open-Meteo air API](https://open-meteo.com/en/docs/air-quality-api)
provides global CAMS coverage including Delhi. The adapter explicitly selects cams_global and
requests hourly pm2_5, pm10, nitrogen_dioxide and ozone, GMT Unix times. Native global model
resolution is approximately 45 km and 3 h; hourly output is interpolated. Actual returned coordinates
identify the model cell. No street-scale measurement or model issue time is inferred.
Historical API availability starts August 2022; these archives remain model data, not observations.
[Terms](https://open-meteo.com/en/terms) allow eligible noncommercial free use under published caps
(600/min, 5,000/hour, 10,000/day); [commercial plans](https://open-meteo.com/en/pricing) require a
key and customer endpoint. Attribute Open-Meteo and CAMS; CC BY 4.0 data attribution remains required.

[OpenAQ measurement schema](https://docs.openaq.org/api/operations/sensor_measurements_get_v3_sensors__sensors_id__measurements_get)
uses v3 sensors/{id}/measurements, X-API-Key, datetime_from/datetime_to, page/limit, period
UTC bounds, parameter name/units and flagInfo. Station lookup establishes sensor ownership,
coordinates, provider, owner and licenses. [Rate limits](https://docs.openaq.org/using-the-api/rate-limits)
are 60/min and 2,000/hour for standard access. [Terms](https://docs.openaq.org/about/terms) require
original-provider attribution and compliance with underlying source licenses; do not assume
universal redistribution permission. Station availability, archive depth, licensing and current
Delhi archive depth and complete coverage require per-station checks. On2026-10-10 IST,
after user-confirmed key rotation, one Delhi bbox page returned100 entries (more pages remain).
GK1 (Oberoi Terrace), location2860223/sensor9320367, reports CC BY4.0 attribution to Oberoi.
A real14:00Z..20:00Z window on2026-10-09 returned5 hourly observed PM2.5 records,
15:00Z..19:00Z, normalized ug/m3, range51.2..82.0, no rejected/flagged values. Raw JSON,
curated Parquet and metadata are local under ignored work/environment; nothing was uploaded
to AWS. This validates one sensor/page, not all Delhi stations or archive completeness.
Optional official Indian/weather sources are not enabled.

## Collection commands

Run in the repo with the virtualenv installed. No command here uploads to AWS.

```powershell
# One two-day forecast request, cached on a stable 0.4-degree request lattice
.\.venv\Scripts\python.exe scripts/ingest_air.py --source open_meteo
# One bounded historical model request (maximum seven days inclusive)
.\.venv\Scripts\python.exe scripts/ingest_air.py --source open_meteo --start 2026-10-01 --end 2026-10-07
# After setting OPENAQ_API_KEY privately, discover Delhi bbox stations
.\.venv\Scripts\python.exe scripts/ingest_air.py --source openaq --stations --max-pages 1
# Select real IDs from discovery; replace the numeric placeholders before running
.\.venv\Scripts\python.exe scripts/ingest_air.py --source openaq --location-id LOCATION_ID --sensor-id SENSOR_ID --start 2026-10-07T00:00:00Z --end 2026-10-08T00:00:00Z --max-pages 3
```

CLI pages contain 100 records, max-pages 1..10. An exhausted page allowance reports `incomplete`
and `resume_page`, exits 2; resume using `--page N` with the same IDs/date window. Failure exits 1,
completion exits 0. Split longer history into <=7-day windows and retain resume metadata; no
claim of a complete historic dataset is made. OpenAQ requests cost two HTTP calls per measurement
page (station + measurements). Unknown units remain null after normalization; gases in ppm/ppb
are not converted without pressure/temperature assumptions. Provider flagInfo.hasFlags quarantines
a value as null while preserving original values and flag metadata; detailed flag descriptions
from the separate flags endpoint are not yet enriched.

## Storage and reliability

LOCAL stores raw objects, curated Parquet and a SQLite metadata/budget index in `work/environment`.
`ENVIRONMENT_LOCAL_PATH` can point elsewhere. Do not run concurrent local writers; AWS uses
DynamoDB atomic quota counters and a single reserved collector invocation.

AWS template workflow: disabled Scheduler -> collector Lambda -> raw S3 object notification ->
SQS -> cleaner Lambda -> curated S3 + DynamoDB environment table. Data owns bucket/queues to
avoid a cross-stack dependency cycle. No deployed bucket name exists yet.

```text
s3://<DataBucket>/raw/source=open_meteo/date=YYYY-MM-DD/<envelope-sha256>.json
s3://<DataBucket>/raw/source=openaq/date=YYYY-MM-DD/<envelope-sha256>.json
s3://<DataBucket>/curated/source=<source>/date=<valid-date>/<raw-key-sha256>.parquet
s3://<DataBucket>/reports/                 # reserved reports prefix
s3://<MlBucket>/datasets/                  # reserved training dataset prefix
s3://<MlBucket>/models/                    # reserved model artifact prefix
```

Raw partitions use collection UTC date, curated partitions use reported UTC date. Local station
discovery additionally saves raw/stations/date=.../page=...json; it does not run through Lambda.
Raw responses retain all provider metadata, request parameters without keys and collection time.
Parquet uses an explicit stable schema, Snappy compression and raw-key lineage. Invalid coordinate
or timestamp schemas fail closed for the page and are retried/DLQ'd in AWS, rather than guessing.
Missing, negative, unsupported-unit, nonfinite or implausible values are null with quality reasons.
The >100,000ug/m3 bound is an engineering quarantine, not a medical threshold. Observations older
than 6 h at collection are flagged; future observations >5 min are quarantined.

Reprocessing the same raw key overwrites the same Parquet keys and metadata idempotently. Within
pages and API reads, stable record IDs deduplicate observations; multiple raw pages may physically
contain the same observation, so downstream exports must deduplicate by record_id. Forecast
retrieval vintages stay separate. Request cache: model 1 h, observations 5 min. Neighbouring request
points snap to a coarse request lattice; actual model cell coordinates come from the provider.
Lattice boundaries may request the same returned cell twice; there is no street-level interpolation.
A crash after raw upload and before cache update can cause another fetch; processing remains
idempotent for each saved object. This is at-least-once delivery, not exactly-once collection.

Default provider budgets 100 HTTP attempts/day and 30/hour, clamped to1,000/day and100/hour even if
configured higher. Retries count; failed hourly reservations can conservatively consume a daily
slot on AWS. Transport spaces calls 2.1s, retries transient failures at most 3 total attempts, stops
immediately on 401/403/429. Credential URLs/bodies are not logged. Schedules default disabled;
CDK context ingestion_interval_minutes accepts 60..1440. No provider calls occur from public APIs.
Counters/throttles control usage, not total AWS dollars or other users of the same provider key.

Cleaner returns partial SQS failures; queue visibility 180s, cleaner deadline 30s, batch 5,
max receives 3 then 14-day DLQ. Collector deadline 180s; asynchronous retries 1 and its failed events
also land in the DLQ. CloudWatch alarms publish to an SNS topic (recipient subscription pending).
Step Functions is deferred: bounded single-page Lambda jobs and resumable local backfill suffice
for this phase. A multi-city durable backfill/training workflow would justify it later.

## Real run evidence (local only)

2026-10-08T18:11:31.163657Z: one Open-Meteo HTTP200 response, requested Delhi vicinity, returned
cell latitude 28.800003 longitude 77.20001. 48 hourly timestamps spanning 2026-10-08T00:00Z through
2026-10-09T23:00Z x 4 pollutants = 192 records: 76 modeled and 116 forecast at collection, zero missing or
quarantined values. No station measurements, API prediction accuracy or AWS upload was tested.
Saved raw basename: `3355337082173b657796acf567a575f7fb55297369d9cdcc7e39ad2f0f1a6886.json`
under raw/source=open_meteo/date=2026-10-08/.
Two Parquet objects, valid dates 2026-10-08 and 2026-10-09, basename:
`cc7cf618d12363bcfb18b3717c11ce4e8dc13a3888a573a73668f47a1256437b.parquet`.
Actual files are ignored local data, not committed fixtures or cloud resources. A repeated CLI
run returned cache_hit=true with identical raw and Parquet keys, without another HTTP request. A repeated CLI
run returned cache_hit=true with identical raw and Parquet keys, without another HTTP request.

## Sample API calls

With FastAPI running and a real Cognito access token configured in your local process (never chat):

```powershell
$headers = @{ Authorization = "Bearer $env:ECOROUTE_ACCESS_TOKEN" }
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/air-quality/forecast?location_id=cams_global:28.8000:77.2000&hours=24' -Headers $headers
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/air-quality/current?source=open_meteo&location_id=cams_global:28.8000:77.2000' -Headers $headers
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/air-quality/history?source=open_meteo&location_id=cams_global:28.8000:77.2000&start=2026-10-08T00:00:00Z&end=2026-10-09T23:00:00Z' -Headers $headers
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/data/quality?source=open_meteo' -Headers $headers
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/air-quality/stations' -Headers $headers
```

These tokens/pools have not been provisioned. Until configured, use pytest's isolated signed-token
integration tests and the ingestion CLI. Historical examples become stale; current/forecast
correctly return unavailable outside their freshness windows.
