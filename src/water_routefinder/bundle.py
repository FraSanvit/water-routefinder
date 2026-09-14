"""Write the water-path v0.2 bundle: ``network/`` + ``environment/conditions.{parquet,meta.yaml}``.

Deterministic: same inputs -> byte-identical output (fixed column order, fixed Parquet
compression, no index, sorted rows, ``yaml.safe_dump(..., sort_keys=False)`` on a model with a
fixed field order).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from water_routefinder import io as network_io
from water_routefinder.network import Network
from water_routefinder.provenance import build_sidecar_meta
from water_routefinder.schema import SidecarMeta

CONDITIONS_PARQUET = "conditions.parquet"
CONDITIONS_META = "conditions.meta.yaml"


def write_bundle(
    out_dir: str | Path,
    table: pd.DataFrame,
    network: Network,
    *,
    title: str,
    target_step: str,
    sources: list[str],
) -> SidecarMeta:
    """Write the full bundle under ``out_dir`` and return the sidecar metadata written."""
    out_dir = Path(out_dir)
    network_dir = out_dir / "network"
    environment_dir = out_dir / "environment"
    network_dir.mkdir(parents=True, exist_ok=True)
    environment_dir.mkdir(parents=True, exist_ok=True)

    harbours_path = network_dir / network_io.HARBOURS_FILE
    routes_path = network_dir / network_io.ROUTES_FILE
    network_io.write_harbours_csv(network, harbours_path)
    network_io.write_routes_geojson(network, routes_path)

    _write_parquet(table, environment_dir / CONDITIONS_PARQUET)

    meta = build_sidecar_meta(
        title=title,
        table=table,
        harbours_csv=harbours_path,
        routes_geojson=routes_path,
        target_step=target_step,
        sources=sources,
    )
    _write_meta(meta, environment_dir / CONDITIONS_META)
    return meta


def _write_parquet(table: pd.DataFrame, path: Path) -> None:
    arrow_table = pa.Table.from_pandas(table, preserve_index=False)
    pq.write_table(arrow_table, path, compression="snappy")


def _write_meta(meta: SidecarMeta, path: Path) -> None:
    # model_dump(mode="json") so date/datetime-like fields serialise as plain strings.
    doc = meta.model_dump(mode="json", exclude_none=False)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
