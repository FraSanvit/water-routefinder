"""Tests on the *shape* of network input files, independent of any processing.

Complements tests/unit/ (which tests processing, given already-valid inputs) — this file feeds
deliberately broken ``routes.geojson``/``harbours.csv`` and asserts each is rejected with a clear
error, per water_routefinder.io / water_routefinder.network (vendored from water-path).
"""

from __future__ import annotations

import json

import pytest

from water_routefinder.io import NetworkInputError, load_network

_HARBOURS = (
    "harbour_id,name,lat,lon,country_code\nA,Harbour A,53.30,-6.25,IE\nB,Harbour B,53.35,-6.10,IE\n"
)


def _routes_geojson(coordinates=None, origin="A", destination="B"):
    coordinates = coordinates or [[-6.25, 53.30], [-6.10, 53.35]]
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"route_id": "R1", "origin": origin, "destination": destination},
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                }
            ],
        }
    )


def _write(tmp_path, *, harbours=_HARBOURS, routes=None):
    (tmp_path / "harbours.csv").write_text(harbours, encoding="utf-8")
    (tmp_path / "routes.geojson").write_text(routes or _routes_geojson(), encoding="utf-8")
    return tmp_path


def test_valid_minimal_network_loads(tmp_path):
    net = load_network(_write(tmp_path))
    assert len(net.harbours) == 2
    assert len(net.routes) == 1


def test_missing_harbours_column_is_rejected(tmp_path):
    broken = "harbour_id,name,lon\nA,Harbour A,-6.25\n"
    with pytest.raises(NetworkInputError, match="missing required column"):
        load_network(_write(tmp_path, harbours=broken))


def test_empty_harbours_file_is_rejected(tmp_path):
    header_only = "harbour_id,name,lat,lon,country_code\n"
    with pytest.raises(NetworkInputError, match="no harbour rows"):
        load_network(_write(tmp_path, harbours=header_only))


def test_non_numeric_lat_is_rejected(tmp_path):
    broken = "harbour_id,name,lat,lon,country_code\nA,Harbour A,north,-6.25,IE\n"
    with pytest.raises(NetworkInputError, match="not a number"):
        load_network(_write(tmp_path, harbours=broken))


def test_single_vertex_linestring_is_rejected(tmp_path):
    with pytest.raises(NetworkInputError, match=">= 2 coordinates"):
        load_network(_write(tmp_path, routes=_routes_geojson(coordinates=[[-6.25, 53.30]])))


def test_dangling_harbour_reference_is_rejected(tmp_path):
    with pytest.raises(NetworkInputError, match="not a known harbour"):
        load_network(_write(tmp_path, routes=_routes_geojson(destination="NOPE")))


def test_route_endpoint_far_from_harbour_is_rejected(tmp_path):
    # Destination harbour B is at (53.35, -6.10); path ends far away instead.
    far = _routes_geojson(coordinates=[[-6.25, 53.30], [-5.50, 52.50]])
    with pytest.raises(NetworkInputError, match="km from harbour"):
        load_network(_write(tmp_path, routes=far))


def test_duplicate_harbour_id_is_rejected(tmp_path):
    dupe = "harbour_id,name,lat,lon,country_code\nA,Harbour A,53.30,-6.25,IE\nA,Harbour A2,53.35,-6.10,IE\n"
    with pytest.raises(NetworkInputError, match="duplicate harbour_id"):
        load_network(_write(tmp_path, harbours=dupe))


def test_malformed_json_is_rejected(tmp_path):
    with pytest.raises(NetworkInputError, match="invalid JSON"):
        load_network(_write(tmp_path, routes="{not json"))


def test_missing_files_are_rejected(tmp_path):
    with pytest.raises(NetworkInputError, match="not found"):
        load_network(tmp_path)
