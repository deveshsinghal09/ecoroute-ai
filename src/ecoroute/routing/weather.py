"""Bounded representative-grid weather; preference costs are not medical risk scores."""

import math
from datetime import UTC, datetime, timedelta

import httpx
from botocore.exceptions import BotoCoreError, ClientError

from ecoroute.environment.schema import utc


class RouteWeather:
    def __init__(self, reserve=lambda: None, client=None, clock=lambda: datetime.now(UTC)):
        self.reserve, self.clock = reserve, clock
        self.client = client or httpx.Client(timeout=3, follow_redirects=False)
        self.cache = {}

    def sample(self, position, stamp):
        # Request coalescing cells, NOT a claim about the provider's native resolution.
        cell = (round(position[1], 1), round(position[0], 1))
        now = self.clock()
        cached = self.cache.get(cell)
        if not cached or now - cached[0] > timedelta(minutes=15):
            self.reserve()
            response = self.client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": cell[0],
                    "longitude": cell[1],
                    "timezone": "UTC",
                    "forecast_days": 3,
                    "wind_speed_unit": "ms",
                    "hourly": "temperature_2m,precipitation,wind_speed_10m",
                },
            )
            response.raise_for_status()
            if len(response.content) > 256 * 1024:
                raise ValueError("weather_response_too_large")
            data = response.json()
            units = data["hourly_units"]
            if (
                units.get("temperature_2m") != "°C"
                or units.get("precipitation") != "mm"
                or units.get("wind_speed_10m") != "m/s"
            ):
                raise ValueError("weather_units_changed")
            hourly = data["hourly"]
            times = hourly["time"]
            if not 1 <= len(times) <= 96 or any(
                len(hourly[key]) != len(times)
                for key in ("temperature_2m", "precipitation", "wind_speed_10m")
            ):
                raise ValueError("weather_schema_changed")
            if len(self.cache) >= 64:
                self.cache.clear()
            self.cache[cell] = (now, data)
            cached = self.cache[cell]
        data = cached[1]
        hourly = data["hourly"]
        stamps = [utc(t + "Z") for t in hourly["time"]]
        index = min(range(len(stamps)), key=lambda i: abs((stamps[i] - stamp).total_seconds()))
        if abs((stamps[index] - stamp).total_seconds()) > 1800:
            raise ValueError("weather_time_coverage_missing")
        temperature, rain, wind = [
            hourly[k][index] for k in ("temperature_2m", "precipitation", "wind_speed_10m")
        ]
        if (
            any(
                not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                for v in (temperature, rain, wind)
            )
            or not -80 <= temperature <= 65
            or not 0 <= rain <= 500
            or not 0 <= wind <= 100
        ):
            raise ValueError("weather_values_missing_or_invalid")
        return {
            "status": "forecast",
            "source": "open_meteo_weather",
            "attribution": "Open-Meteo / weather model providers",
            "reported_at": stamps[index].isoformat(),
            "collected_at": cached[0].isoformat(),
            "temperature_c": temperature,
            "precipitation_mm": rain,
            "wind_m_s": wind,
            "grid_position": [data["longitude"], data["latitude"]],
            "resolution": "model_dependent_not_street_level",
            "preference_cost": min(rain / 5, 1)
            + min(max(temperature - 28, 0) / 15, 1)
            + min(max(15 - temperature, 0) / 15, 1)
            + min(wind / 15, 1),
            "definition": "Preference heuristic: capped rain/5mm + heat above28C/15C + cold below15C/15C + wind/15m/s. Not a medical/safety threshold; sampled at route midpoint and midpoint arrival, not every street.",
        }


def attach_weather(routes, request, provider):
    cells = set()
    for route in routes:
        route["weather"] = {"status": "not_requested", "preference_cost": None}
        if not request.weather_weight:
            continue
        if provider is None:
            route["weather"]["status"] = "unavailable_disabled"
        else:
            try:
                points = route["geometry"]["coordinates"]
                position = points[len(points) // 2]
                cell = (round(position[1], 1), round(position[0], 1))
                cells.add(cell)
                if len(cells) > 3:
                    raise ValueError("weather_grid_request_limit")
                route["weather"] = provider.sample(
                    points[len(points) // 2],
                    request.departure_at + timedelta(seconds=route["duration_s"] / 2),
                )
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                IndexError,
                BotoCoreError,
                ClientError,
            ):
                route["weather"]["status"] = "unavailable_provider_or_schema"
        if route["weather"]["preference_cost"] is None:
            route["warnings"].append(
                "Requested weather preference unavailable; balanced recommendation requires all weighted inputs."
            )
