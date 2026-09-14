"""ERA5 (Copernicus Climate Data Store) source provider — wind and wave only.

ERA5 is an atmospheric/wave reanalysis: it has no ocean-current product, so this provider only
implements ``family in {"wind", "wave"}`` (enforced upstream by
``water_routefinder.config.PROVIDER_CAPABILITIES``). Needs the ``era5`` extra (``cdsapi``) and a
``~/.cdsapirc`` or ``CDSAPI_URL``/``CDSAPI_KEY`` — see
https://cds.climate.copernicus.eu/how-to-api.
"""

from __future__ import annotations

import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr

from water_routefinder.sources.base import BBox

Family = Literal["wave", "wind"]

DEFAULT_DATASET_IDS: dict[Family, str] = {
    "wind": "reanalysis-era5-single-levels",
    "wave": "reanalysis-era5-single-levels",
}

#: ERA5 request variable name -> our working name (kept distinct from the v0.2 standard name
#: until the family-specific transform runs).
DEFAULT_VARIABLES: dict[Family, tuple[str, ...]] = {
    "wind": ("10m_u_component_of_wind", "10m_v_component_of_wind"),
    "wave": (
        "significant_height_of_combined_wind_waves_and_swell",
        "mean_wave_direction",
        "mean_wave_period",
    ),
}

_HOURS = [f"{h:02d}:00" for h in range(24)]


def fetch(
    *,
    family: Family,
    variables: tuple[str, ...],
    bbox: BBox,
    start: date | datetime,
    end: date | datetime,
    dataset_id: str | None = None,
) -> xr.Dataset:
    """Fetch one family's ERA5 subset and convert it to standard names/units."""
    if family not in DEFAULT_VARIABLES:
        raise NotImplementedError(f"ERA5 has no {family!r} product (wind/wave only)")

    import cdsapi

    dataset_id = dataset_id or DEFAULT_DATASET_IDS[family]
    client = cdsapi.Client()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "era5.nc"
        client.retrieve(
            dataset_id,
            {
                "product_type": "reanalysis",
                "format": "netcdf",
                "variable": list(variables),
                "date": f"{start}/{end}",
                "time": _HOURS,
                # CDS area order: [north, west, south, east].
                "area": [bbox.max_lat, bbox.min_lon, bbox.min_lat, bbox.max_lon],
            },
            str(target),
        )
        raw = xr.open_dataset(target).load()
    raw = raw.rename({k: v for k, v in {"latitude": "latitude", "longitude": "longitude"}.items() if k in raw.dims})
    return _TRANSFORMS[family](raw)


def to_standard_wind(ds: xr.Dataset) -> xr.Dataset:
    """``u10``/``v10`` -> ``wind_speed``/``wind_from_direction``."""
    u10, v10 = ds["u10"], ds["v10"]
    speed = np.hypot(u10, v10)
    direction = np.mod(np.degrees(np.arctan2(-u10, -v10)), 360.0)
    return _finish(ds, wind_speed=speed, wind_from_direction=direction)


def to_standard_waves(ds: xr.Dataset) -> xr.Dataset:
    """``swh``/``mwd``/``mwp`` -> ``wave_height``/``wave_from_direction``/``wave_period``."""
    return _finish(
        ds,
        wave_height=ds["swh"],
        wave_from_direction=ds["mwd"],
        wave_period=ds["mwp"],
    )


_TRANSFORMS = {"wind": to_standard_wind, "wave": to_standard_waves}

_UNITS = {
    "wind_speed": "m s-1",
    "wind_from_direction": "degree",
    "wave_height": "m",
    "wave_from_direction": "degree",
    "wave_period": "s",
}


def _finish(ds: xr.Dataset, **standard_vars: xr.DataArray) -> xr.Dataset:
    out = xr.Dataset(
        {name: da.astype("float32") for name, da in standard_vars.items()},
        coords={k: v for k, v in ds.coords.items() if k in ("time", "latitude", "longitude")},
    )
    for name in standard_vars:
        out[name].attrs["units"] = _UNITS[name]
    return out
