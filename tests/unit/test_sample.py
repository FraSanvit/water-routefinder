from __future__ import annotations

from tests._synthetic import synthetic_dataset
from water_routefinder.network import Harbour, Network, Point, Route
from water_routefinder.sample import sample
from water_routefinder.schema import COLUMNS
from water_routefinder.sources.base import BBox

BBOX = BBox(min_lon=-6.3, min_lat=53.2, max_lon=-6.0, max_lat=53.4)


def _grid():
    return synthetic_dataset(BBOX, "2024-01-01", "2024-01-02", step="1h")


def _network(path):
    h1 = Harbour(harbour_id="A", name="A", lat=path[0].lat, lon=path[0].lon)
    h2 = Harbour(harbour_id="B", name="B", lat=path[-1].lat, lon=path[-1].lon)
    route = Route(route_id="R1", origin="A", destination="B", path=tuple(path))
    return Network(harbours=(h1, h2), routes=(route,))


def test_sample_table_matches_contract_columns_and_dtypes():
    network = _network([Point(lat=53.25, lon=-6.25), Point(lat=53.35, lon=-6.05)])
    table, _ = sample(_grid(), network, densify_km=None)
    assert list(table.columns) == list(COLUMNS)


def test_two_vertex_route_without_densify_keeps_two_vertices():
    network = _network([Point(lat=53.25, lon=-6.25), Point(lat=53.35, lon=-6.05)])
    table, densified = sample(_grid(), network, densify_km=None)
    assert len(densified.routes[0].path) == 2
    assert sorted(table["vertex_index"].unique()) == [0, 1]


def test_densify_produces_contiguous_vertex_index():
    network = _network([Point(lat=53.25, lon=-6.25), Point(lat=53.35, lon=-6.05)])
    table, densified = sample(_grid(), network, densify_km=1.0)
    n = len(densified.routes[0].path)
    assert n > 2
    assert sorted(table["vertex_index"].unique()) == list(range(n))


def test_already_dense_route_is_unaffected_by_densify():
    close_points = [Point(lat=53.25, lon=-6.25), Point(lat=53.2501, lon=-6.2501)]
    network = _network(close_points)
    _, densified = sample(_grid(), network, densify_km=1.5)
    assert len(densified.routes[0].path) == 2


def test_row_count_is_vertices_times_timesteps():
    network = _network([Point(lat=53.25, lon=-6.25), Point(lat=53.35, lon=-6.05)])
    grid = _grid()
    table, densified = sample(grid, network, densify_km=None)
    assert len(table) == len(densified.routes[0].path) * grid.sizes["time"]
