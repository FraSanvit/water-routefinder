"""Snakemake script for rule `bundle`: table + densified network -> the water-path v0.2 bundle."""

from pathlib import Path

import pandas as pd

from water_routefinder.bundle import write_bundle
from water_routefinder.io import load_network

network_dir = Path(snakemake.input.routes).parent  # noqa: F821  (resources/automatic/{network}/densified)
network = load_network(network_dir)
table = pd.read_parquet(snakemake.input.table)  # noqa: F821

out_dir = Path(snakemake.output.parquet).parent.parent  # noqa: F821  (results/{network})
write_bundle(
    out_dir,
    table,
    network,
    title=snakemake.params.title,  # noqa: F821
    target_step=snakemake.params.target_step,  # noqa: F821
    sources=list(snakemake.params.sources),  # noqa: F821
)
