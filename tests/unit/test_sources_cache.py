from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from water_routefinder.sources import cache
from water_routefinder.sources.base import BBox

BBOX = BBox(min_lon=-6.3, min_lat=53.2, max_lon=-6.0, max_lat=53.4)
_KEY_KWARGS = dict(
    provider="cmems",
    dataset_id="ds-1",
    variables=("uo", "vo"),
    bbox=BBOX,
    start="2024-01-01",
    end="2024-01-02",
)


def _dataset() -> xr.Dataset:
    time = pd.date_range("2024-01-01", periods=2, freq="1h")
    return xr.Dataset(
        {"current_speed": (("time", "latitude", "longitude"), np.ones((2, 2, 2), dtype="float32"))},
        coords={"time": time, "latitude": [53.2, 53.4], "longitude": [-6.3, -6.0]},
    )


def test_cache_key_is_deterministic():
    assert cache.cache_key(**_KEY_KWARGS) == cache.cache_key(**_KEY_KWARGS)


def test_cache_key_ignores_variable_order():
    a = cache.cache_key(**{**_KEY_KWARGS, "variables": ("uo", "vo")})
    b = cache.cache_key(**{**_KEY_KWARGS, "variables": ("vo", "uo")})
    assert a == b


def test_cache_key_starts_with_the_provider_name():
    assert cache.cache_key(**_KEY_KWARGS).startswith("cmems-")


def test_cache_key_differs_when_any_input_differs():
    base = cache.cache_key(**_KEY_KWARGS)
    variants = [
        {**_KEY_KWARGS, "provider": "era5"},
        {**_KEY_KWARGS, "dataset_id": "ds-2"},
        {**_KEY_KWARGS, "variables": ("uo",)},
        {**_KEY_KWARGS, "bbox": BBox(min_lon=-7.0, min_lat=53.0, max_lon=-6.0, max_lat=54.0)},
        {**_KEY_KWARGS, "start": "2024-02-01"},
        {**_KEY_KWARGS, "end": "2024-02-02"},
    ]
    keys = {cache.cache_key(**v) for v in variants}
    assert base not in keys
    assert len(keys) == len(variants)  # every variant is distinct from every other, too


def test_get_returns_none_on_a_cache_miss(tmp_path):
    assert cache.get(tmp_path, "does-not-exist") is None


def test_put_then_get_round_trips(tmp_path):
    ds = _dataset()
    key = cache.cache_key(**_KEY_KWARGS)

    written = cache.put(tmp_path, key, ds)

    assert written == tmp_path / f"{key}.nc"
    assert written.is_file()
    restored = cache.get(tmp_path, key)
    assert restored is not None
    xr.testing.assert_allclose(restored["current_speed"], ds["current_speed"])


def test_put_creates_a_missing_cache_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    assert not nested.exists()

    cache.put(nested, "k", _dataset())

    assert (nested / "k.nc").is_file()


def test_put_does_not_leave_a_temp_file_behind(tmp_path):
    cache.put(tmp_path, "k", _dataset())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["k.nc"]
