"""Snakemake script for rule `make_bbox`: network -> bbox.json."""

import json
from pathlib import Path

from water_routefinder.io import load_network
from water_routefinder.sources.base import bbox_from_network

# `snakemake` is injected into this script's namespace by the `script:` directive.
network_dir = Path(snakemake.input.routes).parent  # noqa: F821
network = load_network(network_dir)

margin_deg = snakemake.config.get("bbox", {}).get("margin_deg", 0.1)  # noqa: F821
bbox = bbox_from_network(network, margin_deg=margin_deg)

Path(snakemake.output.bbox).write_text(json.dumps(bbox.to_dict(), indent=2) + "\n")  # noqa: F821
