"""Sidecar provenance: file hashes, builder identity, source dataset ids."""

from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from water_routefinder import __version__
from water_routefinder.schema import (
    CONVENTIONS,
    VARIABLE_UNITS,
    NetworkRef,
    Provenance,
    SidecarMeta,
    TimeCoverage,
    VariableMeta,
)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def builder_string() -> str:
    """``"water-routefinder <version> <git-sha>"``; sha falls back to ``"unknown"``."""
    sha = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            sha = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return f"water-routefinder {__version__} {sha}"


def created_timestamp() -> str:
    """UTC now, ISO-8601; overridable via ``SOURCE_DATE_EPOCH`` for reproducible builds."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        dt = datetime.fromtimestamp(int(epoch), tz=UTC)
    else:
        dt = datetime.now(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def build_sidecar_meta(
    *,
    title: str,
    table: pd.DataFrame,
    harbours_csv: str | Path,
    routes_geojson: str | Path,
    target_step: str,
    sources: list[str],
) -> SidecarMeta:
    """Assemble the ``conditions.meta.yaml`` contents for a just-written bundle.

    ``harbours_csv``/``routes_geojson`` must be the files as actually written to
    ``network/`` (hashed in place, after any densification).
    """
    time = pd.to_datetime(table["time"], utc=True)
    variables = {
        name: VariableMeta(
            units=units,
            convention=CONVENTIONS.get(name.split("_")[0]) if name.endswith("_direction") else None,
        )
        for name, units in VARIABLE_UNITS.items()
    }
    return SidecarMeta(
        title=title,
        network_ref=NetworkRef(
            routes_sha256=sha256_file(routes_geojson),
            harbours_sha256=sha256_file(harbours_csv),
        ),
        time_coverage=TimeCoverage(
            start=time.min().isoformat(),
            stop=time.max().isoformat(),
            step=target_step,
        ),
        variables=variables,
        provenance=Provenance(sources=sources, builder=builder_string(), created=created_timestamp()),
    )
