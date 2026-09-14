"""Snakemake script for rule `download`: dispatch to the configured provider for this family."""

import json
from pathlib import Path

from dotenv import load_dotenv

from water_routefinder.sources import cache as source_cache
from water_routefinder.sources import cmems, era5
from water_routefinder.sources.base import BBox

# Belt-and-braces: the Snakefile already loads .env for the whole run, but this script can also
# be invoked directly (e.g. from a test) -- see .env.example.
load_dotenv()

_MODULES = {"cmems": cmems, "era5": era5}

# `snakemake` is injected into this script's namespace by the `script:` directive.
family = snakemake.wildcards.family  # noqa: F821
spec = dict(snakemake.params.spec)
provider = spec["provider"]
variables = tuple(spec["variables"])
dataset_id = spec.get("dataset_id")

bbox = BBox.from_dict(json.loads(Path(snakemake.input.bbox).read_text()))
start, end = snakemake.params.time["start"], snakemake.params.time["end"]

module = _MODULES[provider]
resolved_dataset_id = dataset_id or module.DEFAULT_DATASET_IDS[family]
key = source_cache.cache_key(
    provider=provider,
    dataset_id=resolved_dataset_id,
    variables=variables,
    bbox=bbox,
    start=start,
    end=end,
)
ds = source_cache.get(snakemake.params.cache_dir, key)
if ds is None:
    ds = module.fetch(
        family=family,
        variables=variables,
        bbox=bbox,
        start=start,
        end=end,
        dataset_id=dataset_id,
    )
    source_cache.put(snakemake.params.cache_dir, key, ds)

Path(snakemake.output.raw).parent.mkdir(parents=True, exist_ok=True)
ds.to_netcdf(snakemake.output.raw)
