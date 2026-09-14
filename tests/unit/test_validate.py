from __future__ import annotations

import shutil

import pandas as pd
import yaml

from water_routefinder.validate import validate_bundle


def _copy_bundle(expected_bundle_dir, tmp_path):
    dest = tmp_path / "bundle"
    shutil.copytree(expected_bundle_dir, dest)
    return dest


def test_golden_bundle_is_valid(expected_bundle_dir):
    assert validate_bundle(expected_bundle_dir) == []


def test_missing_file_is_a_violation(expected_bundle_dir, tmp_path):
    bundle = _copy_bundle(expected_bundle_dir, tmp_path)
    (bundle / "environment" / "conditions.meta.yaml").unlink()
    violations = validate_bundle(bundle)
    assert any("missing required file" in v for v in violations)


def test_missing_column_is_a_violation(expected_bundle_dir, tmp_path):
    bundle = _copy_bundle(expected_bundle_dir, tmp_path)
    parquet = bundle / "environment" / "conditions.parquet"
    table = pd.read_parquet(parquet).drop(columns=["wind_speed"])
    table.to_parquet(parquet, index=False)
    violations = validate_bundle(bundle)
    assert any("wind_speed" in v for v in violations)


def test_non_contiguous_vertex_index_is_a_violation(expected_bundle_dir, tmp_path):
    bundle = _copy_bundle(expected_bundle_dir, tmp_path)
    parquet = bundle / "environment" / "conditions.parquet"
    table = pd.read_parquet(parquet)
    table.loc[table.index[0], "vertex_index"] = 999
    table.to_parquet(parquet, index=False)
    violations = validate_bundle(bundle)
    assert any("vertex_index" in v for v in violations)


def test_wrong_sidecar_units_is_a_violation(expected_bundle_dir, tmp_path):
    bundle = _copy_bundle(expected_bundle_dir, tmp_path)
    meta_path = bundle / "environment" / "conditions.meta.yaml"
    meta = yaml.safe_load(meta_path.read_text())
    meta["variables"]["wind_speed"]["units"] = "knots"
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
    violations = validate_bundle(bundle)
    assert any("wind_speed" in v and "units" in v for v in violations)


def test_bad_network_ref_hash_is_a_violation(expected_bundle_dir, tmp_path):
    bundle = _copy_bundle(expected_bundle_dir, tmp_path)
    meta_path = bundle / "environment" / "conditions.meta.yaml"
    meta = yaml.safe_load(meta_path.read_text())
    meta["network_ref"]["routes_sha256"] = "0" * 64
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
    violations = validate_bundle(bundle)
    assert any("network_ref" in v for v in violations)


def test_wrong_schema_major_is_a_violation(expected_bundle_dir, tmp_path):
    bundle = _copy_bundle(expected_bundle_dir, tmp_path)
    meta_path = bundle / "environment" / "conditions.meta.yaml"
    meta = yaml.safe_load(meta_path.read_text())
    meta["waterpath_env_schema"] = "1.0"
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
    violations = validate_bundle(bundle)
    assert any("waterpath_env_schema" in v for v in violations)
