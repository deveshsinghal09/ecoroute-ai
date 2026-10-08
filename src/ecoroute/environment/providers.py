"""Provider contracts verified against official docs; no credentials in envelopes or errors."""
import json
import math
import time
from typing import Protocol

import httpx

from ecoroute.environment.schema import make_record, now, utc

VARIABLES = {"pm2_5": "pm25", "pm10": "pm10", "nitrogen_dioxide": "no2", "ozone": "o3"}


class ProviderError(Exception):
    pass


class MissingCredential(ProviderError):
    pass


class SchemaChanged(ProviderError):
    pass


class Provider(Protocol):
    def fetch(self, **kwargs) -> dict: ...
    def clean(self, envelope: dict) -> list: ...


class JsonTransport:
    def __init__(self, client=None, reserve=lambda: None, interval=2.1, sleep=time.sleep):
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.reserve, self.interval, self.sleep = reserve, interval, sleep
        self.last = 0.0

    def get(self, url, *, params=None, headers=None):
        for attempt in range(3):
            self.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.reserve()  # counts every attempted HTTP call, including failed/retried calls
            self.last = time.monotonic()
            try:
                response = self.client.get(url, params=params, headers=headers)
            except httpx.TransportError:
                if attempt == 2:
                    raise ProviderError("provider_network_unavailable") from None
                self.sleep(2 ** attempt)
                continue
            if response.status_code in (401, 403):
                raise MissingCredential("provider_auth_or_plan_denied")
            if response.status_code == 429:
                # Never immediate retry a quota rejection; next bounded run can retry later.
                raise ProviderError("provider_rate_limited")
            if response.status_code >= 500 and attempt < 2:
                self.sleep(2 ** attempt)
                continue
            if response.status_code != 200:
                raise ProviderError(f"provider_http_{response.status_code}")
            if len(response.content) > 5 * 1024 * 1024:
                raise ProviderError("provider_payload_too_large")
            try:
                payload = response.json()
            except ValueError:
                raise SchemaChanged("invalid_provider_json") from None
            if not isinstance(payload, dict) or payload.get("error"):
                raise SchemaChanged("unexpected_provider_envelope")
            return payload
        raise ProviderError("provider_unavailable")


def grid(latitude, longitude):
    if not math.isfinite(latitude + longitude) or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("invalid coordinates")
    # Stable request lattice, not a claim that these are the provider's native grid centers.
    lat = round(round(latitude / 0.4) * 0.4, 4)
    lon = round(round(longitude / 0.4) * 0.4, 4)
    return min(90, max(-90, lat)), min(180, max(-180, lon))


class OpenMeteo:
    def __init__(self, transport=None, api_key=None):
        self.transport = transport or JsonTransport()
        self.api_key = api_key

    def fetch(self, *, latitude=28.6139, longitude=77.2090, start=None, end=None):
        lat, lon = grid(latitude, longitude)
        params = {"latitude": lat, "longitude": lon, "hourly": ",".join(VARIABLES),
                  "domains": "cams_global", "timezone": "GMT", "timeformat": "unixtime",
                  "cell_selection": "nearest"}
        if start and end:
            params.update(start_date=start, end_date=end)
        else:
            params["forecast_days"] = 2
        safe_params = dict(params)
        host = "air-quality-api.open-meteo.com"
        if self.api_key:
            host = "customer-air-quality-api.open-meteo.com"
            params["apikey"] = self.api_key
        payload = self.transport.get(f"https://{host}/v1/air-quality", params=params)
        return {"schema_version": 1, "source": "open_meteo", "collected_at": now().isoformat(),
                "request": safe_params, "historical": bool(start), "payload": payload,
                "attribution": "Open-Meteo; Copernicus Atmosphere Monitoring Service (CAMS)",
                "license": "CC BY 4.0; Open-Meteo service terms apply"}

    def clean(self, envelope):
        try:
            p = envelope["payload"]
            if p.get("utc_offset_seconds") != 0:
                raise ValueError("unexpected timezone")
            lat, lon = p["latitude"], p["longitude"]
            times, units = p["hourly"]["time"], p["hourly_units"]
            if not times or len(times) != len(set(times)):
                raise ValueError("empty or duplicate times")
            result = []
            for variable, pollutant in VARIABLES.items():
                values = p["hourly"][variable]
                if len(values) != len(times):
                    raise ValueError("array length drift")
                for timestamp, value in zip(times, values, strict=True):
                    reported = utc(timestamp)
                    kind = "modeled" if envelope.get("historical") or reported < utc(envelope["collected_at"]) else "forecast"
                    result.append(make_record(source="open_meteo", kind=kind, pollutant=pollutant,
                        value=value, unit=units[variable], reported_at=timestamp,
                        collected_at=envelope["collected_at"], latitude=lat, longitude=lon,
                        location_id=f"cams_global:{lat:.4f}:{lon:.4f}", resolution_km=45,
                        native_interval_hours=3, model="CAMS global via Open-Meteo (requested cams_global)",
                        provenance={"attribution": envelope["attribution"], "license": envelope["license"],
                            "request": envelope["request"], "model_run_time": "not_supplied",
                            "temporal_note": "Hourly API output; underlying global model is 3-hourly"}))
            return result
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise SchemaChanged("open_meteo_schema_changed") from exc


