"""Offline DAG checks: one shared ``config/config.yaml`` drives every network.

There is no per-network config file, and the shipped config doesn't name a network either --
``run-network`` (and these tests) pick it with ``--config "networks=[...]"``, and with no override
every folder under ``resources/user/`` is built. Everything runs as ``snakemake -n`` (a dry run: nothing is downloaded, no credentials
needed), so unlike ``tests/integration/test_workflow.py`` this belongs to the normal test run.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from water_routefinder.config import load_config

_SINGLE = "sherkin-island"  # both are tracked example networks under resources/user/
_OTHER = "aran-islands"


def _dry_run(repo_root, *config_overrides: str) -> str:
    snakemake = shutil.which("snakemake")
    if snakemake is None:
        pytest.skip("snakemake not on PATH (run under `pixi run test`)")
    # --forceall: without it a dry run prints nothing for a network whose results are already built
    # ("Nothing to be done"), so the assertions below would depend on what's on disk -- passing on
    # a fresh CI checkout but failing on a machine that has run the workflow.
    cmd = [snakemake, "--snakefile", "workflow/Snakefile", "--cores", "1", "-n", "--forceall"]
    if config_overrides:
        cmd += ["--config", *config_overrides]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"snakemake -n exited {result.returncode}\n{output}"
    return output


def _outputs(name: str) -> list[str]:
    return [
        f"results/{name}/validation.txt",
        f"results/{name}/{name}_diag_plot.png",
        f"results/{name}/{name}_availability_map.png",
    ]


def test_networks_override_builds_only_that_network(repo_root):
    out = _dry_run(repo_root, f"networks=[{_SINGLE}]")

    for path in _outputs(_SINGLE):
        assert path in out
    assert f"results/{_OTHER}/" not in out


def test_networks_override_accepts_several_comma_separated(repo_root):
    out = _dry_run(repo_root, f"networks=[{_SINGLE},{_OTHER}]")

    for name in (_SINGLE, _OTHER):
        for path in _outputs(name):
            assert path in out


def test_no_networks_anywhere_builds_every_folder_under_resources_user(repo_root):
    # The shipped config deliberately doesn't name a network, so with no override either, every
    # folder with a routes.geojson is built (this is what `pixi run run-all` does).
    assert load_config(repo_root / "config" / "config.yaml").networks == ()
    names = sorted(p.parent.name for p in (repo_root / "resources" / "user").glob("*/routes.geojson"))
    assert _SINGLE in names and _OTHER in names  # the tracked examples, at least

    out = _dry_run(repo_root)

    for name in names:
        assert f"results/{name}/{name}_availability_map.png" in out
