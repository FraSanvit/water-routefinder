"""Live Copernicus Marine check. Needs CMEMS_USERNAME/CMEMS_PASSWORD; skipped otherwise.

Not run on every PR -- see .github/workflows/integration.yml (nightly + workflow_dispatch).
"""

from __future__ import annotations

import os

import pytest

from water_routefinder.sources import cmems
from water_routefinder.sources.base import BBox

pytestmark = pytest.mark.integration

_HAS_CREDS = bool(os.environ.get("CMEMS_USERNAME")) and bool(os.environ.get("CMEMS_PASSWORD"))


@pytest.mark.skipif(not _HAS_CREDS, reason="CMEMS_USERNAME/CMEMS_PASSWORD not set")
def test_fetch_current_over_dublin_bay():
    bbox = BBox(min_lon=-6.3, min_lat=53.2, max_lon=-6.0, max_lat=53.4)
    ds = cmems.fetch(family="current", variables=("uo", "vo"), bbox=bbox, start="2024-01-01", end="2024-01-02")
    assert "current_speed" in ds.data_vars
    assert "current_to_direction" in ds.data_vars
