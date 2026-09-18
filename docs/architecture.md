# Architecture

## What this is

The sibling repository that **builds** the environmental-conditions bundle
[`water-path`](https://github.com/FraSanvit/water-path) consumes: it reads a route network
(harbours + `routes.geojson`), downloads the met-ocean products that cover it, harmonises them
onto one grid/cadence, samples that grid onto the route geometry, and writes the bundle
`water-path`'s `docs/environment-data-format.md` v0.2 defines. `water-path` never sees a grid —
see its `docs/adr/0001-environment-conditions-format.md` for why.

**No optimisation, physics, or vessel/consumption modelling here** — that's `water-path`'s job.
This repo does not depend on the `water-path` package (unpublished; its own reader still reads
the older v0.1 NetCDF format) — `src/water_routefinder/network.py` + `io.py` vendor a minimal
`Network` model and loader, kept in sync by hand with `water-path`'s `schemas/network.py` /
`io/routes.py`.

## The pipeline

```text
resources/user/{network}/{routes.geojson,harbours.csv}   <- your input
        |
   make_bbox -> download (cmems|era5, per family) -> harmonise -> sample -> bundle -> validate
        |                                               |                    |
        |                                               |                    +-> diagnostics
        |                                               +------------------------> availability
        |
results/{network}/{network,environment,validation.txt,{network}_diag_plot.png,{network}_availability_map.png}
```

`diagnostics` and `availability` are two independent leaves, not a chain: `diagnostics` reads the
finished bundle (route-sampled values); `availability` reads the harmonised *grid* directly,
skipping `sample`/`bundle`, so it can show the source data's own spatial coverage rather than
what got interpolated onto the route.

Snakemake (`workflow/Snakefile` + `workflow/rules/*.smk`) orchestrates; the actual logic lives in
the plain, unit-tested `src/water_routefinder/` package — `workflow/scripts/*.py` are thin
adapters that unpack `snakemake.input/output/params/wildcards` and call the package. That keeps
the core testable without invoking Snakemake, while still getting its DAG/caching/parallelism for
orchestration — the real win: CMEMS downloads are slow and credential-gated, so re-running
`harmonise`/`sample` while iterating doesn't re-hit the network.

Directory conventions follow
[`modelblocks-org/data-module-template`](https://github.com/modelblocks-org/data-module-template):
`resources/user/` (your input) vs `resources/automatic/` (downloads/intermediates, safe to delete)
vs `results/` (output); `config/` (user-editable, schema-validated) vs `workflow/internal/`
(non-user-editable settings — provider capability matrix, default dataset ids). One departure from
that template: it builds *embeddable modules* whose `rule all` refuses to run standalone;
`water-routefinder` is a standalone deliverable, so `rule all` actually builds the bundle(s). This
workflow's structure is built on that template's rationale, and on the Snakemake data-module
practice of [irm-codebase](https://github.com/irm-codebase).

## The bundle contract

The [v0.2 contract](contract.md) (bundle layout, column schema, sidecar shape, direction
conventions) is `water_routefinder/schema.py` in code and [contract.md](contract.md) in prose (a
frozen copy of `water-path`'s `docs/environment-data-format.md`). `validate.py` (+
`workflow/rules/validate.smk`) is the real check today — there's no `water-path`-side contract
test yet, since `water-path`'s own reader hasn't been ported to v0.2 (see the
[roadmap](roadmap.md)'s status note).

## Network validation

Every route's path must start and end close to its origin/destination harbour: `network.py`'s
`PATH_ENDPOINT_TOLERANCE_KM = 2.0` — `Network._cross_check()` rejects the whole network otherwise,
with a clear error naming the offending route and the actual gap in km. Harbour ids referenced by
a route but not defined, duplicate harbour/route ids, and malformed GeoJSON/CSV are all rejected
the same way, at load time, before anything is fetched.

## Basemap

The diagnostic plot's route-map panel draws real coastlines from a bundled, offline
[Natural Earth](https://www.naturalearthdata.com/) 1:10m land extract
(`resources/basemap/europe_land_10m.parquet`, clipped to Europe + the North Atlantic approaches) —
not a live web-tile fetch. That was the first design (via `contextily`), and it turned out to be a
bad trade for a diagnostic plot: checked directly against three tile providers, fetch times ranged
from acceptable to tens of seconds per tile depending on network conditions, one provider now
requires an API key everywhere (including its formerly-free endpoint), and another blocks
unidentified automated clients outright. A bundled static file has none of that — no network call,
no timeout, no rate limit, no ToS, and it's faster besides. Set `diagnostics.basemap: false` in
`config/config.yaml` for a bare-axes plot instead.

## Dependencies & sources

Every source provider (`sources/cmems.py`, `sources/era5.py` — the only two supported for now; see
`config.PROVIDER_CAPABILITIES`) returns data already in the v0.2 standard names/units/conventions —
the per-provider transform lives with the provider, not downstream in `harmonise`/`sample`. There
is no offline mock provider (removed; may return in a later stage for demos/CI that don't need
live credentials).

## Conventions

- `src/` layout, **hatchling** build backend, wrapped by **pixi** (`pixi.toml` — the canonical
  environment/task definition; `pyproject.toml` keeps the package pip-installable standalone).
  Import package `water_routefinder`.
- **pydantic** for config/input validation (`config.py`, `network.py`, `schema.py`).
- `xarray.Dataset` is the interchange format for met-ocean grids; `pandas.DataFrame` for the
  sampled table.
- `tests/unit/` mirrors `src/water_routefinder/` roughly 1:1, using a test-only synthetic dataset
  builder (`tests/_synthetic.py` — not part of the package or reachable from config) so
  `harmonise`/`sample`/`bundle` stay unit-testable without live credentials.
  `tests/test_input_format.py` tests network-file shape validation specifically.
  `tests/integration/test_workflow.py` runs the real Snakemake DAG against live CMEMS and is
  `@pytest.mark.integration`, credential-gated, like `test_cmems_integration.py` /
  `test_era5_integration.py` — none of the three run on every PR.

## Development

```sh
pixi install
pixi run test-unit             # offline unit + input-format tests
pixi run test                   # same, minus any @pytest.mark.integration test
pixi run dry-run                 # sanity-check the DAG, no credentials needed
pixi run lint

export CMEMS_USERNAME=... CMEMS_PASSWORD=...
pixi run run-demo               # build resources/user/dublin-bay -> results/dublin-bay/ (live CMEMS)
pixi run test-integration-live  # + the end-to-end workflow test
```

`snakemake` ships from **bioconda**, not conda-forge alone — `pixi.toml`'s `channels` must include
both, or `snakemake-minimal` resolves to nothing.
