# water-routefinder — development plan

> **Status note (implementation, 2026-09):** the original design below (drafted while this repo
> still lived as `water-path/docs/water-pathfinder-plan.md`) is preserved as historical context —
> most of it still holds. What actually shipped diverges in a few places the plan didn't
> anticipate:
>
> - **Naming**: package `water_routefinder` / CLI-less, not `water_pathfinder` — matches this
>   repo's actual name and GitHub remote (`FraSanvit/water-routefinder`).
> - **Delivery shape**: a **Snakemake workflow** (`workflow/Snakefile`), not a `typer` CLI. The
>   `build`/`validate`/`inspect` commands in §5 below became Snakemake rules
>   (`workflow/rules/*.smk`) driving the same underlying package functions.
> - **Environment/tooling**: **`pixi`** (`pixi.toml`/`pixi.lock`), not `uv`/hatchling-only. `hatchling`
>   still builds the `water_routefinder` package itself; pixi wraps it with the runtime/dev
>   environment and task runner (`pixi run test`, `pixi run run-demo`, ...).
> - **Repository conventions**: adopted from
>   [`modelblocks-org/data-module-template`](https://github.com/modelblocks-org/data-module-template) —
>   `resources/user/` (input) vs `resources/automatic/` (downloads/intermediates) vs `results/`
>   (output), `INTERFACE.yaml`, a `config/` (user-editable, schema-validated) vs
>   `workflow/internal/` (non-user-editable settings) split. One deliberate departure from that
>   template: it builds *embeddable modules* whose `rule all` refuses to run standalone;
>   `water-routefinder` is a standalone deliverable, so `rule all` actually builds the bundle(s).
> - **Multi-provider downloads**: ERA5 (§10's "keep configurable") shipped as a real provider
>   (`sources/era5.py`, wind + wave only — no ocean-current product), not just CMEMS, chosen
>   independently per variable family in `config/config.yaml`.
> - **Contract test deferred, not dropped**: `test_contract_water_path.py` (§7 M1, §8) is not yet
>   written — `water-path` itself still only reads the old v0.1 NetCDF format (its
>   `io/environment.py` needs a v0.2 Parquet port first; tracked as a follow-up in that repo, out
>   of scope here). This repo's own `validate.py` (+ `workflow/rules/validate.smk`) is the real
>   contract check for now, and there's no dependency on the `water-path` package (`Network` +
>   geometry helpers are vendored — see `src/water_routefinder/network.py`).
> - **Added, not in the original plan**: a per-network diagnostic plot
>   (`results/{network}/{network}_diag_plot.png` — route map, per-variable conditions over time,
>   data-quality panel) and a dedicated input-format test suite
>   (`tests/test_input_format.py`), both requested during implementation planning.
> - **No offline mock provider**: `sources/mock.py` (§3, §7 M1's `mock` source) was removed —
>   for now the workflow supports only `cmems` and `era5` (a later stage may bring an offline
>   provider back for demos/CI). This means `config/config.yaml`'s shipped example, `pixi run
>   run-demo`, and the full `tests/integration/test_workflow.py` all need live CMEMS credentials
>   now; the offline unit suite (`pixi run test-unit`) still runs without any, using a small
>   test-only synthetic-dataset helper (`tests/_synthetic.py`, not part of the package or
>   reachable from config) instead of a real provider.
>
> See `docs/contract.md` for the frozen v0.2 bundle contract this repo targets, and
> `CLAUDE.md`/`README.md` for the as-built architecture and usage.

---

> `water-pathfinder` is the sibling repository that **builds** the environmental-conditions
> bundle `water-path` consumes. It scouts what lies along the route — winds, currents, waves —
> and hands `water-path` a ready-to-use table.
>
> This plan currently lives in the `water-path` repo because `water-pathfinder` does not exist
> yet. On creation, move it to `water-pathfinder/docs/roadmap.md` and keep only a one-line
> pointer here.

## 1. Purpose & scope

**In scope**
- Pull met-ocean source products (Copernicus Marine primary; ERA5 / Marine Institute optional).
- Harmonise them onto one standardised grid / cadence / convention set.
- Sample that field **onto the route geometry** of a `water-path` network.
- Emit the bundle defined by `water-path` `docs/environment-data-format.md` **v0.2**:
  `network/` (pass-through, possibly densified) + `environment/conditions.parquet` +
  `environment/conditions.meta.yaml`.

**Out of scope**
- Any optimisation, physics, or vessel modelling — that is `water-path`.
- Serving grids to `water-path` (the harmonised grid stays internal; see ADR-0001).

**Contract direction**: `water-pathfinder` depends on `water-path`'s *published schema*
(the spec doc + a JSON Schema), never on `water-path` code. `water-path` depends on neither.

## 2. Architecture — two stages

```
sources/*  --fetch-->  [ harmonise ]  --regional grid-->  [ sample ]  --table-->  bundle
 (CMEMS,                 regrid + time-align +              bilinear onto
  ERA5, …)               unify conventions + masks          route vertices
```

1. **`harmonise`** — network-agnostic, independently testable. The reusable core (the
   `atlite`-cutout equivalent). Output: an in-memory `xarray.Dataset` regional grid, standard
   variable names & units.
2. **`sample`** — takes the grid + a `water-path` `Network`; may densify route geometry to a
   target vertex spacing; interpolates to every route vertex at every timestep; computes
   `s_along_m`; returns `(table: DataFrame, network: Network)` (network possibly densified).

## 3. Package layout (original plan — superseded by the as-built layout in README.md / CLAUDE.md)

```
src/water_pathfinder/
  config.py            # pydantic: sources, time range, densify target, output options
  schema.py            # the v0.2 contract as code — column set, dtypes, units, sidecar model
                       #   (mirrors water-path; verified against its JSON Schema in CI)
  sources/
    base.py            # SourceProvider ABC: fetch(bbox, start, end) -> xr.Dataset
    mock.py            # deterministic synthetic field, offline — default for tests & demo
    cmems_phy.py       # surface currents (uo, vo)            via `copernicusmarine`
    cmems_wav.py       # waves (VHM0, VMDR, VTM10)            via `copernicusmarine`
    cmems_wind.py      # 10 m wind (eastward_wind, northward_wind)
    era5.py            # optional fallback                    via `cdsapi`
  harmonise.py         # regrid to common grid + resample time + convention/unit unification
  sample.py            # densify geometry, bilinear grid->vertices, along-track distance
  bundle.py            # assemble & write network/ + conditions.parquet + conditions.meta.yaml
  provenance.py        # source dataset ids + versions + access time; network_ref hashing
  validate.py          # check a bundle against schema.py (reused by the CLI and CI)
  viz.py               # `inspect` quicklook: ranges, gaps, per-route field plots
  cli.py               # build / validate / inspect
tests/
  test_schema.py  test_sample.py  test_harmonise.py  test_bundle.py
  test_sources_mock.py
  test_cmems_integration.py        # @pytest.mark.integration, needs credentials, skipped in CI
  test_contract_water_path.py      # installs water-path, runs open_conditions() on our output
docs/
examples/dublin-bay/               # network + a committed demo bundle (mock source)
```

## 4. Key interfaces

```python
class SourceProvider(ABC):
    """One met-ocean product family, returned on its native grid with standard names/units."""
    name: str
    provides: set[str]                      # e.g. {"current_speed", "current_to_direction"}
    def fetch(self, bbox: BBox, start: datetime, end: datetime) -> xr.Dataset: ...

def harmonise(datasets: list[xr.Dataset], *, target_step: str = "1h") -> xr.Dataset: ...

def sample(grid: xr.Dataset, network: Network, *, densify_km: float | None) \
        -> tuple[pandas.DataFrame, Network]: ...

def write_bundle(out_dir: Path, table: DataFrame, network: Network, meta: SidecarMeta) -> None: ...
```

`BBox` is derived from the network's route geometry plus a one-cell margin.

## 5. CLI (original plan — shipped as a Snakemake workflow instead; see README.md)

```
water-pathfinder build  NETWORK_DIR --start DATE --end DATE
                        [--config cfg.yaml] [--out DIR] [--densify-km 1.5]
                        [--source cmems|era5|mock]        # default: from config
water-pathfinder validate  BUNDLE_DIR      # exits non-zero on any schema violation
water-pathfinder inspect   BUNDLE_DIR      # human summary + quicklook plots
```

Config file (YAML):

```yaml
sources:
  current: { dataset_id: "cmems_mod_glo_phy_anfc_0.083deg_PT1H-m", variables: [uo, vo] }
  wave:    { dataset_id: "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i", variables: [VHM0, VMDR, VTM10] }
  wind:    { dataset_id: "cmems_obs-wind_glo_phy_my_l4_...",        variables: [eastward_wind, northward_wind] }
time:   { start: 2024-01-01, end: 2024-12-31 }
sample: { densify_km: 1.5 }
```

## 6. Dependencies

| need | choice | note |
|---|---|---|
| CMEMS access | `copernicusmarine` | official client; token auth |
| ERA5 (optional) | `cdsapi` | behind an extra |
| arrays / IO | `xarray`, `numpy`, `netcdf4` (or `h5netcdf`) | internal grid handling |
| regridding | **`xarray.Dataset.interp` (bilinear)** to start | avoids the `xesmf`/ESMF conda dependency; revisit if conservative regridding is needed |
| geometry | `pyproj` (geodesic densification + distance) | `water-path` uses haversine; `pyproj` is more accurate for this step |
| table out | `pyarrow` | Parquet |
| config / sidecar | `pydantic`, `pyyaml` | |
| CLI | `typer` (or `click`) | superseded — Snakemake is the interface |
| build | `hatchling`, `src/` layout | mirror `water-path`; wrapped by `pixi` |

## 7. Milestones

| # | Deliverable | Exit criterion |
|---|---|---|
| **M0** | Repo skeleton, CI, `schema.py`, `validate.py`, `config.py` | `validate` runs; schema round-trips; CI green |
| **M1** | `mock` source + `harmonise` + `sample` + `bundle` + `build` CLI | `water-pathfinder build examples/dublin-bay --source mock` produces a bundle that passes **`water-path`'s** `open_conditions()` (contract test). Replaces `water-path`'s `make_demo_conditions.py`. |
| **M2** | Real CMEMS sources (phy / wav / wind), auth, bbox-from-network, response caching | integration test builds a 3-day Dublin-Bay bundle from live CMEMS (credential-gated) |
| **M3** | Harmonisation robustness: common grid, time resample, land-mask & gap policy, unit assertions, NaN policy | property tests on synthetic multi-grid inputs; documented policies |
| **M4** | Geometry: densify-to-spacing, along-track distance, re-emit `routes.geojson`; degenerate-route handling | `sample` tests incl. short / 2-vertex / already-dense routes |
| **M5** | Provenance & reproducibility: full `meta.yaml`, `network_ref` hashes, deterministic output, `--dry-run` | byte-identical re-run; provenance lists dataset ids + versions + access date |
| **M6** | Docs + first tagged release | README, usage guide, contract reference, `examples/dublin-bay`; version policy tied to `waterpath_env_schema` |

**As-built status**: M0–M2 are implemented (mock + CMEMS + ERA5 sources, Snakemake `build`/
`validate`/diagnostics rules, `resources/user/dublin-bay` example, unit + input-format +
end-to-end workflow tests, credential-gated integration tests). M3–M6 remain open — see
"Out of scope / follow-ups" in the implementation plan history, or open an issue.

## 8. Testing strategy

- **Default suite is offline**: `mock` source, synthetic grids, committed golden bundle
  (`tests/integration/expected/`).
- **Contract test** (`test_contract_water_path.py`): not yet added — `water-path` needs a v0.2
  reader first (see the status note at the top of this file). `validate_bundle()` +
  `workflow/rules/validate.smk` are the real contract check today.
- **Integration tests** (`-m integration`): real CMEMS/ERA5, gated on `CMEMS_USERNAME`/`_PASSWORD`
  or CDS credentials; run nightly and on demand, not on every PR.
- **Golden-file**: small committed bundle regenerated and diffed; drift is a failing test
  (`tests/integration/test_workflow.py`).
- **Schema sync**: not yet added (no published `water-path` JSON Schema yet) — left as a `TODO`
  in `.github/workflows/ci.yml`.

## 9. Versioning & compatibility

- `water-pathfinder` writes the `waterpath_env_schema` value it targets into every sidecar.
- `water-path` gates on the **major** of that value.
- A breaking schema change = coordinated major bump: new `water-path` `docs/environment-data-format.md`
  version + new `water-pathfinder` minor that targets it + an ADR in `water-path`.
- `water-pathfinder`'s own version is independent (feature/bugfix cadence).

## 10. Open questions

- **Regridding**: `xarray.interp` bilinear is enough for smooth met-ocean fields at these
  scales; confirm before M3. Conservative regridding (`xesmf`) only if fluxes matter.
- **Wind source**: CMEMS blended L4 vs ERA5 vs scatterometer — kept configurable per family in
  `config/config.yaml` (shipped); the Dublin-Bay example defaults to `mock`.
- **Cross-product time resolution**: waves are often 3-hourly, currents hourly — resample all
  to one step (config, default 1 h) and document the interpolation.
- **Wave parameters**: v0.2 ships `wave_period` (mean, Tm) only. Revisit once the physics
  engine specifies its added-resistance model (may want Tp or directional spread).
- **Shared schema package**: JSON Schema fetched in CI is the lightweight option now. If a
  third consumer appears, promote it to a tiny `water-path-env-schema` package both import.

## 11. First steps on repo creation (original plan — see the status note above for what actually happened)

1. `hatch new water-pathfinder` (or copy `water-path`'s `pyproject.toml` skeleton), `src/` layout.
2. Port `water-path`'s `examples/demo/environment/make_demo_conditions.py` logic into
   `sources/mock.py` (it already generates a plausible synthetic field).
3. Implement `schema.py` from `docs/environment-data-format.md` v0.2 + `validate.py`.
4. Wire `harmonise` (pass-through for a single mock source) → `sample` → `bundle` → `build` CLI.
5. Add the `water-path` contract test. Green M1.
6. Delete `water-path`'s `make_demo_conditions.py`; regenerate the demo bundle with
   `water-pathfinder build --source mock` and commit it into `water-path`.

**Not yet done** (tracked as follow-ups, in `water-path` unless noted): step 5 (contract test —
blocked on `water-path`'s v0.2 reader) and step 6 (touches the other repo).
