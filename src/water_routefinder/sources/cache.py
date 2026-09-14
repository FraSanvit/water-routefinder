"""A small netCDF response cache for the real (network-hitting) source providers.

Keyed by everything that determines the response: provider, dataset id, variables, bbox and time
span. Re-running ``harmonise``/``sample`` while iterating doesn't re-hit CMEMS/CDS for unchanged
downloads.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

import xarray as xr

from water_routefinder.sources.base import BBox


def cache_key(
    *,
    provider: str,
    dataset_id: str,
    variables: tuple[str, ...],
    bbox: BBox,
    start: date | datetime,
    end: date | datetime,
) -> str:
    payload = {
        "provider": provider,
        "dataset_id": dataset_id,
        "variables": sorted(variables),
        "bbox": bbox.to_dict(),
        "start": str(start),
        "end": str(end),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{provider}-{digest[:24]}"


def get(cache_dir: str | Path, key: str) -> xr.Dataset | None:
    """Return the cached dataset for ``key``, or ``None`` on a cache miss."""
    path = Path(cache_dir) / f"{key}.nc"
    if not path.is_file():
        return None
    return xr.open_dataset(path).load()


def put(cache_dir: str | Path, key: str, ds: xr.Dataset) -> Path:
    """Write ``ds`` to the cache under ``key`` and return the file path."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.nc"
    tmp = path.with_suffix(".nc.tmp")
    ds.to_netcdf(tmp)
    tmp.replace(path)
    return path
