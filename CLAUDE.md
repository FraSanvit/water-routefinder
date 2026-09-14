# water-routefinder

## What this is

The sibling repository that **builds** the environmental-conditions bundle
[`water-path`](../water-path) consumes: it reads a route network (harbours + `routes.geojson`),
downloads the met-ocean products that cover it (Copernicus Marine and/or ERA5 — the only two
supported sources for now, see below), harmonises them onto one grid/cadence, samples that grid
onto the route geometry, and writes the bundle `water-path` `docs/environment-data-format.md` v0.2
defines. `water-path` never sees a grid — see
`../water-path/docs/adr/0001-environment-conditions-format.md` for why.

**No optimisation, physics, or vessel/consumption modelling here** — that's `water-path`'s job.
This repo does not depend on the `water-path` package (unpublished; its reader is still v0.1
NetCDF) — `src/water_routefinder/network.py` + `io.py` vendor a minimal `Network` model and
loader, kept in sync by hand with `water-path`'s `schemas/network.py` / `io/routes.py`.

## Architecture

```
resources/user/{network}/{routes.geojson,harbours.csv}   <- your input
        |
   make_bbox -> download (cmems|era5, per family) -> harmonise -> sample -> bundle -> validate -> diagnostics
        |
results/{network}/{network,environment,validation.txt,{network}_diag_plot.png}
```

Snakemake (`workflow/Snakefile` + `workflow/rules/*.smk`) orchestrates; the actual logic lives in
the plain, unit-tested `src/water_routefinder/` package — `workflow/scripts/*.py` are thin
adapters that unpack `snakemake.input/output/params/wildcards` and call the package. This keeps
the core testable without invoking Snakemake, while still getting its DAG/caching/parallelism for
orchestration (real wins here: CMEMS downloads are slow and credential-gated, so re-running
`harmonise`/`sample` while iterating doesn't re-hit the network).

Directory conventions follow
[`modelblocks-org/data-module-template`](https://github.com/modelblocks-org/data-module-template):
`resources/user/` (your input) vs `resources/automatic/` (downloads/intermediates, safe to delete)
vs `results/` (output); `config/` (user-editable, schema-validated) vs `workflow/internal/`
(non-user-editable settings — provider capability matrix, default dataset ids). One departure from
that template: it builds *embeddable modules* whose `rule all` refuses to run standalone;
`water-routefinder` is a standalone deliverable, so `rule all` actually builds the bundle(s).

The v0.2 contract (bundle layout, column schema, sidecar shape, direction conventions) is
`water_routefinder/schema.py` in code and `docs/contract.md` in prose (frozen copy of
`../water-path/docs/environment-data-format.md`). `validate.py` (+ `workflow/rules/validate.smk`)
is the real check today — no `water-path`-side contract test yet, since `water-path`'s own reader
hasn't been ported to v0.2 (see `docs/roadmap.md`'s status note).

## Dev environment

Unlike `water-path` (whose `CLAUDE.md` documents a Windows app-control policy that blocks
executing `python.exe` from venv-like locations, forcing a `uv --target` + `PYTHONPATH`
workaround), **`pixi` runs fine on this machine** — its conda-forge-managed interpreter under
`.pixi/envs/` executes without issue. Use pixi directly:

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

If `pixi run ...` ever *is* blocked on a locked-down machine, fall back to `water-path`'s pattern:
`uv pip install --python <uv-managed interpreter> --target <dir>` + `PYTHONPATH=<dir>;src`, then
run the base interpreter directly. Prefer the PowerShell tool for anything that executes Python on
Windows.

## Conventions

- `src/` layout, **hatchling** build backend, wrapped by **pixi** (`pixi.toml` — the canonical
  environment/task definition; `pyproject.toml` keeps the package pip-installable standalone).
  Import package `water_routefinder`.
- **pydantic** for config/input validation (`config.py`, `network.py`, `schema.py`).
- `xarray.Dataset` is the interchange format for met-ocean grids; `pandas.DataFrame` for the
  sampled table.
- Every source provider (`sources/cmems.py`, `era5.py` — the only two supported for now; see
  `config.PROVIDER_CAPABILITIES`) returns data already in the v0.2 standard names/units/
  conventions — the per-provider transform lives with the provider, not downstream in
  `harmonise`/`sample`. There is no offline mock provider (removed; may return in a later stage).
- `tests/unit/` mirrors `src/water_routefinder/` roughly 1:1, using a test-only synthetic dataset
  builder (`tests/_synthetic.py` — not part of the package or reachable from config) so
  `harmonise`/`sample`/`bundle` stay unit-testable without live credentials.
  `tests/test_input_format.py` tests network-file shape validation specifically.
  `tests/integration/test_workflow.py` runs the real Snakemake DAG against live CMEMS and is
  `@pytest.mark.integration`, credential-gated, like `test_cmems_integration.py` /
  `test_era5_integration.py` — none of the three run on every PR.

## Current state

| Area | Status |
|---|---|
| `network.py`/`io.py`/`geo.py` — vendored `Network` model + loader + geodesic helpers | done |
| `schema.py`/`config.py` — v0.2 contract as code + validated workflow config | done |
| `sources/{cmems,era5}.py` + `cache.py` | done — CMEMS default dataset ids verified against the live catalogue via `copernicusmarine.describe()` (no credentials needed for that); ERA5 defaults not yet independently checked against a CDS equivalent |
| `harmonise.py`/`sample.py`/`bundle.py`/`provenance.py`/`validate.py`/`diagnostics.py` | done |
| `workflow/` (Snakefile, rules, scripts) + `config/` | done — DAG verified with `dry-run`; the live `cmems` build has not been run here (no credentials in this environment) |
| Tests (unit, input-format, credential-gated CMEMS/ERA5/workflow integration) | done — unit suite offline via `tests/_synthetic.py`; integration tests not executed here (no credentials) |
| `water-path`-side v0.2 reader + contract test | not started — other repo, out of scope here |
| M3-M6 (harmonisation robustness/property tests, geometry edge cases, full reproducibility, release docs) | not started |
