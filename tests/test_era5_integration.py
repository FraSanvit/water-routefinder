"""Live CDS/ERA5 check. Needs a ~/.cdsapirc or CDSAPI_URL/CDSAPI_KEY; skipped otherwise.

Not run on every PR -- see .github/workflows/integration.yml (nightly + workflow_dispatch).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from water_routefinder.sources import era5
from water_routefinder.sources.base import BBox

pytestmark = pytest.mark.integration

_HAS_CREDS = bool(os.environ.get("CDSAPI_KEY")) or (Path.home() / ".cdsapirc").is_file()


@pytest.mark.skipif(not _HAS_CREDS, reason="no CDS API credentials (CDSAPI_KEY or ~/.cdsapirc)")
def test_fetch_wind_over_dublin_bay():
    bbox = BBox(min_lon=-6.3, min_lat=53.2, max_lon=-6.0, max_lat=53.4)
    ds = era5.fetch(
        family="wind",
        variables=("10m_u_component_of_wind", "10m_v_component_of_wind"),
        bbox=bbox,
        start="2024-01-01",
        end="2024-01-02",
    )
    assert "wind_speed" in ds.data_vars
    assert "wind_from_direction" in ds.data_vars
