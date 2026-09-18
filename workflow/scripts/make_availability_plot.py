"""Snakemake script for rule `availability`: grid + network -> {network}_availability_map.png."""

from pathlib import Path

from water_routefinder.diagnostics import make_availability_plot

bundle_dir = Path(snakemake.input.routes).parent.parent  # noqa: F821  (results/{network})
network = snakemake.wildcards.network  # noqa: F821
basemap = snakemake.config.get("diagnostics", {}).get("basemap", True)  # noqa: F821

make_availability_plot(  # noqa: F821
    bundle_dir,
    snakemake.input.grid,  # noqa: F821
    snakemake.output.png,  # noqa: F821
    title=f"{network} — data availability",
    basemap=basemap,
)
