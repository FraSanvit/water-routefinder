"""Two diagnostic PNGs per network.

``{network}_diag_plot.png`` (``make_diag_plot``): three panels, sharing one colour per route
between the first two -- the route map (dashed lines, optionally over a real land basemap),
per-variable conditions over time (one line per route, mean across its vertices), and a
data-quality summary (NaN fraction / vertex count per route, as horizontal bars). Reads the
already-sampled ``conditions.parquet`` (one row per route vertex per timestep).

``{network}_availability_map.png`` (``make_availability_plot``): one map per variable (magnitude
+ direction, for each of wind/current/wave), coloured by that grid cell's time-mean value, with
the routes overlaid -- a masked (permanently land-blocked) grid cell renders as transparent, so a
route crossing a gap in the colour is directly visible. Reads the harmonised *grid*
(``resources/automatic/{network}/grid.nc``), not the sampled table -- the whole point is to see
the source data's own spatial footprint before route-sampling, not what got interpolated onto
the route.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import xarray as xr

from water_routefinder.io import load_network
from water_routefinder.network import Network
from water_routefinder.schema import VARIABLE_UNITS, VARIABLES


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

    # figsize/height_ratios are tuned together so the map row's own box (full width, this row's
    # share of the height) comes out close to a 4:3 landscape shape (~1.35 width:height) rather
    # than the very wide, short strip a naive [3, 6, 2] split over this height would give (~2.5:1)
    # -- `_fit_to_panel_aspect` fills whatever box it's handed, so a too-wide box forces a
    # north-south route (e.g. rosslare-roscoff) into an unreasonably wide lon view. Taller overall
    # (21in vs the conditions/quality rows' previous 18in) so those two rows keep roughly their
    # previous absolute height instead of shrinking to make room for a taller map row.
    fig = plt.figure(figsize=(11, 21), constrained_layout=True)
    gs = fig.add_gridspec(3, 1, height_ratios=[5, 6, 2])
    route_colors = _plot_map(fig.add_subplot(gs[0]), network, basemap=basemap)
    _plot_conditions(fig, gs[1], table, route_colors)
    _plot_quality(fig, gs[2], table, network)
    fig.suptitle(title or f"{bundle_dir.name} — conditions diagnostics", fontsize=14)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    return out_png


#: Which of the 7 contract variables get a panel here, and how they're paired up -- one row per
#: family (wind, current, wave), magnitude next to its direction. Deliberately excludes
#: wave_period: it's a real magnitude field, but it isn't "wave, wind, current... and direction",
#: and folding it in would break the tidy 3x2 grid for no real gain (its own availability already
#: matches wave_height's -- both come from the same source dataset).
_AVAILABILITY_LAYOUT: tuple[tuple[str, str], ...] = (
    ("wind_speed", "wind_from_direction"),
    ("current_speed", "current_to_direction"),
    ("wave_height", "wave_from_direction"),
)

#: Direction variables need a cyclic colormap -- a sequential one (e.g. viridis) on 0-360 degrees
#: shows a false discontinuity at the wrap-around, since 359 deg and 1 deg are nearly the same
#: direction but would land at opposite ends of the colour scale.
_DIRECTION_VARS = frozenset(dir_var for _, dir_var in _AVAILABILITY_LAYOUT)


def make_availability_plot(
    bundle_dir: str | Path,
    grid_path: str | Path,
    out_png: str | Path,
    *,
    title: str | None = None,
    basemap: bool = True,
) -> Path:
    """Build and save the data-availability figure; returns the path written.

    One map per variable in ``_AVAILABILITY_LAYOUT``, coloured by that grid cell's time-mean
    value (``skipna``): a cell that's masked (NaN) at every timestep -- the common case all
    through this project's coastal-resolution investigations -- stays NaN in the mean too, so it
    renders as a transparent gap the route can be seen crossing, exactly the same as it would from
    any single snapshot. The mean is used anyway, not a single timestep, because it's strictly
    more informative for the cells that *do* have data (a representative value, not one arbitrary
    hour's noise) at no cost to the availability check itself.

    ``bundle_dir`` supplies the network geometry (``bundle_dir/network/``); ``grid_path`` is the
    harmonised grid (``resources/automatic/{network}/grid.nc``) -- a different input than
    ``make_diag_plot``, which reads the already-sampled table instead.
    """
    bundle_dir = Path(bundle_dir)
    out_png = Path(out_png)
    network = load_network(bundle_dir / "network")

    with xr.open_dataset(grid_path) as grid:
        fig = plt.figure(figsize=(11, 15), constrained_layout=True)
        gs = fig.add_gridspec(len(_AVAILABILITY_LAYOUT), 2)
        for row, pair in enumerate(_AVAILABILITY_LAYOUT):
            for col, var in enumerate(pair):
                _plot_availability_panel(fig.add_subplot(gs[row, col]), grid, var, network, basemap=basemap)
        fig.suptitle(title or f"{bundle_dir.name} — data availability", fontsize=14)

        out_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_png, dpi=110)
        plt.close(fig)
    return out_png


def _plot_availability_panel(ax, grid: xr.Dataset, var: str, network: Network, *, basemap: bool):
    """One variable's time-mean value, per grid cell, as coloured pixels -- plus the same
    basemap/route/harbour overlay as `_plot_map`, reusing its exact framing logic so this panel is
    just as correctly proportioned regardless of the network's shape. Returns the `QuadMesh`
    (rather than leaving callers to fish it out of `ax.collections`, which also picks up the
    harbour markers plotted afterwards)."""
    # Pin the box's physical shape up front, before anything is drawn on it: with 6 of these
    # panels sharing one constrained_layout solve (unlike the single-map main diag plot), each
    # variable's colorbar has different tick-label text (e.g. "4" vs "0.10"), and left free that
    # nudges its own column narrower/wider than its siblings, and a basemap's autoscale can do the
    # same to row heights -- both were observed to make same-network panels visibly different
    # sizes despite identical data. `set_box_aspect` is layout-engine-aware (unlike
    # `set_aspect(..., adjustable="box")`, which only reacts to data limits): it tells
    # constrained_layout up front "this box has exactly this shape," so sibling decorations can no
    # longer perturb it.
    ax.set_box_aspect(1 / _panel_aspect_ratio(ax))

    if basemap:
        _add_basemap(ax)

    values = grid[var].mean(dim="time", skipna=True)
    cmap = "twilight" if var in _DIRECTION_VARS else "viridis"
    # shading="auto": picks the right convention automatically for 1-D cell-centre coordinates
    # (this grid's `latitude`/`longitude`) vs. cell-edge ones -- no need to hand-compute edges.
    # alpha < 1: lets the basemap's coastline show through the coloured cells, so land that
    # happens to fall *inside* a coarse, mostly-water grid cell is still visible under the colour,
    # not just at the fully-transparent (NaN) gaps.
    mesh = ax.pcolormesh(grid["longitude"], grid["latitude"], values, shading="auto", cmap=cmap, alpha=0.7, zorder=1)
    ax.figure.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04, label=VARIABLE_UNITS.get(var, ""))

    # A single bold colour, not one per route (unlike `_plot_map`'s legend): several thin
    # differently-coloured lines would be hard to read against a full-colourmap background: the
    # point here is "does the route cross a gap", not "which route is which".
    for route in network.routes:
        lats = [p.lat for p in route.path]
        lons = [p.lon for p in route.path]
        ax.plot(lons, lats, linestyle="--", color="black", linewidth=1.2, zorder=5)
    for h in network.harbours:
        ax.scatter([h.lon], [h.lat], marker="s", s=30, color="black", zorder=6)

    ax.set_title(var, fontsize=9)
    ax.tick_params(labelsize=6)

    lon_min, lon_max, lat_min, lat_max = _network_extent(network)
    lon_pad = max((lon_max - lon_min) * _MAP_MARGIN_FRACTION, _MAP_MIN_MARGIN_DEG)
    lat_pad = max((lat_max - lat_min) * _MAP_MARGIN_FRACTION, _MAP_MIN_MARGIN_DEG)
    lon_min, lon_max = lon_min - lon_pad, lon_max + lon_pad
    lat_min, lat_max = lat_min - lat_pad, lat_max + lat_pad
    lon_min, lon_max, lat_min, lat_max = _fit_to_panel_aspect(ax, lon_min, lon_max, lat_min, lat_max)
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    # No `set_aspect(..., adjustable="box")` here (unlike `_plot_map`): `set_box_aspect` above
    # already owns the box's physical shape, and the xlim/ylim just set already match it (same
    # `_fit_to_panel_aspect` math `_plot_map` uses) -- stacking the two box-shape mechanisms would
    # be redundant at best, and risks re-introducing the exact per-panel size drift this is meant
    # to fix.
    return mesh


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

#: Map view padding, as a fraction of the network's own lon/lat span -- not a fixed number of
#: degrees. A fixed margin looks fine on a small network (e.g. Dublin Bay, ~0.3 deg across) but is
#: barely visible on a long one (e.g. Rosslare-Roscoff, ~3.6 deg across), leaving harbours pinned
#: right at the figure edge. `_MAP_MIN_MARGIN_DEG` is just a floor for the degenerate case of a
#: near-zero-extent network (e.g. a single very short route).
_MAP_MARGIN_FRACTION = 0.08
_MAP_MIN_MARGIN_DEG = 0.01


def _network_extent(network: Network) -> tuple[float, float, float, float]:
    """(min_lon, max_lon, min_lat, max_lat) across every route vertex and harbour."""
    lons = [p.lon for r in network.routes for p in r.path] + [h.lon for h in network.harbours]
    lats = [p.lat for r in network.routes for p in r.path] + [h.lat for h in network.harbours]
    return min(lons), max(lons), min(lats), max(lats)


def _plot_map(ax, network: Network, *, basemap: bool) -> dict[str, str]:
    """Draw the route map; returns ``{route_id: colour}`` so ``_plot_conditions`` can reuse the
    same colour per route."""
    if basemap:
        _add_basemap(ax)

    route_colors: dict[str, str] = {}
    for route in network.routes:
        lats = [p.lat for p in route.path]
        lons = [p.lon for p in route.path]
        (line,) = ax.plot(
            lons, lats, linestyle="--", marker=".", markersize=3, linewidth=1.2, zorder=5, label=route.route_id
        )
        route_colors[route.route_id] = line.get_color()
    for h in network.harbours:
        ax.scatter([h.lon], [h.lat], marker="s", s=40, color="black", zorder=6)
        ax.annotate(
            h.harbour_id, (h.lon, h.lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=6
        )
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("Network")

    lon_min, lon_max, lat_min, lat_max = _network_extent(network)
    lon_pad = max((lon_max - lon_min) * _MAP_MARGIN_FRACTION, _MAP_MIN_MARGIN_DEG)
    lat_pad = max((lat_max - lat_min) * _MAP_MARGIN_FRACTION, _MAP_MIN_MARGIN_DEG)
    lon_min, lon_max = lon_min - lon_pad, lon_max + lon_pad
    lat_min, lat_max = lat_min - lat_pad, lat_max + lat_pad
    lon_min, lon_max, lat_min, lat_max = _fit_to_panel_aspect(ax, lon_min, lon_max, lat_min, lat_max)
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    # adjustable="box": now that the limits above are pre-padded to already match the panel's own
    # aspect ratio, this is a no-op in the common case (nothing left to shrink) -- but it still
    # matters: it turns "this box has a fixed shape" back into a real constraint constrained_layout
    # must honour, rather than leaving the axes free to grow however it likes ("auto"). Without it,
    # the map row was observed pulling height away from its sibling rows (the conditions panel's 7
    # subplots got squeezed down to ~0.2in tall each) since nothing was left telling the solver the
    # map had any size preference of its own once its aspect was left unconstrained.
    ax.set_aspect("equal", adjustable="box")

    if network.routes:
        ax.legend(fontsize=7, loc="best", ncol=2)
    return route_colors


def _panel_aspect_ratio(ax) -> float:
    """Approximate width:height of ``ax``'s own box, in inches, from its default gridspec-derived
    position and the figure's size -- read before ``constrained_layout`` makes its final pass
    (which also reserves space for the title/legend/labels, not accounted for here). An
    approximation, not exact, but a stable and cheap one: it depends only on the figure size and
    the gridspec's row/column ratios, not on how the plot's content happens to render."""
    pos = ax.get_position()
    fig_w, fig_h = ax.figure.get_size_inches()
    return (pos.width * fig_w) / (pos.height * fig_h)


def _fit_to_panel_aspect(
    ax, lon_min: float, lon_max: float, lat_min: float, lat_max: float
) -> tuple[float, float, float, float]:
    """Grow (never shrink) whichever of the lon/lat span is under-filling its panel, so the map
    fills the whole box its panel is allotted instead of matplotlib shrinking the box to match the
    data (``aspect="equal", adjustable="box"``, the previous approach) -- which, on an elongated
    network (e.g. Sherkin Island: a wide longitude span, a narrow latitude one), could squeeze the
    box down enough to clip its own y-axis off the figure. Whichever dimension's span already
    fills more of its share of the panel is the anchor and is left alone; the other is extended,
    symmetrically, until lon_span:lat_span matches the panel's own width:height -- e.g. a network
    spanning 3 deg lon x 2.5 deg lat in a 4:3 panel: 3 / 2.5 = 1.2 is less than 4 / 3 = 1.33, so
    the panel is relatively wider than the data, lat is the anchor, and lon grows from 3 deg to
    2.5 * (4 / 3) = 3.33 deg to fill the panel's width.

    Degrees are compared directly (no latitude/cos correction), consistent with the plain
    equirectangular treatment the rest of this map already uses.
    """
    lon_span, lat_span = lon_max - lon_min, lat_max - lat_min
    panel_aspect = _panel_aspect_ratio(ax)
    data_aspect = lon_span / lat_span

    if data_aspect < panel_aspect:
        # The panel is relatively wider than the data -- lat is the anchor, lon needs widening.
        lon_center = (lon_min + lon_max) / 2
        half = (lat_span * panel_aspect) / 2
        lon_min, lon_max = lon_center - half, lon_center + half
    else:
        # The data is relatively wider than the panel -- lon is the anchor, lat needs heightening.
        lat_center = (lat_min + lat_max) / 2
        half = (lon_span / panel_aspect) / 2
        lat_min, lat_max = lat_center - half, lat_center + half

    return lon_min, lon_max, lat_min, lat_max


def _add_basemap(ax) -> None:
    """Best-effort land backdrop from the bundled Natural Earth extract. Never fails the plot --
    a missing/corrupt file or a missing geopandas install just means no basemap (a warning, not
    a crash) -- though neither should happen in a normal install."""
    try:
        import geopandas as gpd

        land = gpd.read_parquet(_BASEMAP_PATH)
        ax.set_facecolor("#eef6fb")
        # aspect=None: geopandas' own default otherwise re-imposes an equal (lat-corrected) aspect
        # on `ax` regardless of anything we do -- silently undoing `_fit_to_panel_aspect` below,
        # which relies on the axes staying at matplotlib's own default aspect ("auto", fill the
        # box) so the panel's box is never shrunk to match the data.
        land.plot(ax=ax, color="#e2ddd0", edgecolor="#a8a296", linewidth=0.4, zorder=0, aspect=None)
    except Exception as exc:  # noqa: BLE001 - any failure here is cosmetic, never fatal
        warnings.warn(f"diagnostics: basemap unavailable, plotting without it ({exc})", stacklevel=2)


def _plot_conditions(fig, gridspec_slot, table: pd.DataFrame, route_colors: dict[str, str]) -> None:
    """One subplot per variable; one line per route (mean across that route's vertices), each in
    the same colour as its line on the Network map -- which is also this plot's only legend."""
    # No explicit hspace here -- passing one directly to a nested subgridspec breaks
    # constrained_layout's row-height solve for that block specifically (confirmed by bisection:
    # any hspace > 0 on this 7-row nested subgridspec starved it down to a sliver, ~0.2in per
    # subplot instead of the ~1in it should get, and above ~0.42 it fails outright with "axes sizes
    # collapsed to zero" and abandons layout for the *entire* figure -- which was the real cause of
    # a previous bug where the map panel's y-axis tick labels got clipped off the saved PNG,
    # nothing to do with the map panel itself). constrained_layout still adds its own padding
    # between these subplots automatically, to clear each one's title/tick decorations.
    inner = gridspec_slot.subgridspec(len(VARIABLES), 1)
    # Pin every subplot to the table's real time span explicitly, rather than trusting
    # autoscale: a variable that's entirely NaN (real, e.g. a source's land mask covering the
    # whole bbox) has no valid (x, y) pairs to autoscale from, so matplotlib falls back to a
    # meaningless default range near its epoch -- which, shown only on the last subplot (the
    # others hide their tick labels to avoid clutter), reads as if the *whole* multi-month plot
    # only covered a single day.
    time_min, time_max = table["time"].min(), table["time"].max()
    for i, var in enumerate(VARIABLES):
        ax = fig.add_subplot(inner[i])
        for route_id, color in route_colors.items():
            series = table.loc[table["route_id"] == route_id].groupby("time")[var].mean()
            ax.plot(series.index, series.values, color=color, linewidth=1)
        ax.set_xlim(time_min, time_max)
        ax.set_title(var, fontsize=8, loc="left", pad=2)
        ax.tick_params(labelsize=6)
        if i < len(VARIABLES) - 1:
            ax.set_xticklabels([])
    fig.axes[-1].set_xlabel("time")


def _plot_quality(fig, gridspec_slot, table: pd.DataFrame, network) -> None:
    """Two side-by-side horizontal-bar panels, one row per route: NaN fraction (left) and vertex
    count (right), sharing the y-axis so the route labels line up between them. Two independent
    axes rather than one axis with a `twiny()` secondary axis -- a twin axis's extra ticks/label
    sit right where `constrained_layout` expects a title to go, and it has no notion of the space
    that needs, so it collided with neighbouring panels no matter how much padding was added.
    Separate axes are each laid out normally, so the collision doesn't happen in the first place."""
    per_route = table.groupby("route_id")
    route_ids = [r.route_id for r in network.routes]
    nan_frac = [
        per_route.get_group(rid)[list(VARIABLES)].isna().mean().mean() if rid in per_route.groups else float("nan")
        for rid in route_ids
    ]
    vertex_count = [len(r.path) for r in network.routes]

    inner = gridspec_slot.subgridspec(1, 2, wspace=0.08)
    ax_nan = fig.add_subplot(inner[0])
    ax_vtx = fig.add_subplot(inner[1], sharey=ax_nan)

    y = list(range(len(route_ids)))
    ax_nan.barh(y, nan_frac, height=0.6, color="tab:red", alpha=0.8)
    ax_vtx.barh(y, vertex_count, height=0.6, color="tab:gray", alpha=0.8)

    ax_nan.set_yticks(y)
    ax_nan.set_yticklabels(route_ids, fontsize=7)
    ax_nan.invert_yaxis()  # first route at the top
    ax_nan.tick_params(axis="x", labelsize=7)
    ax_nan.set_xlabel("NaN fraction", fontsize=8)
    ax_nan.set_title("Data quality — NaN fraction", fontsize=9)
    # Fixed 0-1 range, not autoscaled to whatever the worst route happens to be: the whole point of
    # this metric is to see at a glance how bad it is, which an autoscaled axis defeats -- 30% NaN
    # would fill the same bar width as 100% NaN if the axis just scaled to that run's own max.
    ax_nan.set_xlim(0, 1)

    # axis="y" here, not "x": `labelleft` is a *y*-axis-ticks setting, so a previous version of
    # this call (scoped to axis="x") silently never hid these labels -- `sharey` only shares tick
    # positions/limits, not label visibility or font size, so ax_vtx was rendering its own copy of
    # the route labels at matplotlib's default font size (visibly bigger than ax_nan's explicit
    # 7pt) instead of being hidden as intended.
    ax_vtx.tick_params(axis="y", labelleft=False)
    ax_vtx.tick_params(axis="x", labelsize=7)
    ax_vtx.set_xlabel("vertex count", fontsize=8)
    ax_vtx.set_title("Data quality — vertex count", fontsize=9)
