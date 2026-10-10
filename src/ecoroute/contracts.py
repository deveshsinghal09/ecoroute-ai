"""Explicit response documentation for dynamic envelopes; shared runtime/export OpenAPI."""
from copy import deepcopy


def obj(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": True}


STRING = {"type": "string"}
BOOL = {"type": "boolean"}
NUMBER = {"type": "number"}
NULL_NUMBER = {"anyOf": [NUMBER, {"type": "null"}]}
OBJECT = {"type": "object", "additionalProperties": True}
ARRAY = {"type": "array", "items": OBJECT}


def ref(name):
    return {"$ref": "#/components/schemas/" + name}


SCHEMAS = {
    "ApiError": obj({"error": obj({"code": STRING, "request_id": STRING}, ("code", "request_id"))}, ("error",)),
    "GeoJsonLineString": obj({"type": {"const": "LineString"}, "coordinates": {"type": "array", "minItems": 2,
        "items": {"type": "array", "prefixItems": [NUMBER, NUMBER], "minItems": 2, "maxItems": 2}}}, ("type", "coordinates")),
    "PollutantEstimate": obj({"value_ug_m3": NULL_NUMBER, "source": {"anyOf": [STRING, {"type": "null"}]}, "status": STRING,
        "reported_at": {"anyOf": [STRING, {"type": "null"}]}, "collected_at": {"anyOf": [STRING, {"type": "null"}]}, "resolution_km": NULL_NUMBER,
        "confidence": STRING, "warnings": {"type": "array", "items": STRING}}, ("value_ug_m3",)),
    "RouteSegment": obj({"geometry": ref("GeoJsonLineString"), "segment_index": {"type": "integer"},
        "length_m": NUMBER, "duration_s": NUMBER, "arrival_at": STRING, "end_at": STRING,
        "sample_at": STRING, "sample_position": {"type": "array", "items": NUMBER},
        "pollutants": obj({p: ref("PollutantEstimate") for p in ("pm25", "pm10", "no2", "o3")}),
        "pm25_exposure_ug_h_m3": NULL_NUMBER}, ("geometry", "duration_s", "pollutants", "pm25_exposure_ug_h_m3")),
    "ScoredRoute": obj({"route_id": STRING, "geometry": ref("GeoJsonLineString"), "duration_s": NUMBER,
        "distance_m": NUMBER, "estimated_pm25_exposure_ug_h_m3": NULL_NUMBER,
        "known_pm25_exposure_ug_h_m3": NUMBER, "pm25_coverage_fraction": NUMBER,
        "relative_exposure_change_percent": NULL_NUMBER, "baseline_route_id": STRING,
        "confidence": STRING, "routing_source": OBJECT, "source_metadata": ARRAY,
        "segments": {"type": "array", "items": ref("RouteSegment")}, "recommendation_reason": STRING},
        ("route_id", "geometry", "duration_s", "distance_m", "estimated_pm25_exposure_ug_h_m3")),
    "RouteComparison": obj({"routes": {"type": "array", "items": ref("ScoredRoute")},
        "selected_route_id": STRING, "baseline_route_id": STRING, "recommended_route_ids": OBJECT,
        "baseline_definition": STRING, "score_definition": STRING, "spatial_differentiation": STRING,
        "cache_hit": BOOL}, ("routes", "selected_route_id", "baseline_route_id", "recommended_route_ids")),
    "OwnedRecord": obj({"id": STRING, "expires_at": {"anyOf": [{"type": "integer"}, STRING]}}),
    "DataEnvelope": obj({"status": STRING, "records": ARRAY, "truncated": BOOL, "attribution": STRING, "limitations": STRING}, ("status", "records", "truncated")),
    "DepartureAnalysis": obj({"departures": ARRAY, "lowest_estimated_exposure_departure": {"anyOf": [STRING, {"type": "null"}]}, "baseline_definition": STRING}, ("departures",)),
    "Explanation": obj({"mode": STRING, "explanation": STRING, "supporting_metrics": ARRAY,
        "fallback_reason": {"anyOf": [STRING, {"type": "null"}]}, "ranking_changed": {"const": False}}, ("mode", "explanation", "supporting_metrics")),
    "AlertEvaluation": obj({"evaluation": OBJECT, "alert": {"anyOf": [OBJECT, {"type": "null"}]}, "created": BOOL,
        "notification": obj({"status": STRING, "delivered": {"const": False}})}, ("evaluation", "alert", "created")),
    "WearableRegistration": obj({"device_id": STRING, "consent": OBJECT, "mqtt_topic": STRING,
        "mqtt_client_id": STRING, "hardware_connected": {"const": False}}, ("device_id", "consent", "hardware_connected")),
    "WearableAcceptance": obj({"event_id": STRING, "device_id": STRING, "accepted": BOOL, "duplicate": BOOL,
        "expires_at": {"type": "integer"}}, ("event_id", "device_id", "accepted", "duplicate")),
    "StationPrediction": obj({"station_id": STRING, "value_ug_m3": NUMBER, "unit": {"const": "ug/m3"},
        "horizon_hours": {"const": 1}, "model_version": STRING, "forecast_type": {"const": "station_prediction"},
        "issued_at": STRING, "valid_at": STRING, "confidence": STRING}, ("station_id", "value_ug_m3", "model_version", "valid_at")),
}


def response_schema(path, method):
    relative = path.removeprefix("/api/v1/")
    exact = {
        "routes/preview": ref("RouteComparison"),
        "health": obj({"status": STRING, "profile": STRING, "phase": STRING, "live_domain_providers": BOOL}),
        "ready": obj({"status": STRING}), "routes/compare": ref("RouteComparison"),
        "routes/optimize": obj({"recommended_route": ref("ScoredRoute"), "recommended_route_ids": OBJECT,
            "baseline_route_id": STRING, "score_definition": STRING}),
        "routes/exposure": ref("ScoredRoute"), "routes/departure-time-analysis": ref("DepartureAnalysis"),
        "routes/predict-departure-times": ref("DepartureAnalysis"),
        "routes/{route_id}": {**SCHEMAS["ScoredRoute"], "description": "Segments omitted; use dedicated segments endpoint."},
        "routes/{route_id}/segments": obj({"route_id": STRING, "segments": {"type": "array", "items": ref("RouteSegment")}, "total": {"type": "integer"}, "next_offset": NULL_NUMBER}),
        "air-quality/stations": obj({"status": STRING, "stations": ARRAY, "truncated": BOOL}),
        "data/quality": obj({"status": STRING, "reports": ARRAY, "truncated": BOOL}),
        "ml/status": obj({"status": STRING, "verified_models": {"type": "integer"}, "horizon_hours": {"const": 1}, "reason": {"anyOf": [STRING, {"type": "null"}]}}),
        "ml/models": obj({"models": ARRAY}), "ml/metrics": obj({"model_version": STRING, "metrics": OBJECT, "limitations": {"type": "array", "items": STRING}}),
        "ml/predict": ref("StationPrediction"), "ml/batch-predict": obj({"results": ARRAY, "execution": STRING, "horizon_hours": {"const": 1}}),
        "devices/register": ref("WearableRegistration"), "wearables/measurements": ref("WearableAcceptance"),
        "wearables/consent": obj({"device_id": STRING, "consent": OBJECT, "revision": {"type": "integer"}, "warning": STRING}),
        "wearables/latest": obj({"status": STRING, "measurement": {"anyOf": [OBJECT, {"type": "null"}]}}),
        "wearables/history": obj({"measurements": ARRAY, "next_cursor": {"anyOf": [STRING, {"type": "null"}]}, "truncated": BOOL}),
        "wearables/data": obj({"status": STRING}),
        "journeys/{journey_id}/wearable-correlation": obj({"journey_id": STRING, "device_id": STRING, "samples": ARRAY, "paired_count": {"type": "integer"}, "exposure_index": {"type": "null"}, "medical_stress_score": {"type": "null"}}),
        "ai/explain-route": ref("Explanation"), "alerts/evaluate": ref("AlertEvaluation"),
        "alerts": obj({"alerts": ARRAY, "truncated": BOOL}), "alerts/{alert_id}": ref("OwnedRecord"),
        "alerts/preferences": obj({"alerts_enabled": BOOL, "channel": {"enum": ["in_app", "sms"]}}),
        "schools/compare-routes": obj({"school_id": STRING, "comparison": ref("RouteComparison"), "confidence": STRING, "advisory": STRING}),
        "schools/forecast": obj({"school_id": STRING, "commute_start": STRING, "forecast": OBJECT, "official_closure_status": {"const": "not_provided"}, "warning": STRING}),
        "workflows/status": obj({"configured": BOOL, "runs": ARRAY, "truncated": BOOL, "deployment_verified": {"const": False}, "schedule_enablement": STRING}),
        "trips": ref("OwnedRecord"), "trips/{trip_id}": ref("OwnedRecord"),
    }
    if relative in {"air-quality/current", "air-quality/forecast", "air-quality/history"}:
        return ref("DataEnvelope")
    if relative not in exact:
        # Explicit legacy placeholder APIs have no successful data product.
        if relative in {"navigation/routes", "air-quality", "predictions", "school-safety", "wearables/telemetry"}:
            return None
        raise ValueError("undocumented_response_contract: " + method + " " + path)
    return exact[relative]


def enrich(schema):
    schema = deepcopy(schema)
    schema["components"]["schemas"].update(SCHEMAS)
    from ecoroute.environment.schema import AirRecord
    schema["components"]["schemas"]["AirRecord"] = AirRecord.model_json_schema()
    schema["components"]["schemas"]["AirRecord"]["properties"]["age_seconds"] = {"type": "integer", "minimum": 0}
    schema["components"]["schemas"]["DataEnvelope"]["properties"]["records"] = {"type": "array", "items": ref("AirRecord")}
    schema["servers"] = [{"url": "http://127.0.0.1:8000", "description": "Local backend; deployed URL not verified"}]
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "delete"}:
                continue
            response = response_schema(path, method)
            operation["x-ecoroute-scope"] = ("ecoroute/read" if method == "get" else "ecoroute/write") if operation.get("security") else None
            for code in ("401", "403", "404", "409", "413", "422", "429", "500", "503"):
                operation["responses"][code] = {"description": "Normalized error; endpoint-dependent", "content": {"application/json": {"schema": ref("ApiError")}}}
            if response is None:
                operation["deprecated"] = True
                operation["description"] = "Legacy unconnected placeholder or retired telemetry API; returns 503/410 after authentication/validation."
                for code in ("200", "201"):
                    operation["responses"].pop(code, None)
                operation["responses"]["410"] = {"description": "Retired endpoint", "content": {"application/json": {"schema": ref("ApiError")}}}
            else:
                for code, value in operation["responses"].items():
                    if code.startswith("2"):
                        value["content"] = {"application/json": {"schema": response}}
                if path in {"/api/v1/trips", "/api/v1/devices/register", "/api/v1/wearables/measurements"}:
                    operation["responses"]["200"] = {"description": "Identical idempotent replay", "content": {"application/json": {"schema": response}}}
            if path == "/api/v1/ready":
                operation["responses"]["503"] = {"description": "Dependency or auth configuration not ready", "content": {"application/json": {"schema": response}}}
    return schema
