"""The water-path v0.2 environmental-conditions contract, as code.

Mirrors ``../water-path/docs/environment-data-format.md`` v0.2 (frozen copy: ``docs/contract.md``).
This is the single source of truth other modules import from — ``bundle.py`` writes to it,
``validate.py`` checks against it, ``sample.py`` builds a table shaped like it.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

#: Bump the major when the on-disk contract changes incompatibly.
SCHEMA_VERSION = "0.2"

#: Column name -> pandas dtype for ``conditions.parquet`` / ``conditions.csv``.
COLUMNS: dict[str, str] = {
    "route_id": "string",
    "vertex_index": "int32",
    "time": "datetime64[ns, UTC]",
    "wind_speed": "float32",
    "wind_from_direction": "float32",
    "current_speed": "float32",
    "current_to_direction": "float32",
    "wave_height": "float32",
    "wave_from_direction": "float32",
    "wave_period": "float32",
}

#: The 7 environmental variables (excludes the 3 key columns).
VARIABLES: tuple[str, ...] = tuple(c for c in COLUMNS if c not in ("route_id", "vertex_index", "time"))

#: Variable -> expected units, per the contract table.
VARIABLE_UNITS: dict[str, str] = {
    "wind_speed": "m s-1",
    "wind_from_direction": "degree",
    "current_speed": "m s-1",
    "current_to_direction": "degree",
    "wave_height": "m",
    "wave_from_direction": "degree",
    "wave_period": "s",
}

#: Direction convention per family: the "from"/"to" split mirrors the source products.
CONVENTIONS: dict[str, Literal["from", "to"]] = {
    "wind": "from",
    "wave": "from",
    "current": "to",
}


class NetworkRef(BaseModel):
    """Hashes tying a bundle to the exact ``network/`` files it was built against."""

    routes_sha256: str
    harbours_sha256: str


class TimeCoverage(BaseModel):
    start: str
    stop: str
    step: str


class VariableMeta(BaseModel):
    units: str
    convention: str | None = None


class Provenance(BaseModel):
    sources: list[str] = Field(default_factory=list)
    builder: str
    created: str


class SidecarMeta(BaseModel):
    """``conditions.meta.yaml`` — units, CRS, conventions, provenance, schema version."""

    waterpath_env_schema: str = SCHEMA_VERSION
    crs: str = "EPSG:4326"
    title: str
    network_ref: NetworkRef
    time_coverage: TimeCoverage
    variables: dict[str, VariableMeta]
    provenance: Provenance


def empty_frame() -> pd.DataFrame:
    """An empty, correctly-typed ``conditions`` table."""
    return coerce_dtypes(pd.DataFrame({c: pd.Series(dtype=object) for c in COLUMNS}))


def coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Cast every contract column to its declared dtype (order preserved, extra columns dropped)."""
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"table is missing column(s): {', '.join(missing)}")
    out = df[list(COLUMNS)].copy()
    for col, dtype in COLUMNS.items():
        if dtype == "datetime64[ns, UTC]":
            out[col] = pd.to_datetime(out[col], utc=True)
        else:
            out[col] = out[col].astype(dtype)
    return out
