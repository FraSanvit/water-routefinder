"""Per-provider met-ocean data sources.

The workflow supports only ``cmems`` and ``era5`` for now (a later stage may add an offline mock
provider back for demos/CI). Each provider module exposes a ``fetch(...)`` that returns an
``xarray.Dataset`` already in the v0.2 contract's standard variable names, units and direction
conventions (see ``water_routefinder.schema``) — the provider-specific transform lives with the
provider, not downstream.
"""
