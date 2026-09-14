"""End-to-end: run the real Snakemake DAG (live cmems provider) and check what it produces.

The workflow supports only ``cmems``/``era5`` for now (no offline mock provider -- see
docs/roadmap.md), so this needs CMEMS_USERNAME/CMEMS_PASSWORD and is credential-gated; it does not
run on every PR (see .github/workflows/integration.yml).
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from water_routefinder.validate import validate_bundle

pytestmark = pytest.mark.integration

_HAS_CREDS = bool(os.environ.get("CMEMS_USERNAME")) and bool(os.environ.get("CMEMS_PASSWORD"))


def _run_workflow(repo_root):
    snakemake = shutil.which("snakemake")
    if snakemake is None:
        pytest.skip("snakemake not on PATH (run under `pixi run test-integration-live`)")
    result = subprocess.run(
        [
            snakemake,
            "--snakefile",
            "workflow/Snakefile",
            "--configfile",
            "tests/integration/test_config.yaml",
            "--cores",
            "1",
            "--forceall",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"snakemake exited {result.returncode}\n--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )


@pytest.mark.skipif(not _HAS_CREDS, reason="CMEMS_USERNAME/CMEMS_PASSWORD not set")
def test_workflow_builds_a_valid_bundle(repo_root, expected_bundle_dir):
    _run_workflow(repo_root)
    built = repo_root / "results" / "dublin-bay"

    assert validate_bundle(built) == []

    # Route/harbour geometry is deterministic (independent of the data source) -- compare against
    # the committed fixture. Table *values* are live CMEMS data and vary run to run, so only the
    # structural checks above (validate_bundle) apply to environment/conditions.parquet.
    for rel in ("network/harbours.csv", "network/routes.geojson"):
        assert (built / rel).read_bytes() == (expected_bundle_dir / rel).read_bytes(), rel

    diag_plot = built / "dublin-bay_diag_plot.png"
    assert diag_plot.is_file()
    assert diag_plot.stat().st_size > 1000
