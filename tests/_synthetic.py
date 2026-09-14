"""Test-only synthetic met-ocean field.

Not a "mock provider" -- the workflow supports only ``cmems``/``era5`` for now (see
docs/roadmap.md) and this module is not part of ``water_routefinder`` or reachable from
``config/config.yaml``. It exists purely so ``harmonise``/``sample``/``bundle`` logic can be unit
tested without live credentials or network access.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from water_routefinder.schema import VARIABLE_UNITS
from water_routefinder.sources.base import BBox

_N_LAT = 5
_N_LON = 5


def synthetic_dataset(
    bbox: BBox,
    start,
    end,
    *,
    step: str = "1h",
    seed: int = 0,
) -> xr.Dataset:
    """A small, deterministic dataset in the v0.2 standard names/units, covering ``bbox``."""
    time = pd.date_range(start=start, end=end, freq=step, inclusive="left")
    lat = np.linspace(bbox.min_lat, bbox.max_lat, _N_LAT)
    lon = np.linspace(bbox.min_lon, bbox.max_lon, _N_LON)

    rng = np.random.default_rng(seed)
    h = np.arange(time.size, dtype=float)[:, None, None]

    data_vars = {}
    for i, var in enumerate(VARIABLE_UNITS):
        base = 5.0 + i if "direction" not in var else 180.0
        wobble = 2.0 * np.sin(2 * np.pi * h / 24.0 + i)
        noise = rng.normal(0.0, 0.1, size=(time.size, lat.size, lon.size))
        values = base + wobble + noise
        if "direction" in var:
            values = np.mod(values, 360.0)
        else:
            values = np.clip(values, 0.0, None)
        data_vars[var] = (("time", "latitude", "longitude"), values.astype("float32"))

    ds = xr.Dataset(data_vars, coords={"time": time, "latitude": lat, "longitude": lon})
    for var, units in VARIABLE_UNITS.items():
        ds[var].attrs["units"] = units
    return ds
