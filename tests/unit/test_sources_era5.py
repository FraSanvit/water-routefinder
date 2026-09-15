from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from water_routefinder.sources import era5
from water_routefinder.sources.base import BBox

BBOX = BBox(min_lon=-6.3, min_lat=53.2, max_lon=-6.0, max_lat=53.4)


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
    with pytest.raises(NotImplementedError):
        era5.fetch(
            family="current",  # type: ignore[arg-type]
            variables=(),
            bbox=BBOX,
            start="2024-01-01",
            end="2024-01-02",
        )


class _FakeCdsClient:
    """Stands in for ``cdsapi.Client``: records the request, and -- since real ``retrieve()``
    downloads a netCDF file to ``target`` -- writes ``result_ds`` there instead of hitting CDS."""

    def __init__(self, result_ds: xr.Dataset, captured: dict):
        self._result_ds = result_ds
        self._captured = captured

    def retrieve(self, name, request, target):
        self._captured["dataset_id"] = name
        self._captured["request"] = request
        self._captured["target"] = target
        self._result_ds.to_netcdf(target)


def _stub_cdsapi(monkeypatch, result_ds: xr.Dataset, captured: dict):
    fake_module = SimpleNamespace(Client=lambda *a, **kw: _FakeCdsClient(result_ds, captured))
    monkeypatch.setitem(sys.modules, "cdsapi", fake_module)


def test_fetch_wind_builds_the_right_request_and_transforms_the_result(monkeypatch):
    captured: dict = {}
    _stub_cdsapi(monkeypatch, _native_dataset(u10=1.0, v10=0.0), captured)

    out = era5.fetch(
        family="wind",
        variables=era5.DEFAULT_VARIABLES["wind"],
        bbox=BBOX,
        start="2024-01-01",
        end="2024-01-02",
    )

    assert captured["dataset_id"] == "reanalysis-era5-single-levels"
    req = captured["request"]
    assert req["variable"] == list(era5.DEFAULT_VARIABLES["wind"])
    assert req["date"] == "2024-01-01/2024-01-02"
    assert len(req["time"]) == 24 and req["time"][0] == "00:00" and req["time"][-1] == "23:00"
    # CDS area order is [north, west, south, east].
    assert req["area"] == [BBOX.max_lat, BBOX.min_lon, BBOX.min_lat, BBOX.max_lon]
    assert set(out.data_vars) == {"wind_speed", "wind_from_direction"}


def test_fetch_wave_builds_the_right_request_and_transforms_the_result(monkeypatch):
    captured: dict = {}
    _stub_cdsapi(monkeypatch, _native_dataset(swh=1.0, mwd=1.0, mwp=1.0), captured)

    out = era5.fetch(
        family="wave",
        variables=era5.DEFAULT_VARIABLES["wave"],
        bbox=BBOX,
        start="2024-01-01",
        end="2024-01-02",
    )

    assert captured["request"]["variable"] == list(era5.DEFAULT_VARIABLES["wave"])
    assert set(out.data_vars) == {"wave_height", "wave_from_direction", "wave_period"}


def test_fetch_uses_the_given_dataset_id_over_the_default(monkeypatch):
    captured: dict = {}
    _stub_cdsapi(monkeypatch, _native_dataset(u10=0.0, v10=0.0), captured)

    era5.fetch(
        family="wind",
        variables=era5.DEFAULT_VARIABLES["wind"],
        bbox=BBOX,
        start="2024-01-01",
        end="2024-01-02",
        dataset_id="custom-reanalysis-id",
    )

    assert captured["dataset_id"] == "custom-reanalysis-id"
