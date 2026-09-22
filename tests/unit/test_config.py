from __future__ import annotations

import pytest
from pydantic import ValidationError

from water_routefinder.config import WorkflowConfig, load_config

_BASE = {
    "time": {"start": "2024-01-01", "end": "2024-01-08"},
    "sources": {
        "current": {"provider": "cmems", "variables": ["uo", "vo"]},
        "wave": {"provider": "cmems", "variables": ["VHM0"]},
        "wind": {"provider": "era5", "variables": ["10m_u_component_of_wind"]},
    },
}


def test_valid_config_parses():
    cfg = WorkflowConfig.model_validate(_BASE)
    assert cfg.sample.densify_km == 1.5
    assert cfg.harmonise.target_step == "1h"
    assert cfg.diagnostics.basemap is True


def test_basemap_can_be_disabled():
    cfg = WorkflowConfig.model_validate({**_BASE, "diagnostics": {"basemap": False}})
    assert cfg.diagnostics.basemap is False


def test_era5_current_is_rejected():
    bad = {
        **_BASE,
        "sources": {**_BASE["sources"], "current": {"provider": "era5", "variables": ["x"]}},
    }
    with pytest.raises(ValidationError, match="current"):
        WorkflowConfig.model_validate(bad)


def test_unsupported_provider_is_rejected():
    bad = {
        **_BASE,
        "sources": {**_BASE["sources"], "wind": {"provider": "mock", "variables": ["x"]}},
    }
    with pytest.raises(ValidationError):
        WorkflowConfig.model_validate(bad)


def test_end_before_start_is_rejected():
    bad = {**_BASE, "time": {"start": "2024-01-08", "end": "2024-01-01"}}
    with pytest.raises(ValidationError):
        WorkflowConfig.model_validate(bad)


def test_load_config_reads_the_shipped_example(repo_root):
    cfg = load_config(repo_root / "config" / "config.yaml")
    # The shipped config deliberately doesn't say which network to build (one config for all of
    # them; `run-network`/`run-demo` choose per run) -- empty means "every folder under
    # resources/user/".
    assert cfg.networks == ()
    assert cfg.sources["current"].provider == "cmems"
