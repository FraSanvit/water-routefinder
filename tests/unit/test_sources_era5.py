from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from water_routefinder.sources import era5


def _native_dataset(**vars_2d):
    time = pd.date_range("2024-01-01", periods=2, freq="1h")
    lat = np.array([53.3, 53.4])
    lon = np.array([-6.2, -6.1])
    data_vars = {
        name: (("time", "latitude", "longitude"), np.full((2, 2, 2), value, dtype="float64"))
        for name, value in vars_2d.items()
    }
    return xr.Dataset(data_vars, coords={"time": time, "latitude": lat, "longitude": lon})


def test_to_standard_wind():
    ds = _native_dataset(u10=0.0, v10=1.0)
    out = era5.to_standard_wind(ds)
    assert np.allclose(out["wind_speed"].values, 1.0)
    assert np.allclose(out["wind_from_direction"].values, 180.0)


def test_to_standard_waves_passthrough():
    ds = _native_dataset(swh=2.0, mwd=90.0, mwp=7.0)
    out = era5.to_standard_waves(ds)
    assert np.allclose(out["wave_height"].values, 2.0)
    assert np.allclose(out["wave_from_direction"].values, 90.0)
    assert np.allclose(out["wave_period"].values, 7.0)


def test_current_is_not_supported():
    from water_routefinder.sources.base import BBox

    with pytest.raises(NotImplementedError):
        era5.fetch(
            family="current",  # type: ignore[arg-type]
            variables=(),
            bbox=BBox(min_lon=-6.3, min_lat=53.2, max_lon=-6.0, max_lat=53.4),
            start="2024-01-01",
            end="2024-01-02",
        )
