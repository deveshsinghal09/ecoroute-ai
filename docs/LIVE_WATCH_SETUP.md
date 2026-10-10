# Live wearable connection

Verified on 2026-10-11: OPPO Reno8 5G is authorized through Android Debug Bridge and nRF Connect
is installed. The connected watch session receives notifications on vendor characteristic 0x0AF7.
The discovered list showed Generic Access 0x1800, Generic Attribute 0x1801 and vendor service
0x0AF0 with 0x0AF6/0x0AF7/0x0AF1/0x0AF2 characteristics. Standard Heart Rate 0x180D/0x2A37
was not found in that session. **No heart rate, steps, SpO2 or other health metric has been decoded
or verified from this Noise watch.** Unknown bytes were not mapped to measurements or stored in
the telemetry backend. USB file transfer/debugging does not turn nRF Connect into a health API.

## Standard sensor connection in the website

1. Open http://127.0.0.1:5173/ in a Bluetooth-capable Chrome/Edge browser, then Wearable.
   On Android, use Chrome with an HTTPS/localhost origin. Embedded browsers may not support
   Web Bluetooth; the interface gives setup guidance when it is unavailable.
2. Enable laptop Bluetooth and keep the sensor close. For the direct laptop path, disconnect
   other BLE clients such as nRF Connect/NoiseFit temporarily if they prevent a connection.
   Do not delete watch pairing, factory-reset it or change firmware.
3. Check **Allow this browser to read my watch over Bluetooth**, then **Connect Bluetooth**.
   Choose your own watch/sensor in the browser's device chooser. No connection occurs on page load.
4. The adapter accesses only standard Heart Rate and optional Battery services. It requires actual
   Heart Rate Measurement notifications. Devices that expose only proprietary services stop with
   a clear error. This path is not claimed compatible with the verified Noise session above.
5. The 3D screen and accessible readout update only received values. Missing oxygen, sleep,
   steps, calories, activity and health scores stay unavailable. The chart plots received BPM
   against browser receipt time; it is not an ECG. No medical/causal pollution score is computed.
6. Heart rate becomes unavailable after 60 seconds without a valid notification. Battery expires
   after five minutes. These are UI freshness windows, not clinical thresholds. The standard
   characteristic provides no observation timestamp: receipt time is explicitly labeled.
7. **Disconnect & clear**, unchecking Bluetooth consent, leaving Wearable or reloading closes
   the BLE session and clears browser-held readings. No localStorage, file, public endpoint or
   AWS upload is used by this connection. Up to 60 trend samples are held in memory only.

Supported formats: unsigned 8/16-bit BPM, little-endian optional fields, optional RR intervals in
1/1024-second units. Truncated packets, out-of-range BPM and explicit missing skin contact are
rejected. Energy Expended is cumulative kJ; it is not relabeled daily calories. Optional battery
requires a valid one-byte percentage. No custom GATT commands or firmware writes are sent.

## Phone and nRF Connect prerequisites

Install Android SDK Platform-Tools from https://developer.android.com/tools/releases/platform-tools.
On OPPO: Settings → Additional/System settings → Developer options → USB debugging. Use a USB data
cable, unlock, and approve this laptop's RSA fingerprint. File-transfer mode alone is insufficient.
If unauthorized, reconnect; if necessary revoke prior debugging authorizations and approve again.
Do not root the phone, extract application databases or forward phone-wide logs.

Safe metadata check from the repository root:
```
.venv/Scripts/python.exe scripts/check_watch_connection.py
```
Optional --adb accepts the exact local platform-tools/adb path. The script prints readiness and
nRF package presence, not serials, phone contents, secrets or health values. Its success means
ADB access only. To inspect supported services manually, open the connected device's **Client**
tab in nRF Connect and look for Heart Rate 0x180D / Heart Rate Measurement 0x2A37 with Notify.
Do not use nRF Connect's sample HR peripheral/server feature as actual watch measurements.
Disconnect USB and revoke debugging authorizations when no longer needed.

## Noise/vendor bridge: currently blocked

Required evidence before implementing a Noise decoder:

- Exact firmware/model and a documented, authorized SDK/API or verified companion export.
- Documented service/characteristic IDs, packet types, units, timestamps, contact/quality flags
  and permissions. The UUID alone does not establish field meaning.
- If NoiseFit Assist supports Health Connect/Google Fit/export, verify that it actually supplies
  the required records and timestamps. No such support is verified here. An authorized Android
  bridge must request only selected permissions; API keys/tokens must not be pasted in chat.
- Validate decoded records against the watch/companion display with matching timestamps before
  labeling them live. Unsupported metrics remain null. No guessed offsets/protocol writes.

A future bridge reuses the existing authenticated HTTPS flow:
POST /api/v1/devices/register (bridge=companion_https), POST /api/v1/wearables/consent and
POST /api/v1/wearables/measurements. Bodies follow docs/openapi.json; owner user_id must match
the verified Cognito subject. Preserve source record ID, actual observed timestamp and sensor
provenance, synthetic=false. Steps need daily_total versus interval_count semantics. GPS requires
separate consent/accuracy. Existing idempotency, retention, deletion and ownership checks apply.
Use temporary Cognito access tokens in an approved platform keystore; never hardcode AWS keys.

The existing **Read latest measurement** button remains Cognito-protected and now maps verified,
non-synthetic heart rate/daily steps into the 3D display. It is a manual snapshot, not a streaming
phone bridge. Backend timestamps are labeled reported, stale heart rate is not shown as current,
and old UTC-day step counts are omitted. No raw BLE packets are accepted by that endpoint.

## Credentials, permissions and costs

Local BLE display needs no AWS credential, nRF password, X.509 certificate or provider key. It
needs physical device selection, Bluetooth permission and the explicit in-app consent above.
Cloud telemetry still needs COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, the public frontend Cognito
domain/client/callback configuration, an owned registered device and telemetry consent. JWTs are
secret; store in memory/platform keystores, not chat/Git. No new public health-data access exists.
For approved AWS hosting, reuse existing Wearables DynamoDB/S3/IoT roles and scoped permissions
in WEARABLES.md/CREDENTIALS_CHECKLIST.md; this change adds no IAM role or policy.

No AWS action, paid service, APK install, model training or notification was performed. Local BLE
and ADB checks incur no AWS usage. Any future cloud API/DynamoDB/IoT/S3 usage has the documented
costs and requires configured authorization; no hardware private keys were requested.

## Actual validation

Frontend tests use synthetic sensor events in an isolated test browser only. They verify consent,
updates, unknown-service rejection, missing fields, disconnect/revocation and stale readings.
They do not establish Noise compatibility or actual measured-data ingestion. ADB/nRF hardware
inspection verified only connection/notification transport and the proprietary characteristic list.

Official references:
- https://developer.chrome.com/docs/capabilities/bluetooth
- https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/HRS_v1.0/out/en/index-en.html
- https://developer.android.com/studio/run/device
- https://github.com/nordicsemi/Android-nRF-Connect/blob/main/documentation/README.md
- https://support.gonoise.com/support/solutions/articles/47001212418-my-watch-is-not-pairing-with-bluetooth-auto-disconnect
