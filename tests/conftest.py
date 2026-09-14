"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

# Loaded at collection time, before test_cmems_integration.py / test_era5_integration.py /
# test_workflow.py check os.environ for credentials -- see .env.example.
load_dotenv(REPO_ROOT / ".env")


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def demo_network_dir() -> Path:
    """The example input this repo ships: resources/user/dublin-bay/."""
    return REPO_ROOT / "resources" / "user" / "dublin-bay"


@pytest.fixture
def expected_bundle_dir() -> Path:
    """A committed, structurally-valid bundle fixture, used by tests that don't need real data
    (validate.py, diagnostics.py) and by the live-CMEMS workflow test's network-geometry check."""
    return REPO_ROOT / "tests" / "integration" / "expected"
