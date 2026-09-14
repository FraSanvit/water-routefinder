"""Shared setup: cross-validate config, discover which networks to build."""

from water_routefinder.config import WorkflowConfig

# Re-validates the merged `config` dict beyond what the JSON Schema can express (e.g. the
# provider-capability rule: ERA5 has no ocean-current product) -- fails fast, before any rule runs.
WORKFLOW_CONFIG = WorkflowConfig.model_validate(config)

wildcard_constraints:
    network=r"[^/]+",
    family="current|wave|wind",


if WORKFLOW_CONFIG.networks:
    NETWORKS = list(WORKFLOW_CONFIG.networks)
else:
    NETWORKS = sorted(set(glob_wildcards("resources/user/{network}/routes.geojson").network))

if not NETWORKS:
    raise ValueError(
        "no networks to build: put routes.geojson + harbours.csv under "
        "resources/user/<name>/, or set config.networks"
    )
