"""Workflow configuration: ``config/config.yaml`` as a validated Python object.

``workflow/internal/config.schema.yaml`` gives Snakemake's own ``validate()`` a shape check (JSON
Schema, per the modelblocks-org data-module-template convention). This module adds the checks a
JSON Schema can't express cleanly, in particular the provider-capability rule ("ERA5 has no ocean
current product").
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

Family = Literal["current", "wave", "wind"]
#: The workflow supports only these two (live, network-hitting) sources for now. An offline mock
#: provider may return in a later stage for demos/CI; deliberately not offered today.
Provider = Literal["cmems", "era5"]

#: Which providers can supply which variable family. ERA5 is an atmospheric reanalysis — no
#: ocean-current product.
PROVIDER_CAPABILITIES: dict[Family, tuple[Provider, ...]] = {
    "current": ("cmems",),
    "wave": ("cmems", "era5"),
    "wind": ("cmems", "era5"),
}


class SourceSpec(BaseModel):
    model_config = {"frozen": True}

    provider: Provider
    #: Product dataset id for the chosen provider; ``None`` -> use the provider's default from
    #: ``workflow/internal/settings.yaml``.
    dataset_id: str | None = None
    variables: tuple[str, ...] = Field(min_length=1)


class TimeRange(BaseModel):
    model_config = {"frozen": True}

    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> TimeRange:
        if self.end <= self.start:
            raise ValueError(f"time.end ({self.end}) must be after time.start ({self.start})")
        return self


class SampleConfig(BaseModel):
    model_config = {"frozen": True}

    densify_km: float | None = Field(default=1.5, gt=0)


class HarmoniseConfig(BaseModel):
    model_config = {"frozen": True}

    target_step: str = "1h"


class BBoxConfig(BaseModel):
    model_config = {"frozen": True}

    margin_deg: float = Field(default=0.1, ge=0)


class DiagnosticsConfig(BaseModel):
    model_config = {"frozen": True}

    #: Overlay real land polygons (a bundled, offline Natural Earth extract -- no network call)
    #: behind the route map. Set False for a bare-axes plot.
    basemap: bool = True


class WorkflowConfig(BaseModel):
    """The full, validated contents of ``config/config.yaml``."""

    model_config = {"frozen": True}

    #: Subdirectories of ``resources/user/`` to build. Empty -> discover all.
    networks: tuple[str, ...] = Field(default_factory=tuple)
    time: TimeRange
    sample: SampleConfig = SampleConfig()
    harmonise: HarmoniseConfig = HarmoniseConfig()
    bbox: BBoxConfig = BBoxConfig()
    diagnostics: DiagnosticsConfig = DiagnosticsConfig()
    cache_dir: str = "resources/automatic/.cache"
    sources: dict[Family, SourceSpec]

    @model_validator(mode="after")
    def _provider_capabilities(self) -> WorkflowConfig:
        missing = [f for f in ("current", "wave", "wind") if f not in self.sources]
        if missing:
            raise ValueError(f"config.sources is missing famil(y/ies): {', '.join(missing)}")
        for family, spec in self.sources.items():
            allowed = PROVIDER_CAPABILITIES[family]
            if spec.provider not in allowed:
                raise ValueError(
                    f"config.sources.{family}.provider={spec.provider!r} is not supported; "
                    f"{family} accepts one of {allowed}"
                )
        return self


def load_config(path: str | Path) -> WorkflowConfig:
    """Load and validate ``config/config.yaml`` (or an equivalent file)."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return WorkflowConfig.model_validate(raw)
