from __future__ import annotations

import os

from tests._synthetic import synthetic_dataset
from water_routefinder.bundle import write_bundle
from water_routefinder.harmonise import harmonise
from water_routefinder.io import load_network
from water_routefinder.sample import sample
from water_routefinder.sources.base import bbox_from_network


def _bundle_args(demo_network_dir):
    network = load_network(demo_network_dir)
    bbox = bbox_from_network(network, margin_deg=0.1)
    ds = synthetic_dataset(bbox, "2024-01-01", "2024-01-02")
    grid = harmonise([ds], target_step="1h")
    table, densified = sample(grid, network, densify_km=1.5)
    return table, densified


def test_write_bundle_produces_all_four_files(demo_network_dir, tmp_path):
    table, network = _bundle_args(demo_network_dir)
    out_dir = tmp_path / "bundle"
    write_bundle(out_dir, table, network, title="t", target_step="1h", sources=["mock"])

    assert (out_dir / "network" / "harbours.csv").is_file()
    assert (out_dir / "network" / "routes.geojson").is_file()
    assert (out_dir / "environment" / "conditions.parquet").is_file()
    assert (out_dir / "environment" / "conditions.meta.yaml").is_file()


def test_write_bundle_is_deterministic_given_pinned_timestamp(demo_network_dir, tmp_path):
    table, network = _bundle_args(demo_network_dir)
    os.environ["SOURCE_DATE_EPOCH"] = "1704067200"  # 2024-01-01T00:00:00Z
    try:
        out_a, out_b = tmp_path / "a", tmp_path / "b"
        write_bundle(out_a, table, network, title="t", target_step="1h", sources=["mock"])
        write_bundle(out_b, table, network, title="t", target_step="1h", sources=["mock"])
    finally:
        del os.environ["SOURCE_DATE_EPOCH"]

    for rel in (
        "network/harbours.csv",
        "network/routes.geojson",
        "environment/conditions.parquet",
        "environment/conditions.meta.yaml",
    ):
        assert (out_a / rel).read_bytes() == (out_b / rel).read_bytes(), rel
