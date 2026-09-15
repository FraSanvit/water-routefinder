"""Snakemake script for rule `diagnostics`: bundle -> {network}_diag_plot.png."""

from pathlib import Path

from water_routefinder.diagnostics import make_diag_plot

bundle_dir = Path(snakemake.input.parquet).parent.parent  # noqa: F821  (results/{network})
network = snakemake.wildcards.network  # noqa: F821
basemap = snakemake.config.get("diagnostics", {}).get("basemap", True)  # noqa: F821

make_diag_plot(  # noqa: F821
    bundle_dir, snakemake.output.png, title=f"{network} — conditions diagnostics", basemap=basemap
)