class OpenAQ:
    def __init__(self, api_key, transport=None):
        if not api_key or api_key.startswith(("<", "YOUR_")):
            raise MissingCredential("OPENAQ_API_KEY_missing")
        self.key = api_key
        self.transport = transport or JsonTransport()

    def get(self, path, params=None):
        result = self.transport.get("https://api.openaq.org/v3/" + path, params=params,
                                    headers={"X-API-Key": self.key})
        if not isinstance(result.get("results"), list) or not isinstance(result.get("meta"), dict):
            raise SchemaChanged("openaq_results_missing")
        return result

    def stations(self, page=1, limit=100):
        return self.get("locations", {"bbox": "76.8,28.3,77.6,29.0", "limit": limit, "page": page})

    def fetch(self, *, location_id, sensor_id, start, end, page=1, limit=100):
        location = self.get(f"locations/{int(location_id)}")["results"]
        if len(location) != 1:
            raise SchemaChanged("openaq_location_missing")
        station = location[0]
        if not any(s.get("id") == sensor_id for s in station.get("sensors", [])):
            raise SchemaChanged("sensor_not_in_location")
        payload = self.get(f"sensors/{int(sensor_id)}/measurements",
                           {"datetime_from": start, "datetime_to": end, "page": page, "limit": limit})
        return {"schema_version": 1, "source": "openaq", "collected_at": now().isoformat(),
                "request": {"location_id": location_id, "sensor_id": sensor_id, "start": start,
                            "end": end, "page": page, "limit": limit},
                "station": station, "payload": payload, "attribution": "OpenAQ and original data provider"}

    def clean(self, envelope):
        try:
            station = envelope["station"]
            result = []
            for item in envelope["payload"]["results"]:
                parameter = item["parameter"]
                if parameter["name"] not in {"pm25", "pm10", "no2", "o3"}:
                    continue
                coordinates = item.get("coordinates") or station["coordinates"]
                record = make_record(source="openaq", kind="observed", pollutant=parameter["name"],
                    value=item["value"], unit=parameter["units"],
                    reported_at=item["period"]["datetimeTo"]["utc"],
                    period_start=utc(item["period"]["datetimeFrom"]["utc"]),
                    collected_at=envelope["collected_at"], latitude=coordinates["latitude"],
                    longitude=coordinates["longitude"], location_id=str(station["id"]),
                    sensor_id=str(envelope["request"]["sensor_id"]),
                    provider_quality=json.dumps(item.get("flagInfo", item.get("flags", "not_supplied")), sort_keys=True),
                    provenance={"provider": station.get("provider"), "owner": station.get("owner"),
                        "licenses": station.get("licenses", []), "coverage": item.get("coverage"),
                        "period": item["period"], "station_name": station.get("name"),
                        "is_mobile": station.get("isMobile"), "is_monitor": station.get("isMonitor"),
                        "attribution": envelope["attribution"]})
                if item.get("flagInfo", {}).get("hasFlags") is True:
                    record.quality_flags.append("provider_flagged")
                    record.value = None
                result.append(record)
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaChanged("openaq_schema_changed") from exc




def cleaner(envelope):
    if envelope["source"] == "open_meteo":
        return OpenMeteo().clean(envelope)
    if envelope["source"] == "openaq":
        # Cleaning saved raw data does not require a provider credential or network.
        return OpenAQ.__new__(OpenAQ).clean(envelope)
    raise SchemaChanged("unknown_source")
