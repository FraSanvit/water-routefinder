"""Snakemake script for rule `harmonise`: three raw datasets -> one common grid."""

import xarray as xr

from water_routefinder.harmonise import harmonise

datasets = [
    xr.open_dataset(path).load()
    for path in (snakemake.input.current, snakemake.input.wave, snakemake.input.wind)  # noqa: F821
]
grid = harmonise(datasets, target_step=snakemake.params.target_step)  # noqa: F821
grid.to_netcdf(snakemake.output.grid)  # noqa: F821
