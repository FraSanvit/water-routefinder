"""One overview PNG per network: ``results/{network}/{network}_diag_plot.png``.

Three panels: the route map (optionally over a real land basemap), per-variable conditions over
time (min/mean/max across all vertices), and a data-quality summary (NaN fraction / vertex count
per route).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from water_routefinder.io import load_network
from water_routefinder.network import Network
from water_routefinder.schema import VARIABLES
from water_routefinder.sources.base import bbox_from_network


def make_diag_plot(
    bundle_dir: str | Path,
    out_png: str | Path,
    *,
    title: str | None = None,
    basemap: bool = True,
) -> Path:
    """Build and save the diagnostic figure; returns the path written.

    ``basemap`` overlays real land polygons behind the route map -- read from a small,
    fully-offline, no-network-call local file (see ``_add_basemap``). Pass ``False`` to skip it
    (e.g. a minimal bare-axes plot).
    """
    bundle_dir = Path(bundle_dir)
    out_png = Path(out_png)
    network = load_network(bundle_dir / "network")
    table = pd.read_parquet(bundle_dir / "environment" / "conditions.parquet")

    fig = plt.figure(figsize=(11, 18), constrained_layout=True)
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 6, 2])
    _plot_map(fig.add_subplot(gs[0]), network, basemap=basemap)
    _plot_conditions(fig, gs[1], table)
    _plot_quality(fig.add_subplot(gs[2]), table, network)
    fig.suptitle(title or f"{bundle_dir.name} — conditions diagnostics", fontsize=14)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        # A twin axis in a tightly-packed data-quality panel can trip constrained_layout's
        # "axes collapsed to zero" heuristic; harmless, the figure still renders correctly.
        warnings.filterwarnings("ignore", message="constrained_layout not applied")
        fig.savefig(out_png, dpi=110)
    plt.close(fig)
    return out_png


#: Land polygons for the basemap: Natural Earth 1:10m "land" (public domain), clipped to Europe
#: + North Atlantic approaches (lon -30..35, lat 32..72 -- covers every example network, with
#: room for more) and re-saved as GeoParquet. A plain local file, not a live web-tile fetch: the
#: first cut of this used `contextily` to pull map tiles at render time, which turned out to be
#: a bad trade for a diagnostic plot -- checked directly against three tile providers from a
#: slow/restricted network: Esri ~48s/tile, OpenStreetMap ~7s/tile *and* an outright 403 (its
#: tile usage policy blocks automated clients without a compliant User-Agent), CartoDB requires
#: an API key everywhere now, including its old "free" endpoint (serves an "API key required"
#: watermark image with a 200 status -- fails silently, not even an exception). None of that can
#: happen to a bundled static file: no network call, no timeout, no rate limit, no ToS, and it's
#: faster besides.
_BASEMAP_PATH = Path(__file__).resolve().parents[2] / "resources" / "basemap" / "europe_land_10m.parquet"


def _plot_map(ax, network: Network, *, basemap: bool) -> None:
    if basemap:
        _add_basemap(ax)
    for route in network.routes:
        lats = [p.lat for p in route.path]
        lons = [p.lon for p in route.path]
        ax.plot(lons, lats, marker=".", markersize=3, linewidth=1.2, zorder=5, label=route.route_id)
    for h in network.harbours:
        ax.scatter([h.lon], [h.lat], marker="s", s=40, color="black", zorder=6)
        ax.annotate(
            h.harbour_id, (h.lon, h.lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=6
        )
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("Network")
    if basemap:
        # The basemap layer spans all of Europe -- without an explicit xlim/ylim, autoscale
        # would fit *that* instead of the network, zooming out to the whole continent for e.g. a
        # Dublin Bay route. adjustable="box" (not the default "datalim") keeps these exact limits:
        # "datalim" lets the equal-aspect constraint silently override one of them to fit the
        # axes' box shape instead -- which clipped the latitude axis off the figure entirely.
        bbox = bbox_from_network(network, margin_deg=0.05)
        ax.set_xlim(bbox.min_lon, bbox.max_lon)
        ax.set_ylim(bbox.min_lat, bbox.max_lat)
        ax.set_aspect("equal", adjustable="box")
    else:
        ax.set_aspect("equal", adjustable="datalim")
    if network.routes:
        ax.legend(fontsize=7, loc="best", ncol=2)


def _add_basemap(ax) -> None:
    """Best-effort land backdrop from the bundled Natural Earth extract. Never fails the plot --
    a missing/corrupt file or a missing geopandas install just means no basemap (a warning, not
    a crash) -- though neither should happen in a normal install."""
    try:
        import geopandas as gpd

        land = gpd.read_parquet(_BASEMAP_PATH)
        ax.set_facecolor("#eef6fb")
        land.plot(ax=ax, color="#e2ddd0", edgecolor="#a8a296", linewidth=0.4, zorder=0)
    except Exception as exc:  # noqa: BLE001 - any failure here is cosmetic, never fatal
        warnings.warn(f"diagnostics: basemap unavailable, plotting without it ({exc})", stacklevel=2)


def _plot_conditions(fig, gridspec_slot, table: pd.DataFrame) -> None:
    inner = gridspec_slot.subgridspec(len(VARIABLES), 1, hspace=0.6)
    grouped = table.groupby("time")
    # Pin every subplot to the table's real time span explicitly, rather than trusting
    # autoscale: a variable that's entirely NaN (real, e.g. a source's land mask covering the
    # whole bbox) has no valid (x, y) pairs to autoscale from, so matplotlib falls back to a
    # meaningless default range near its epoch -- which, shown only on the last subplot (the
    # others hide their tick labels to avoid clutter), reads as if the *whole* multi-month plot
    # only covered a single day.
    time_min, time_max = table["time"].min(), table["time"].max()
    for i, var in enumerate(VARIABLES):
        ax = fig.add_subplot(inner[i])
        stats = grouped[var].agg(["min", "mean", "max"])
        ax.plot(stats.index, stats["mean"], color="tab:blue", linewidth=1)
        ax.fill_between(stats.index, stats["min"], stats["max"], color="tab:blue", alpha=0.2)
        ax.set_xlim(time_min, time_max)
        ax.set_title(var, fontsize=8, loc="left", pad=2)
        ax.tick_params(labelsize=6)
        if i < len(VARIABLES) - 1:
            ax.set_xticklabels([])
    fig.axes[-1].set_xlabel("time")


def _plot_quality(ax, table: pd.DataFrame, network) -> None:
    per_route = table.groupby("route_id")
    route_ids = [r.route_id for r in network.routes]
    nan_frac = [per_route.get_group(rid)[list(VARIABLES)].isna().mean().mean() if rid in per_route.groups else float("nan") for rid in route_ids]
    vertex_count = [len(r.path) for r in network.routes]

    x = range(len(route_ids))
    ax2 = ax.twinx()
    ax.bar(x, nan_frac, color="tab:red", alpha=0.6, label="NaN fraction")
    ax2.bar([i + 0.35 for i in x], vertex_count, width=0.35, color="tab:gray", alpha=0.6, label="vertex count")
    ax.set_xticks([i + 0.175 for i in x])
    ax.set_xticklabels(route_ids, rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("NaN fraction", color="tab:red")
    ax2.set_ylabel("vertex count", color="tab:gray")
    ax.set_title("Data quality")
