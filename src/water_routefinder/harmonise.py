"""Put one or more source datasets onto a single common grid/cadence.

Network-agnostic and independently testable — the ``atlite``-cutout equivalent the plan describes.
Every input must already be in the v0.2 standard variable names/units (each source provider's own
job, see ``sources/``); this stage only regrids and re-aligns in time, it never renames or converts
units.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import xarray as xr

from water_routefinder.schema import VARIABLE_UNITS


def harmonise(datasets: list[xr.Dataset], *, target_step: str = "1h") -> xr.Dataset:
    """Regrid + time-resample ``datasets`` onto one common grid, merged into one Dataset.

    - Common grid: the **intersection** of every input's lat/lon extent, at the *finest* input
      resolution. Deliberately not the union -- ``xarray.Dataset.interp`` returns NaN for any
      point outside a source's own coordinate range (no extrapolation), so asking a coarser or
      narrower-coverage source for points beyond what it actually returned would poison the
      common grid with NaN that has nothing to do with real data gaps (land masking etc.) and
      everything to do with different providers/products returning different native extents for
      the same bbox request. NaN from genuine source gaps still passes through untouched, per the
      contract -- ``water-path`` only raises if it actually needs a NaN cell.
    - Common time axis: spans the union of every input's time coverage, stepped at ``target_step``.
    - Bilinear (``xarray.Dataset.interp``) in space; linear in time.
    """
    if not datasets:
        raise ValueError("harmonise: at least one dataset is required")
    for ds in datasets:
        _assert_standard(ds)

    lat_res = min(_resolution(ds, "latitude") for ds in datasets)
    lon_res = min(_resolution(ds, "longitude") for ds in datasets)
    min_lat = max(float(ds["latitude"].min()) for ds in datasets)
    max_lat = min(float(ds["latitude"].max()) for ds in datasets)
    min_lon = max(float(ds["longitude"].min()) for ds in datasets)
    max_lon = min(float(ds["longitude"].max()) for ds in datasets)
    if min_lat >= max_lat or min_lon >= max_lon:
        raise ValueError(
            "harmonise: the input datasets' native grids don't overlap spatially at all -- "
            f"intersection is lat [{min_lat}, {max_lat}], lon [{min_lon}, {max_lon}]"
        )
    # np.arange's endpoint padding (`+ res / 2`, so a point exactly at the bound is kept) can
    # overshoot past the intersection when the extent isn't an exact multiple of the resolution --
    # clip back to the bound (with a tiny epsilon for float slop) so we never re-introduce the
    # out-of-range-extrapolates-to-NaN problem this intersection logic exists to avoid.
    lat = np.arange(min_lat, max_lat + lat_res / 2, lat_res)
    lat = lat[lat <= max_lat + 1e-9]
    lon = np.arange(min_lon, max_lon + lon_res / 2, lon_res)
    lon = lon[lon <= max_lon + 1e-9]

    min_time = min(pd.Timestamp(ds["time"].min().values) for ds in datasets)
    max_time = max(pd.Timestamp(ds["time"].max().values) for ds in datasets)
    common_time = pd.date_range(start=min_time, end=max_time, freq=target_step)
    if common_time.empty:
        raise ValueError(f"harmonise: empty common time axis ({min_time} .. {max_time})")

    regridded = []
    for ds in datasets:
        r = ds.interp(latitude=lat, longitude=lon, method="linear")
        r = r.interp(time=common_time, method="linear")
        regridded.append(r)

    merged = xr.merge(regridded, compat="override", combine_attrs="drop_conflicts")
    for var in merged.data_vars:
        if var in VARIABLE_UNITS:
            merged[var].attrs["units"] = VARIABLE_UNITS[var]
    merged.attrs["water_routefinder_target_step"] = target_step
    return merged


def _resolution(ds: xr.Dataset, dim: str) -> float:
    values = np.asarray(ds[dim].values, dtype="float64")
    if values.size < 2:
        raise ValueError(
            f"harmonise: dataset has < 2 points along {dim!r}, cannot infer resolution"
        )
    return float(np.median(np.abs(np.diff(values))))


def _assert_standard(ds: xr.Dataset) -> None:
    missing_dims = [d for d in ("time", "latitude", "longitude") if d not in ds.coords]
    if missing_dims:
        raise ValueError(f"harmonise: dataset is missing coord(s): {', '.join(missing_dims)}")
    for var in ds.data_vars:
        expected = VARIABLE_UNITS.get(str(var))
        if expected is None:
            continue
        got = ds[var].attrs.get("units")
        if got != expected:
            warnings.warn(
                f"harmonise: {var} has units {got!r}, expected {expected!r}", stacklevel=3
            )
