"""Geodesic helpers, built on ``pyproj.Geod`` (WGS84).

``water-path``'s ``geo.py`` uses a spherical (haversine) approximation — good enough for its
validation-only use. Here we sample real fields onto real route geometry, so we use the geodesic
(ellipsoidal) distance instead.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pyproj import Geod

from water_routefinder.network import Point

_GEOD = Geod(ellps="WGS84")


def geodesic_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Geodesic distance between two points, in kilometres."""
    _, _, dist_m = _GEOD.inv(lon1, lat1, lon2, lat2)
    return dist_m / 1000.0


def densify_line(points: Sequence[Point], target_m: float) -> list[Point]:
    """Insert vertices so consecutive spacing is <= ``target_m``, keeping every original vertex.

    Degenerate cases: a 2-point line with a single short segment gets no extra points if it's
    already <= target_m; a route already denser than the target is returned unchanged.
    """
    if target_m is None or target_m <= 0:
        return list(points)
    if len(points) < 2:
        return list(points)

    out: list[Point] = [points[0]]
    for a, b in zip(points, points[1:]):
        az12, _, seg_m = _GEOD.inv(a.lon, a.lat, b.lon, b.lat)
        n_extra = math.ceil(seg_m / target_m) - 1
        if n_extra > 0:
            for lon, lat in _GEOD.npts(a.lon, a.lat, b.lon, b.lat, n_extra):
                out.append(Point(lat=lat, lon=lon))
        out.append(b)
    return out


def cumulative_s_along_m(points: Sequence[Point]) -> list[float]:
    """Cumulative geodesic distance (metres) from the first point to each point in turn."""
    if not points:
        return []
    s = [0.0]
    for a, b in zip(points, points[1:]):
        _, _, seg_m = _GEOD.inv(a.lon, a.lat, b.lon, b.lat)
        s.append(s[-1] + seg_m)
    return s
