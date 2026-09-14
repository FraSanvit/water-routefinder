"""Copernicus Marine (CMEMS) source provider.

Wraps ``copernicusmarine.open_dataset`` (lazy xarray) and converts each product family's native
variables to the v0.2 contract's standard names/units/conventions. Needs the ``cmems`` extra
(``copernicusmarine``) and credentials -- see ``.env.example`` / ``config/README.md`` for the
options (``copernicusmarine login``, a local ``.env``, or real environment variables). If our own
``CMEMS_USERNAME``/``CMEMS_PASSWORD`` aren't set, we pass ``None`` through and
``copernicusmarine`` falls back to its own resolution (its ``COPERNICUSMARINE_SERVICE_USERNAME``/
``_PASSWORD``, then a ``copernicusmarine login``-created credentials file, then ``.netrc``).

Default dataset ids (``workflow/internal/settings.yaml`` normally supplies/overrides these) were
verified against the live catalogue via ``copernicusmarine.describe()`` (no credentials needed --
it's a public catalogue query, unlike ``open_dataset``/``subset``), each dataset id's variables
checked against what this module requests: current -> `uo`/`vo`, wave -> `VHM0`/`VMDR`/`VTM10`,
wind -> `eastward_wind`/`northward_wind`. Re-run that check before relying on them again after a
long gap — Copernicus Marine periodically reprocesses and renames products, e.g.:

    import copernicusmarine
    cat = copernicusmarine.describe(dataset_id="cmems_mod_glo_phy_anfc_0.083deg_PT1H-m")
    # -> cat.products[0].datasets[0].versions[0].parts[0].services[0].variables

The same query also showed the current dataset is 3-D (it carries temperature/salinity at
depth too) but ``uo``/``vo`` only have one depth level -- see ``_CURRENT_SURFACE_DEPTH_M`` below.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Literal

import numpy as np
import xarray as xr

from water_routefinder.sources.base import BBox

Family = Literal["current", "wave", "wind"]

#: Verified defaults (see the module docstring) — override via config.sources.<family>.dataset_id.
DEFAULT_DATASET_IDS: dict[Family, str] = {
    "current": "cmems_mod_glo_phy_anfc_0.083deg_PT1H-m",
    "wave": "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i",
    "wind": "cmems_obs-wind_glo_phy_my_l4_0.125deg_PT1H",
}

DEFAULT_VARIABLES: dict[Family, tuple[str, ...]] = {
    "current": ("uo", "vo"),
    "wave": ("VHM0", "VMDR", "VTM10"),
    "wind": ("eastward_wind", "northward_wind"),
}

#: ``cmems_mod_glo_phy_anfc_0.083deg_PT1H-m`` is a 3-D physics product (it also carries
#: temperature/salinity at depth); ``uo``/``vo`` on it only have this one, near-surface depth
#: level (confirmed via ``copernicusmarine.describe()``: ``coordinates[depth].values ==
#: [0.49402499198913574]``). Pinned explicitly below rather than left unset, so a future
#: reprocessing that adds levels can't silently turn "surface current" into a multi-depth fetch.
#: wave/wind are inherently surface scalar fields with no depth axis -- nothing to pin there.
_CURRENT_SURFACE_DEPTH_M = 0.49402499198913574

_DIM_RENAME = {"lat": "latitude", "lon": "longitude"}


def fetch(
    *,
    family: Family,
    variables: tuple[str, ...],
    bbox: BBox,
    start: date | datetime,
    end: date | datetime,
    dataset_id: str | None = None,
) -> xr.Dataset:
    """Fetch one family's CMEMS subset and convert it to standard names/units."""
    import copernicusmarine

    dataset_id = dataset_id or DEFAULT_DATASET_IDS[family]
    depth_kwargs = {}
    if family == "current":
        depth_kwargs = {
            "minimum_depth": _CURRENT_SURFACE_DEPTH_M,
            "maximum_depth": _CURRENT_SURFACE_DEPTH_M,
        }
    raw = copernicusmarine.open_dataset(
        dataset_id=dataset_id,
        variables=list(variables),
        minimum_longitude=bbox.min_lon,
        maximum_longitude=bbox.max_lon,
        minimum_latitude=bbox.min_lat,
        maximum_latitude=bbox.max_lat,
        start_datetime=str(start),
        end_datetime=str(end),
        username=os.environ.get("CMEMS_USERNAME"),
        password=os.environ.get("CMEMS_PASSWORD"),
        **depth_kwargs,
    )
    raw = raw.rename({k: v for k, v in _DIM_RENAME.items() if k in raw.dims})
    if "depth" in raw.dims:
        # Defensive: even pinned to one value, `depth` may still come back as a length-1
        # dimension rather than being auto-squeezed.
        raw = raw.squeeze("depth", drop=True)
    return _TRANSFORMS[family](raw)


def to_standard_currents(ds: xr.Dataset) -> xr.Dataset:
    """``uo``, ``vo`` (m/s, eastward/northward) -> ``current_speed``/``current_to_direction``."""
    uo, vo = ds["uo"], ds["vo"]
    speed = np.hypot(uo, vo)
    # Oceanographic "to" convention: compass bearing the current flows towards.
    direction = np.mod(np.degrees(np.arctan2(uo, vo)), 360.0)
    return _finish(ds, current_speed=speed, current_to_direction=direction)


def to_standard_waves(ds: xr.Dataset) -> xr.Dataset:
    """``VHM0``/``VMDR``/``VTM10`` -> ``wave_height``/``wave_from_direction``/``wave_period``."""
    return _finish(
        ds,
        wave_height=ds["VHM0"],
        wave_from_direction=ds["VMDR"],
        wave_period=ds["VTM10"],
    )


def to_standard_wind(ds: xr.Dataset) -> xr.Dataset:
    """``eastward_wind``/``northward_wind`` -> ``wind_speed``/``wind_from_direction``."""
    e, n = ds["eastward_wind"], ds["northward_wind"]
    speed = np.hypot(e, n)
    # Meteorological "from" convention: compass bearing the wind blows from.
    direction = np.mod(np.degrees(np.arctan2(-e, -n)), 360.0)
    return _finish(ds, wind_speed=speed, wind_from_direction=direction)


_TRANSFORMS = {
    "current": to_standard_currents,
    "wave": to_standard_waves,
    "wind": to_standard_wind,
}

_UNITS = {
    "current_speed": "m s-1",
    "current_to_direction": "degree",
    "wave_height": "m",
    "wave_from_direction": "degree",
    "wave_period": "s",
    "wind_speed": "m s-1",
    "wind_from_direction": "degree",
}


def _finish(ds: xr.Dataset, **standard_vars: xr.DataArray) -> xr.Dataset:
    out = xr.Dataset(
        {name: da.astype("float32") for name, da in standard_vars.items()},
        coords={k: v for k, v in ds.coords.items() if k in ("time", "latitude", "longitude")},
    )
    for name in standard_vars:
        out[name].attrs["units"] = _UNITS[name]
    return out
