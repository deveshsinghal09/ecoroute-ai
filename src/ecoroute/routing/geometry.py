"""WGS84 lon/lat geometry and distance-based cuts along existing provider geometry."""

import math
from datetime import timedelta

from ecoroute.routing.models import RoutingError

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def decode_flexible(value):
    """Flexible Polyline v1 -> GeoJSON lon/lat, including safe consumption of optional Z.

    Format reference: aws-geospatial/polyline and heremaps/flexible-polyline (MIT-0/MIT).
    This implementation bounds varints and total points; unsupported headers fail closed.
    """
    if not isinstance(value, str) or not 2 <= len(value) <= 300000:
        raise RoutingError("invalid_provider_geometry", 502)
    index = 0

    def unsigned():
        nonlocal index
        total = 0
        for shift in range(0, 65, 5):
            if index >= len(value) or value[index] not in ALPHABET:
                raise RoutingError("invalid_provider_polyline", 502)
            digit = ALPHABET.index(value[index])
            index += 1
            total |= (digit & 31) << shift
            if not digit & 32:
                return total
        raise RoutingError("invalid_provider_polyline", 502)

    if unsigned() != 1:
        raise RoutingError("unsupported_polyline_version", 502)
    header = unsigned()
    precision, dimension = header & 15, (header >> 4) & 7
    if precision > 11 or header >> 11 or dimension in (4, 5):
        raise RoutingError("unsupported_polyline_header", 502)
    previous, points = [0, 0, 0], []
    while index < len(value):
        for axis in range(3 if dimension else 2):
            v = unsigned()
            previous[axis] += -(v // 2) - 1 if v & 1 else v // 2
        points.append([previous[1] / 10**precision, previous[0] / 10**precision])
        if len(points) > 10000:
            raise RoutingError("provider_geometry_too_large", 502)
    return validate_line(points)


def validate_line(points):
    if not isinstance(points, list) or not 2 <= len(points) <= 10000:
        raise RoutingError("invalid_provider_geometry", 502)
    cleaned = []
    for p in points:
        if (
            not isinstance(p, (list, tuple))
            or len(p) < 2
            or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in p[:2]
            )
            or not -180 <= p[0] <= 180
            or not -90 <= p[1] <= 90
        ):
            raise RoutingError("invalid_provider_coordinates", 502)
        point = [float(p[0]), float(p[1])]
        if not cleaned or point != cleaned[-1]:
            cleaned.append(point)
    if len(cleaned) < 2:
        raise RoutingError("zero_length_provider_geometry", 502)
    return cleaned


def distance(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(h)))


def interpolate(a, b, fraction):
    # Delhi-only short road edges; no antimeridian/polar interpolation is supported.
    return [a[i] + (b[i] - a[i]) * fraction for i in range(2)]


def split_line(points, maximum):
    """Retain every provider vertex; inserted cut points lie on existing road edges."""
    pieces, current, length = [], [points[0]], 0.0
    for start, end in zip(points[:-1], points[1:], strict=True):
        edge = distance(start, end)
        if edge > 10000:
            raise RoutingError("provider_geometry_gap", 502)
        while edge + length > maximum + 1e-6:
            take = maximum - length
            cut = interpolate(start, end, take / edge)
            current.append(cut)
            pieces.append((current, maximum))
            current, length, start = [cut], 0.0, cut
            edge = distance(start, end)
            if len(pieces) >= 600:
                raise RoutingError("route_segment_limit", 422)
        current.append(end)
        length += edge
    if length > 1e-6:
        pieces.append((current, length))
    return pieces


def midpoint(points):
    lengths = [distance(a, b) for a, b in zip(points[:-1], points[1:], strict=True)]
    left = sum(lengths) / 2
    for a, b, length in zip(points[:-1], points[1:], lengths, strict=True):
        if left <= length:
            return interpolate(a, b, left / length)
        left -= length
    return points[-1]


def segments(candidate, departure, maximum):
    output, elapsed = [], 0.0
    for leg in candidate["legs"]:
        pieces = split_line(leg["coordinates"], maximum)
        total = sum(length for _, length in pieces)
        for points, length in pieces:
            duration = leg["duration_s"] * length / total
            output.append(
                {
                    "segment_index": len(output),
                    "geometry": {"type": "LineString", "coordinates": points},
                    "length_m": length,
                    "duration_s": duration,
                    "arrival_at": (departure + timedelta(seconds=elapsed)).isoformat(),
                    "sample_at": (
                        departure + timedelta(seconds=elapsed + duration / 2)
                    ).isoformat(),
                    "end_at": (departure + timedelta(seconds=elapsed + duration)).isoformat(),
                    "sample_position": midpoint(points),
                }
            )
            elapsed += duration
    if len(output) > 600:
        raise RoutingError("route_segment_limit", 422)
    return output
