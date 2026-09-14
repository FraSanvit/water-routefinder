"""Snakemake script for rule `diagnostics`: bundle -> {network}_diag_plot.png."""

from pathlib import Path

from water_routefinder.diagnostics import make_diag_plot

bundle_dir = Path(snakemake.input.parquet).parent.parent  # noqa: F821  (results/{network})
network = snakemake.wildcards.network  # noqa: F821

make_diag_plot(bundle_dir, snakemake.output.png, title=f"{network} — conditions diagnostics")  # noqa: F821
