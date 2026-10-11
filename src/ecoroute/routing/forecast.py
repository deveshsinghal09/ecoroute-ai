"""Request-time gap filling with actual provider forecasts, never synthetic readings."""
import json
import logging
import time
from datetime import UTC, datetime, timedelta

import httpx
from botocore.exceptions import BotoCoreError, ClientError

from ecoroute.environment.providers import OpenMeteo, ProviderError, grid
from ecoroute.environment.repository import BudgetExceeded


class ForecastTransport:
    def __init__(self, client, reserve):
        self.client, self.reserve = client, reserve

    def get(self, url, *, params=None, headers=None):
        self.reserve()  # One attempt; no automatic retries or quota bypass.
        with self.client.stream("GET", url, params=params, headers=headers) as response:
            if response.status_code != 200:
                raise ProviderError("route_forecast_provider_unavailable")
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 256 * 1024:
                    raise ProviderError("route_forecast_payload_too_large")
                chunks.append(chunk)
        result = json.loads(b"".join(chunks))
        if not isinstance(result, dict) or result.get("error"):
            raise ProviderError("route_forecast_schema_changed")
        return result


class RouteForecast:
    def __init__(self, reserve, *, client=None, clock=lambda: datetime.now(UTC)):
        self.reserve, self.clock = reserve, clock
        self.client = client or httpx.Client(timeout=2, follow_redirects=False, trust_env=False)
        self.cache = {}  # Public grid forecasts only; no user IDs or route geometry.

    def supplement(self, index, routes):
        started, cells, extra = time.monotonic(), {}, []
        for pieces in routes:
            for piece in pieces:
                stamp = datetime.fromisoformat(piece["sample_at"])
                if index.sample(piece["sample_position"], stamp)["value_ug_m3"] is None:
                    lon, lat = piece["sample_position"]
                    cell = grid(lat, lon)
                    if cell not in cells and len(cells) < 3:
                        cells[cell] = None
        status = "not_needed"
        for cell in cells:
            if time.monotonic() - started >= 4:
                status = "request_deadline"
                break
            cached, now = self.cache.get(cell), self.clock()
            if cached and now - cached[0] < timedelta(hours=1):
                extra.extend(cached[1])
                status = "forecast_cache"
                continue
            try:
                adapter = OpenMeteo(ForecastTransport(self.client, self.reserve))
                rows = [r.model_dump(mode="json") for r in adapter.clean(
                    adapter.fetch(latitude=cell[0], longitude=cell[1]))]
                if len(self.cache) >= 64:
                    self.cache.clear()
                self.cache[cell] = (now, rows)
                extra.extend(rows)
                status = "provider_forecast"
            except BudgetExceeded:
                status = "request_allowance"
                break
            except (httpx.HTTPError, ProviderError, ValueError, KeyError, TypeError, BotoCoreError, ClientError):
                status = "provider_unavailable"
                break
        # The existing sampler still enforces geography, valid time, freshness and units.
        logging.getLogger("ecoroute.routing").info(json.dumps({"event": "route_forecast_lookup",
            "status": status, "cells_considered": len(cells), "records": len(extra)}))
        from ecoroute.routing.pollution import PollutionIndex
        return PollutionIndex(index.rows + extra, as_of=index.as_of, truncated=index.truncated), status
