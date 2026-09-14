# water-routefinder

Builds standardised wind, current and wave conditions along vessel routes — downloads met-ocean
data (Copernicus Marine and/or ERA5), harmonises it onto one grid, and samples it onto route
geometry into the ready-to-use bundle
[`water-path`](https://github.com/FraSanvit/water-path) consumes. A [Snakemake](https://snakemake.github.io/)
workflow, managed with [pixi](https://pixi.sh).

The workflow supports only `cmems` and `era5` for now (a later stage may add an offline mock
provider back for demos/CI) — running `run-demo` for real needs live credentials (see below).

## Quickstart

```sh
pixi install                # creates the project environment (pixi.toml)
pixi run test-unit           # offline unit + input-format tests (no credentials needed)
pixi run dry-run              # sanity-check the DAG without running anything (no credentials needed)

cp .env.example .env         # then fill in CMEMS_USERNAME/CMEMS_PASSWORD (see config/README.md
                               #   for alternatives, incl. `copernicusmarine login`)
pixi run run-demo            # builds resources/user/dublin-bay -> results/dublin-bay/
```

`run-demo` produces, from the example network under `resources/user/dublin-bay/`:

```
results/dublin-bay/
  network/{harbours.csv, routes.geojson}      # the water-path bundle
  environment/{conditions.parquet, conditions.meta.yaml}
  validation.txt                              # "OK", or the contract violations found
  dublin-bay_diag_plot.png                    # route map + conditions-over-time + data-quality panel
```

## Configuring your own network

Put a network directory under `resources/user/<name>/`:
- `routes.geojson` — a GeoJSON `FeatureCollection` of route `LineString`s (see
  `resources/user/dublin-bay/routes.geojson` for the shape).
- `harbours.csv` — `harbour_id,name,lat,lon[,country_code]`.

Then edit `config/config.yaml` (documented in `config/README.md`) — at minimum set `networks` to
your network's name and a `time` window — and run `pixi run run-demo` (or
`pixi run snakemake --snakefile workflow/Snakefile --configfile config/config.yaml --cores 1`
directly). Each variable family (current/wave/wind) picks its own provider — `cmems` (needs
`CMEMS_USERNAME`/`CMEMS_PASSWORD`) or `era5` (wind/wave only — needs a CDS API key).

## Layout

```
pixi.toml, pyproject.toml   # pixi workspace + the water_routefinder package (hatchling)
INTERFACE.yaml               # path-variable documentation
config/                      # user-editable config + its schema doc
workflow/                    # Snakefile, rules/*.smk, scripts/*.py, internal/ (schema + settings)
src/water_routefinder/       # the reusable, unit-tested core the workflow scripts call into
resources/user/              # your input networks (routes.geojson + harbours.csv)
resources/automatic/          # downloads + intermediates (safe to delete; regenerated)
results/                      # the built bundle(s) + validation report + diagnostic plot
tests/                        # unit, input-format, and end-to-end workflow tests
docs/                         # roadmap.md (design history) + contract.md (the v0.2 bundle spec)
```

See `CLAUDE.md` for the architecture in more depth and `docs/contract.md` for the bundle contract.

## Tests

```sh
pixi run test-unit             # offline: unit tests + input-format tests
pixi run test                  # same, minus any @pytest.mark.integration test
pixi run test-integration-live # needs CMEMS_USERNAME/CMEMS_PASSWORD and/or CDS API credentials
                                 #   -- includes the full end-to-end Snakemake workflow test
```

## License

Apache-2.0 — see `LICENSE`.
