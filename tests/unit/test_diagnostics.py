from __future__ import annotations

import warnings

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from water_routefinder.diagnostics import _BASEMAP_PATH, _plot_conditions, _plot_map, make_diag_plot
from water_routefinder.io import load_network
from water_routefinder.schema import empty_frame


def test_make_diag_plot_writes_a_non_empty_png(expected_bundle_dir, tmp_path):
    out_png = tmp_path / "dublin-bay_diag_plot.png"
    # basemap defaults True: this is now a fully local, offline, network-free file read (see
    # docs/roadmap.md / the diagnostics.py module docstring for why it's not a live tile fetch).
    result = make_diag_plot(expected_bundle_dir, out_png)
    assert result == out_png
    assert out_png.is_file()
    assert out_png.stat().st_size > 1000
    assert out_png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_basemap_file_exists_and_covers_every_example_network():
    assert _BASEMAP_PATH.is_file()
    import geopandas as gpd

    land = gpd.read_parquet(_BASEMAP_PATH)
    min_lon, min_lat, max_lon, max_lat = land.total_bounds
    # Every resources/user/*/ example network built so far sits inside this extent (Ireland to
    # Brittany); a generous margin so new examples don't quietly fall outside it.
    assert min_lon <= -12 and max_lon >= 2
    assert min_lat <= 48 and max_lat >= 53


def test_basemap_failure_is_a_warning_not_a_crash(expected_bundle_dir, monkeypatch):
    # A missing/corrupt basemap file (or a missing geopandas install) must never take the whole
    # diagnostic plot down with it -- the basemap is a nice-to-have overlay.
    import water_routefinder.diagnostics as diag

    monkeypatch.setattr(diag, "_BASEMAP_PATH", diag._BASEMAP_PATH.parent / "does-not-exist.parquet")

    network = load_network(expected_bundle_dir / "network")
    fig, ax = plt.subplots()
    with pytest.warns(UserWarning, match="basemap unavailable"):
        _plot_map(ax, network, basemap=True)
    plt.close(fig)


def test_basemap_false_skips_the_land_overlay(expected_bundle_dir, monkeypatch):
    import water_routefinder.diagnostics as diag

    def _boom(_ax):
        raise AssertionError("_add_basemap should not be called when basemap=False")

    monkeypatch.setattr(diag, "_add_basemap", _boom)

    network = load_network(expected_bundle_dir / "network")
    fig, ax = plt.subplots()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning here would mean we tried anyway
        _plot_map(ax, network, basemap=False)
    plt.close(fig)


def test_basemap_view_stays_framed_to_the_network(expected_bundle_dir):
    # The basemap layer spans all of Europe; the view must stay framed to the network's own
    # extent, not zoom out to fit the whole land layer.
    network = load_network(expected_bundle_dir / "network")
    fig, ax = plt.subplots()
    _plot_map(ax, network, basemap=True)
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    plt.close(fig)

    lons = [p.lon for r in network.routes for p in r.path] + [h.lon for h in network.harbours]
    lats = [p.lat for r in network.routes for p in r.path] + [h.lat for h in network.harbours]
    assert xlim[0] <= min(lons) and xlim[1] >= max(lons)
    assert ylim[0] <= min(lats) and ylim[1] >= max(lats)
    # A loose upper bound: the view shouldn't be many degrees wider than the network itself.
    assert xlim[1] - xlim[0] < (max(lons) - min(lons)) + 2
    assert ylim[1] - ylim[0] < (max(lats) - min(lats)) + 2


def test_conditions_xaxis_stays_pinned_when_a_variable_is_entirely_nan():
    # Regression test for a real bug caught against live CMEMS data (sherkin-island): a variable
    # that's entirely NaN (e.g. a source's land mask covering the whole bbox) has no valid data
    # point for matplotlib to autoscale its x-axis from, so it silently fell back to a default
    # range near matplotlib's epoch -- making a multi-month plot look like it only spanned a day.
    time = pd.date_range("2024-01-01", "2024-03-30", freq="1h", tz="UTC")
    table = empty_frame()
    table = pd.concat(
        [
            table,
            pd.DataFrame(
                {
                    "route_id": "R1",
                    "vertex_index": 0,
                    "time": time,
                    "wind_speed": 5.0,
                    "wind_from_direction": 180.0,
                    "current_speed": float("nan"),  # entirely NaN, like the real case
                    "current_to_direction": float("nan"),
                    "wave_height": float("nan"),
                    "wave_from_direction": float("nan"),
                    "wave_period": float("nan"),
                }
            ),
        ],
        ignore_index=True,
    )

    fig = plt.figure()
    gs = fig.add_gridspec(1, 1)
    _plot_conditions(fig, gs[0], table)

    expected_min = mdates.date2num(time.min())
    expected_max = mdates.date2num(time.max())
    for ax in fig.axes:
        got_min, got_max = ax.get_xlim()
        assert got_min == expected_min
        assert got_max == expected_max
    plt.close(fig)
