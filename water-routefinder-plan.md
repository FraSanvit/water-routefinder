# water-pathfinder — development plan

> `water-pathfinder` is the sibling repository that **builds** the environmental-conditions
> bundle `water-path` consumes. It scouts what lies along the route — winds, currents, waves —
> and hands `water-path` a ready-to-use table.

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

## 3. Package layout

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
    provides: set[str]  # e.g. {"current_speed", "current_to_direction"}

    def fetch(self, bbox: BBox, start: datetime, end: datetime) -> xr.Dataset: ...


def harmonise(datasets: list[xr.Dataset], *, target_step: str = "1h") -> xr.Dataset: ...


def sample(
    grid: xr.Dataset, network: Network, *, densify_km: float | None
) -> tuple[pandas.DataFrame, Network]: ...


def write_bundle(out_dir: Path, table: DataFrame, network: Network, meta: SidecarMeta) -> None: ...
```

`BBox` is derived from the network's route geometry plus a one-cell margin.

## 5. CLI

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
| CLI | `typer` (or `click`) | |
| build | `hatchling`, `src/` layout | mirror `water-path` |

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

## 8. Testing strategy

- **Default suite is offline**: `mock` source, synthetic grids, committed golden bundle.
- **Contract test** (`test_contract_water_path.py`): `pip install water-path`, build a bundle,
  assert `waterpath.io.environment.open_conditions(bundle)` succeeds and round-trips.
- **Integration tests** (`-m integration`): real CMEMS, gated on `CMEMS_USERNAME`/`_PASSWORD`
  secrets; run nightly and on demand, not on every PR.
- **Golden-file**: small committed bundle regenerated and diffed; drift is a failing test.
- **Schema sync**: CI fetches `water-path`'s published JSON Schema and asserts `schema.py`
  matches — the two repos cannot silently diverge.

## 9. Versioning & compatibility

- `water-pathfinder` writes the `waterpath_env_schema` value it targets into every sidecar.
- `water-path` gates on the **major** of that value.
- A breaking schema change = coordinated major bump: new `water-path` `docs/environment-data-format.md`
  version + new `water-pathfinder` minor that targets it + an ADR in `water-path`.
- `water-pathfinder`'s own version is independent (feature/bugfix cadence).

## 10. Open questions

- **Regridding**: `xarray.interp` bilinear is enough for smooth met-ocean fields at these
  scales; confirm before M3. Conservative regridding (`xesmf`) only if fluxes matter.
- **Wind source**: CMEMS blended L4 vs ERA5 vs scatterometer — keep configurable; pick a
  sensible default for the Dublin-Bay example.
- **Cross-product time resolution**: waves are often 3-hourly, currents hourly — resample all
  to one step (config, default 1 h) and document the interpolation.
- **Wave parameters**: v0.2 ships `wave_period` (mean, Tm) only. Revisit once the physics
  engine specifies its added-resistance model (may want Tp or directional spread).
- **Shared schema package**: JSON Schema fetched in CI is the lightweight option now. If a
  third consumer appears, promote it to a tiny `water-path-env-schema` package both import.

## 11. First steps on repo creation

1. `hatch new water-pathfinder` (or copy `water-path`'s `pyproject.toml` skeleton), `src/` layout.
2. Port `water-path`'s `examples/demo/environment/make_demo_conditions.py` logic into
   `sources/mock.py` (it already generates a plausible synthetic field).
3. Implement `schema.py` from `docs/environment-data-format.md` v0.2 + `validate.py`.
4. Wire `harmonise` (pass-through for a single mock source) → `sample` → `bundle` → `build` CLI.
5. Add the `water-path` contract test. Green M1.
6. Delete `water-path`'s `make_demo_conditions.py`; regenerate the demo bundle with
   `water-pathfinder build --source mock` and commit it into `water-path`.
