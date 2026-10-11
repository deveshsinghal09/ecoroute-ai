# Collector success and downstream verification - 11 October 2026

## Follow-up verified result

Customer-managed diagnostic reads are now effective. Safe raw/ notification prefix deployed;
subsequent real objects reached natural cleaning. Worker curated log and metadata confirm
192forward-forecast records/2Parquet partitions, zero missing/flagged values. Separate date-window
collection produced288modeled records/3partitions. No direct cleaning/queue purge/replay used.
check_live_services.py --pipeline --profile dev-admin now returns curated_metadata_verified.
Real Drive/Walk/Cycle previews have full PM2.5 coverage with low confidence/coarse-grid warnings.
Schedules remain disabled. Earlier raw-only checks below are superseded historical evidence.


User's Console result shows successful collector execution, cached=false and a raw Open-Meteo
object dated2026-10-11. Structured collector logs independently show execution at14:03:42UTC.
This verifies raw collection/persistence, not pollution curation, route exposure or observed data.

Read-only CLI checks using non-root dev-admin in Mumbai:

- QUALITY#open_meteo and FILES#open_meteo queried consistently: no rows returned.
- Collector log contains the matching successful invocation; no runtime error seen.
- Cleaning Worker log: no events in the queried fifteen-minute window.
- CloudFormation confirms the Worker and its SQS mapping exist.
- Direct S3 notification, SQS attributes, Worker configuration and mapping reads: AccessDenied.

The exact downstream cause is **not yet known**. No new collection, message receive/delete,
direct cleaning invocation, notification update, schedule, IAM change or deployment was performed.

For an authorized administrator:

1. IAM -> Policies -> Create policy -> JSON. Use a customer-managed policy: this user's
   aggregate inline-policy size already reaches the 2,048-character limit.
2. Copy the entire config/iam-ingestion-diagnostics.json contents into the editor.
3. Review and name EcoRouteIngestionDiagnostics; create. Then IAM -> Users -> devesh_eco ->
   Permissions -> Add permissions -> Attach policies directly -> select that policy -> Add.
   Keep EcoRouteIntegrationChecks attached; creation alone does not grant user permissions.
4. This adds read-only access to the exact environmental bucket notification, two queue attributes,
   Worker configuration and one event-source-mapping ARN. It grants no object data reads, secrets,
   queue consumption/deletion, trigger mutation or paid compute provisioning.
5. Remove the diagnostic policy when troubleshooting is complete. If resources are recreated,
   inventory and re-scope actual ARNs before reusing the file. No wildcard permission is proposed.

Alternative Console checks in Mumbai, without making unreviewed changes:

- S3 -> ecoroutedata-airdatad62c85d3-aqvlom4hqoks -> Properties -> Event notifications:
  object-created events with prefix raw/ should target the existing Tasks queue. The cleaner
  validates raw/source= separately. Special characters in notification filters require encoding.
- Lambda -> EcoRouteCore-Worker11F36D0F-LhvCNZsSHtKA -> Configuration -> Triggers:
  inspect the Tasks SQS trigger state and last processing result.
- SQS -> EcoRouteData-Tasks0BA6A452-MJCcBKBl8cek -> Monitoring/Access policy:
  inspect available/in-flight counts and existing S3 producer permission; do not purge the queue.
- CloudWatch -> EcoRouteCore-WorkerLogsC1193B08-hbhQEJDem4io: inspect cleaning_failed/curated events.

Only after natural curation is verified should another route comparison be used as a pollution
coverage test. Do not bypass SQS with a direct cleaner call to claim the event pipeline worked.
Open-Meteo output remains a coarse modeled forecast, not a roadside observation or an AQI reading.

AWS references: [Lambda mapping authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html),
[S3 event destinations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html).
