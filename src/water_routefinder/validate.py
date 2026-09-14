"""Check a written bundle against the v0.2 contract.

The real check for now (``water-path`` itself still reads the old v0.1 format — see
docs/roadmap.md), reused by ``workflow/rules/validate.smk`` and the test suite.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from water_routefinder.bundle import CONDITIONS_META, CONDITIONS_PARQUET
from water_routefinder.io import NetworkInputError, load_network
from water_routefinder.provenance import sha256_file
from water_routefinder.schema import COLUMNS, SCHEMA_VERSION, VARIABLE_UNITS, SidecarMeta


def validate_bundle(bundle_dir: str | Path) -> list[str]:
    """Return a list of contract violations; ``[]`` means the bundle is valid."""
    bundle_dir = Path(bundle_dir)
    violations: list[str] = []

    network_dir = bundle_dir / "network"
    environment_dir = bundle_dir / "environment"
    parquet_path = environment_dir / CONDITIONS_PARQUET
    meta_path = environment_dir / CONDITIONS_META

    for label, path in (
        ("network/harbours.csv", network_dir / "harbours.csv"),
        ("network/routes.geojson", network_dir / "routes.geojson"),
        (f"environment/{CONDITIONS_PARQUET}", parquet_path),
        (f"environment/{CONDITIONS_META}", meta_path),
    ):
        if not path.is_file():
            violations.append(f"missing required file: {label}")
    if violations:
        return violations

    try:
        network = load_network(network_dir)
    except NetworkInputError as exc:
        return [f"network/ failed to load: {exc}"]

    table = pd.read_parquet(parquet_path)
    missing_cols = [c for c in COLUMNS if c not in table.columns]
    if missing_cols:
        violations.append(f"conditions table missing column(s): {', '.join(missing_cols)}")
        return violations

    try:
        meta = SidecarMeta.model_validate(yaml.safe_load(meta_path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001 - surfaced as a violation, not a crash
        return [f"conditions.meta.yaml is invalid: {exc}"]

    violations += _check_dtypes(table)
    violations += _check_row_identity(table, network)
    violations += _check_time(table)
    violations += _check_sidecar(meta, network_dir)
    return violations


def _check_dtypes(table: pd.DataFrame) -> list[str]:
    out = []
    for col, dtype in COLUMNS.items():
        got = table[col].dtype
        if dtype == "datetime64[ns, UTC]":
            # Any time resolution is fine (Parquet round-trips as us/ns depending on the
            # writer); what matters is "datetime64, UTC-aware".
            tz = getattr(got, "tz", None)
            if not pd.api.types.is_datetime64_any_dtype(got) or str(tz) != "UTC":
                out.append(f"column {col!r} is not UTC datetime64 (got {got})")
        elif str(got) != dtype:
            out.append(f"column {col!r} has dtype {got}, expected {dtype}")
    return out


def _check_row_identity(table: pd.DataFrame, network) -> list[str]:
    out = []
    dupes = table.duplicated(subset=["route_id", "vertex_index", "time"]).sum()
    if dupes:
        out.append(f"{dupes} duplicate (route_id, vertex_index, time) row(s)")

    table_route_ids = set(table["route_id"].unique())
    network_route_ids = {r.route_id for r in network.routes}
    missing = network_route_ids - table_route_ids
    if missing:
        out.append(f"route_id(s) in network but absent from table: {sorted(missing)}")

    for route in network.routes:
        sub = table.loc[table["route_id"] == route.route_id, "vertex_index"]
        if sub.empty:
            continue
        expected = np.arange(len(route.path), dtype="int32")
        got = np.sort(sub.unique())
        if len(got) != len(route.path) or not np.array_equal(got, expected):
            out.append(
                f"route {route.route_id!r}: vertex_index is not contiguous 0..{len(route.path) - 1} "
                f"(path has {len(route.path)} vertices, table has {len(sub.unique())} distinct index(es))"
            )
    return out


def _check_time(table: pd.DataFrame) -> list[str]:
    out = []
    times = pd.DatetimeIndex(pd.to_datetime(table["time"])).unique().sort_values()
    if len(times) < 2:
        return out
    diffs = times.to_series().diff().dropna()
    if not (diffs > pd.Timedelta(0)).all():
        out.append("time is not strictly increasing")
    if diffs.nunique() > 1:
        out.append("time is not uniformly spaced across the table")
    return out


def _check_sidecar(meta: SidecarMeta, network_dir: Path) -> list[str]:
    out = []
    if meta.waterpath_env_schema.split(".")[0] != SCHEMA_VERSION.split(".")[0]:
        out.append(
            f"waterpath_env_schema {meta.waterpath_env_schema!r} has a different major version "
            f"than this validator's {SCHEMA_VERSION!r}"
        )
    for name, expected_units in VARIABLE_UNITS.items():
        vm = meta.variables.get(name)
        if vm is None:
            out.append(f"conditions.meta.yaml: variables is missing {name!r}")
        elif vm.units != expected_units:
            out.append(
                f"conditions.meta.yaml: {name} units {vm.units!r} != expected {expected_units!r}"
            )

    routes_hash = sha256_file(network_dir / "routes.geojson")
    harbours_hash = sha256_file(network_dir / "harbours.csv")
    if meta.network_ref.routes_sha256 != routes_hash:
        out.append("network_ref.routes_sha256 does not match network/routes.geojson")
    if meta.network_ref.harbours_sha256 != harbours_hash:
        out.append("network_ref.harbours_sha256 does not match network/harbours.csv")
    return out
