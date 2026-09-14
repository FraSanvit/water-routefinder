from __future__ import annotations

import math

from water_routefinder.geo import cumulative_s_along_m, densify_line, geodesic_km
from water_routefinder.network import Point


def test_geodesic_km_one_degree_at_equator():
    # WGS84 equatorial circumference / 360 ~= 111.32 km.
    km = geodesic_km(0.0, 0.0, 0.0, 1.0)
    assert 110.5 < km < 111.5


def test_densify_line_respects_target_spacing():
    a = Point(lat=0.0, lon=0.0)
    b = Point(lat=0.0, lon=0.1)  # ~11.1 km
    points = densify_line([a, b], target_m=1000.0)
    assert points[0] == a
    assert points[-1] == b
    for p1, p2 in zip(points, points[1:]):
        assert geodesic_km(p1.lat, p1.lon, p2.lat, p2.lon) * 1000 <= 1000.0 + 1.0


def test_densify_line_leaves_already_dense_route_unchanged():
    a = Point(lat=0.0, lon=0.0)
    b = Point(lat=0.0, lon=0.001)  # ~111 m
    points = densify_line([a, b], target_m=1000.0)
    assert points == [a, b]


def test_densify_line_short_target_none_or_zero_is_a_no_op():
    a = Point(lat=0.0, lon=0.0)
    b = Point(lat=0.0, lon=0.1)
    assert densify_line([a, b], None) == [a, b]
    assert densify_line([a, b], 0.0) == [a, b]


def test_cumulative_s_along_m_is_monotonic_and_starts_at_zero():
    points = [Point(lat=0.0, lon=lon) for lon in (0.0, 0.05, 0.12, 0.2)]
    s = cumulative_s_along_m(points)
    assert s[0] == 0.0
    assert all(b > a for a, b in zip(s, s[1:]))
    assert math.isclose(s[-1], geodesic_km(0, 0, 0, 0.2) * 1000, rel_tol=1e-9)
