"""Sample a harmonised grid onto route geometry.

May densify each route's geometry first (target vertex spacing, per the contract's
recommendation of ~1-2 km); interpolates the grid to every (possibly new) vertex at every
timestep; returns a tidy table plus the (possibly densified) network for ``bundle.py`` to re-emit
as ``routes.geojson``.
"""

from __future__ import annotations

import pandas as pd
import xarray as xr

from water_routefinder import geo
from water_routefinder.network import Network
from water_routefinder.schema import VARIABLES, coerce_dtypes


def sample(
    grid: xr.Dataset, network: Network, *, densify_km: float | None
) -> tuple[pd.DataFrame, Network]:
    """Bilinear-sample ``grid`` onto every route vertex at every timestep.

    Returns ``(table, network)`` — ``table`` sorted by ``route_id, vertex_index, time``, dtyped
    per :mod:`water_routefinder.schema`; ``network`` has each route's (possibly densified) path,
    for the caller to re-emit as ``routes.geojson``.
    """
    target_m = densify_km * 1000.0 if densify_km else None
    new_routes = []
    frames: list[pd.DataFrame] = []

    for route in network.routes:
        points = geo.densify_line(route.path, target_m) if target_m else list(route.path)
        new_routes.append(route.with_path(tuple(points)))

        lat_idx = xr.DataArray([p.lat for p in points], dims="vertex")
        lon_idx = xr.DataArray([p.lon for p in points], dims="vertex")
        sampled = grid.interp(latitude=lat_idx, longitude=lon_idx, method="linear")

        df = sampled[list(VARIABLES)].to_dataframe().reset_index()
        df = df.rename(columns={"vertex": "vertex_index"})
        df["route_id"] = route.route_id
        frames.append(df[["route_id", "vertex_index", "time", *VARIABLES]])

    table = pd.concat(frames, ignore_index=True)
    table = coerce_dtypes(table)
    table = table.sort_values(["route_id", "vertex_index", "time"]).reset_index(drop=True)

    return table, network.with_routes(tuple(new_routes))
