from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from tests._synthetic import synthetic_dataset
from water_routefinder.harmonise import harmonise
from water_routefinder.sources.base import BBox

BBOX = BBox(min_lon=-6.3, min_lat=53.2, max_lon=-6.0, max_lat=53.4)


def _ds(**kw):
    return synthetic_dataset(BBOX, "2024-01-01", "2024-01-02", **kw)


def test_single_source_passthrough_keeps_all_variables():
    grid = harmonise([_ds()], target_step="1h")
    assert set(grid.data_vars) == {
        "wind_speed",
        "wind_from_direction",
        "current_speed",
        "current_to_direction",
        "wave_height",
        "wave_from_direction",
        "wave_period",
    }


def test_time_resample_to_target_step():
    grid = harmonise([_ds(step="1h")], target_step="3h")
    diffs = np.diff(grid["time"].values).astype("timedelta64[h]")
    assert (diffs == np.timedelta64(3, "h")).all()


def test_merges_onto_finest_grid_resolution():
    coarse = xr.Dataset(
        {"wind_speed": (("time", "latitude", "longitude"), np.zeros((2, 2, 2), dtype="float32"))},
        coords={
            "time": pd.date_range("2024-01-01", periods=2, freq="1h"),
            "latitude": [53.2, 53.4],
            "longitude": [-6.3, -6.0],
        },
    )
    coarse["wind_speed"].attrs["units"] = "m s-1"
    fine = xr.Dataset(
        {
            "current_speed": (
                ("time", "latitude", "longitude"),
                np.zeros((2, 5, 5), dtype="float32"),
            )
        },
        coords={
            "time": pd.date_range("2024-01-01", periods=2, freq="1h"),
            "latitude": np.linspace(53.2, 53.4, 5),
            "longitude": np.linspace(-6.3, -6.0, 5),
        },
    )
    fine["current_speed"].attrs["units"] = "m s-1"

    grid = harmonise([coarse, fine], target_step="1h")
    assert grid.sizes["latitude"] >= 5


def test_wrong_units_warns():
    bad = _ds()
    bad["wind_speed"].attrs["units"] = "knots"
    with pytest.warns(UserWarning, match="wind_speed"):
        harmonise([bad], target_step="1h")


def test_empty_dataset_list_raises():
    with pytest.raises(ValueError):
        harmonise([], target_step="1h")


def test_narrower_source_is_not_extrapolated_to_nan():
    # Regression test for a real bug caught against live CMEMS data (sherkin-island): a source
    # with a native grid narrower than another source's caused the (then union-based) common grid
    # to ask that narrower source for points outside its own coverage -- xarray.interp returns
    # NaN for those (no extrapolation), silently poisoning an otherwise-complete variable. The
    # common grid must stay within the *intersection* of every source's native extent.
    wide = xr.Dataset(
        {"current_speed": (("time", "latitude", "longitude"), np.ones((2, 3, 3), dtype="float32"))},
        coords={
            "time": pd.date_range("2024-01-01", periods=2, freq="1h"),
            "latitude": [51.42, 51.50, 51.58],
            "longitude": [-9.58, -9.50, -9.42],
        },
    )
    wide["current_speed"].attrs["units"] = "m s-1"
    narrow = xr.Dataset(
        {
            "wind_speed": (
                ("time", "latitude", "longitude"),
                np.full((2, 2, 2), 5.0, dtype="float32"),
            )
        },
        coords={
            "time": pd.date_range("2024-01-01", periods=2, freq="1h"),
            "latitude": [51.44, 51.56],
            "longitude": [-9.56, -9.44],
        },
    )
    narrow["wind_speed"].attrs["units"] = "m s-1"

    grid = harmonise([wide, narrow], target_step="1h")

    assert not np.isnan(grid["wind_speed"].values).any()
    assert float(grid["latitude"].min()) >= 51.44
    assert float(grid["latitude"].max()) <= 51.56


def test_no_spatial_overlap_raises_a_clear_error():
    a = xr.Dataset(
        {"wind_speed": (("time", "latitude", "longitude"), np.ones((1, 2, 2), dtype="float32"))},
        coords={
            "time": pd.date_range("2024-01-01", periods=1, freq="1h"),
            "latitude": [0.0, 1.0],
            "longitude": [0.0, 1.0],
        },
    )
    a["wind_speed"].attrs["units"] = "m s-1"
    b = xr.Dataset(
        {"wave_height": (("time", "latitude", "longitude"), np.ones((1, 2, 2), dtype="float32"))},
        coords={
            "time": pd.date_range("2024-01-01", periods=1, freq="1h"),
            "latitude": [50.0, 51.0],
            "longitude": [50.0, 51.0],
        },
    )
    b["wave_height"].attrs["units"] = "m"

    with pytest.raises(ValueError, match="don't overlap"):
        harmonise([a, b], target_step="1h")
