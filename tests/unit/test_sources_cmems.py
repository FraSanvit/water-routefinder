from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import xarray as xr

from water_routefinder.sources import cmems
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


def test_to_standard_currents_speed_and_direction():
    # uo (eastward) = 1, vo (northward) = 0 -> flowing due east -> "to" bearing 90 degrees.
    ds = _native_dataset(uo=1.0, vo=0.0)
    out = cmems.to_standard_currents(ds)
    assert np.allclose(out["current_speed"].values, 1.0)
    assert np.allclose(out["current_to_direction"].values, 90.0)
    assert out["current_speed"].attrs["units"] == "m s-1"
    assert out["current_to_direction"].attrs["units"] == "degree"


def test_to_standard_wind_from_direction():
    # Wind vector pointing due north (e=0, n=1) blows FROM the south -> from-bearing 180.
    ds = _native_dataset(eastward_wind=0.0, northward_wind=1.0)
    out = cmems.to_standard_wind(ds)
    assert np.allclose(out["wind_speed"].values, 1.0)
    assert np.allclose(out["wind_from_direction"].values, 180.0)


def test_to_standard_waves_passthrough():
    ds = _native_dataset(VHM0=1.5, VMDR=200.0, VTM10=6.0)
    out = cmems.to_standard_waves(ds)
    assert np.allclose(out["wave_height"].values, 1.5)
    assert np.allclose(out["wave_from_direction"].values, 200.0)
    assert np.allclose(out["wave_period"].values, 6.0)


def test_default_dataset_ids_cover_every_family():
    assert set(cmems.DEFAULT_DATASET_IDS) == {"current", "wave", "wind"}


def _stub_open_dataset(monkeypatch, result_ds, captured_kwargs: dict):
    def fake_open_dataset(**kwargs):
        captured_kwargs.update(kwargs)
        return result_ds

    monkeypatch.setitem(
        sys.modules, "copernicusmarine", SimpleNamespace(open_dataset=fake_open_dataset)
    )


def test_fetch_pins_the_surface_depth_for_current(monkeypatch):
    # cmems_mod_glo_phy_anfc_0.083deg_PT1H-m is a 3-D product; uo/vo only have one depth level
    # (confirmed via copernicusmarine.describe()) -- fetch() must pin it explicitly.
    captured: dict = {}
    _stub_open_dataset(monkeypatch, _native_dataset(uo=1.0, vo=0.0), captured)

    cmems.fetch(
        family="current", variables=("uo", "vo"), bbox=BBOX, start="2024-01-01", end="2024-01-02"
    )

    assert captured["minimum_depth"] == cmems._CURRENT_SURFACE_DEPTH_M
    assert captured["maximum_depth"] == cmems._CURRENT_SURFACE_DEPTH_M


def test_fetch_does_not_pin_depth_for_wave_or_wind(monkeypatch):
    captured: dict = {}
    _stub_open_dataset(monkeypatch, _native_dataset(VHM0=1.0, VMDR=1.0, VTM10=1.0), captured)

    cmems.fetch(
        family="wave",
        variables=("VHM0", "VMDR", "VTM10"),
        bbox=BBOX,
        start="2024-01-01",
        end="2024-01-02",
    )

    assert "minimum_depth" not in captured
    assert "maximum_depth" not in captured


def test_fetch_squeezes_a_stray_length_one_depth_dimension(monkeypatch):
    # Defensive case: even pinned to one value, the API could still hand back a length-1 `depth`
    # dimension rather than dropping it.
    time = pd.date_range("2024-01-01", periods=2, freq="1h")
    lat, lon = np.array([53.3, 53.4]), np.array([-6.2, -6.1])
    with_depth = xr.Dataset(
        {
            "uo": (("depth", "time", "latitude", "longitude"), np.ones((1, 2, 2, 2))),
            "vo": (("depth", "time", "latitude", "longitude"), np.zeros((1, 2, 2, 2))),
        },
        coords={
            "depth": [cmems._CURRENT_SURFACE_DEPTH_M],
            "time": time,
            "latitude": lat,
            "longitude": lon,
        },
    )
    _stub_open_dataset(monkeypatch, with_depth, {})

    out = cmems.fetch(
        family="current", variables=("uo", "vo"), bbox=BBOX, start="2024-01-01", end="2024-01-02"
    )

    assert "depth" not in out.dims
    assert set(out["current_speed"].dims) == {"time", "latitude", "longitude"}
