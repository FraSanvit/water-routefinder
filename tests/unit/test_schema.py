from __future__ import annotations

import pandas as pd
import pytest

from water_routefinder.schema import (
    COLUMNS,
    VARIABLE_UNITS,
    VARIABLES,
    NetworkRef,
    Provenance,
    SidecarMeta,
    TimeCoverage,
    VariableMeta,
    coerce_dtypes,
    empty_frame,
)


def test_variables_excludes_key_columns():
    assert set(VARIABLES) == set(COLUMNS) - {"route_id", "vertex_index", "time"}
    assert len(VARIABLES) == 7


def test_variable_units_cover_every_variable():
    assert set(VARIABLE_UNITS) == set(VARIABLES)


def test_empty_frame_has_contract_columns_and_dtypes():
    df = empty_frame()
    assert list(df.columns) == list(COLUMNS)
    for col, dtype in COLUMNS.items():
        if dtype == "datetime64[ns, UTC]":
            assert str(df[col].dtype).startswith("datetime64")
        else:
            assert str(df[col].dtype) == dtype


def test_coerce_dtypes_casts_and_orders_columns():
    raw = pd.DataFrame(
        {
            "time": ["2024-01-01T00:00:00Z"],
            "vertex_index": [0],
            "route_id": ["R1"],
            "wind_speed": [1.0],
            "wind_from_direction": [0.0],
            "current_speed": [0.0],
            "current_to_direction": [0.0],
            "wave_height": [0.0],
            "wave_from_direction": [0.0],
            "wave_period": [0.0],
            "extra_column": ["dropped"],
        }
    )
    out = coerce_dtypes(raw)
    assert list(out.columns) == list(COLUMNS)
    assert "extra_column" not in out.columns
    assert out["vertex_index"].dtype == "int32"


def test_coerce_dtypes_raises_on_missing_column():
    with pytest.raises(ValueError, match="missing column"):
        coerce_dtypes(empty_frame().drop(columns=["wind_speed"]))


def test_sidecar_meta_round_trip():
    meta = SidecarMeta(
        title="t",
        network_ref=NetworkRef(routes_sha256="a" * 64, harbours_sha256="b" * 64),
        time_coverage=TimeCoverage(
            start="2024-01-01T00:00:00Z", stop="2024-01-02T00:00:00Z", step="1h"
        ),
        variables={name: VariableMeta(units=units) for name, units in VARIABLE_UNITS.items()},
        provenance=Provenance(
            sources=["mock"],
            builder="water-routefinder 0.0.0 abc123",
            created="2024-01-01T00:00:00Z",
        ),
    )
    restored = SidecarMeta.model_validate(meta.model_dump(mode="json"))
    assert restored == meta
