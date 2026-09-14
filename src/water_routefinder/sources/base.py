"""Shared source-provider plumbing: bounding boxes and the ``fetch`` contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

import xarray as xr

from water_routefinder.network import Network


@dataclass(frozen=True)
class BBox:
    """A geographic bounding box, WGS84 degrees."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def __post_init__(self) -> None:
        if self.min_lon >= self.max_lon or self.min_lat >= self.max_lat:
            raise ValueError(f"degenerate bbox: {self}")

    def to_dict(self) -> dict[str, float]:
        return {
            "min_lon": self.min_lon,
            "min_lat": self.min_lat,
            "max_lon": self.max_lon,
            "max_lat": self.max_lat,
        }

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> BBox:
        return cls(min_lon=d["min_lon"], min_lat=d["min_lat"], max_lon=d["max_lon"], max_lat=d["max_lat"])


def bbox_from_network(network: Network, margin_deg: float = 0.1) -> BBox:
    """The network's route/harbour bounding box, expanded by ``margin_deg`` on every side."""
    lats: list[float] = [h.lat for h in network.harbours]
    lons: list[float] = [h.lon for h in network.harbours]
    for r in network.routes:
        lats.extend(p.lat for p in r.path)
        lons.extend(p.lon for p in r.path)
    return BBox(
        min_lon=min(lons) - margin_deg,
        min_lat=min(lats) - margin_deg,
        max_lon=max(lons) + margin_deg,
        max_lat=max(lats) + margin_deg,
    )


class SourceProvider(Protocol):
    """One met-ocean product family, returned on its native grid, standard names/units/units."""

    def fetch(
        self,
        *,
        variables: tuple[str, ...],
        bbox: BBox,
        start: date | datetime,
        end: date | datetime,
        dataset_id: str | None = None,
    ) -> xr.Dataset: ...
