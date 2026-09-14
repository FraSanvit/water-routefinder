from __future__ import annotations

from water_routefinder.io import load_network, write_harbours_csv, write_routes_geojson


def test_load_demo_network(demo_network_dir):
    network = load_network(demo_network_dir)
    assert len(network.harbours) == 3
    assert len(network.routes) == 2
    assert network.harbour("DCC").name == "Dublin City Quay"
    route = network.route("DCC-DUN")
    assert route.origin == "DCC"
    assert route.destination == "DUN"
    assert len(route.path) >= 2


def test_write_then_load_round_trips(demo_network_dir, tmp_path):
    network = load_network(demo_network_dir)
    write_harbours_csv(network, tmp_path / "harbours.csv")
    write_routes_geojson(network, tmp_path / "routes.geojson")

    reloaded = load_network(tmp_path)
    assert reloaded.harbours == network.harbours
    assert reloaded.routes == network.routes
