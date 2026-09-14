"""Snakemake script for rule `sample`: grid + network -> table + densified network files."""

from pathlib import Path

import xarray as xr

from water_routefinder.io import load_network, write_harbours_csv, write_routes_geojson
from water_routefinder.sample import sample

network_dir = Path(snakemake.input.routes).parent  # noqa: F821
network = load_network(network_dir)
grid = xr.open_dataset(snakemake.input.grid).load()  # noqa: F821

table, densified = sample(grid, network, densify_km=snakemake.params.densify_km)  # noqa: F821

Path(snakemake.output.table).parent.mkdir(parents=True, exist_ok=True)  # noqa: F821
table.to_parquet(snakemake.output.table, index=False)  # noqa: F821

out_harbours = Path(snakemake.output.harbours)  # noqa: F821
out_harbours.parent.mkdir(parents=True, exist_ok=True)
write_harbours_csv(densified, out_harbours)
write_routes_geojson(densified, snakemake.output.routes)  # noqa: F821
