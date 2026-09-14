from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from water_routefinder.diagnostics import _plot_conditions, make_diag_plot
from water_routefinder.schema import empty_frame


def test_make_diag_plot_writes_a_non_empty_png(expected_bundle_dir, tmp_path):
    out_png = tmp_path / "dublin-bay_diag_plot.png"
    result = make_diag_plot(expected_bundle_dir, out_png)
    assert result == out_png
    assert out_png.is_file()
    assert out_png.stat().st_size > 1000
    assert out_png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


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
