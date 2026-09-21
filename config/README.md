# Configuring a build

`config/config.yaml` is the only file you normally need to edit. It's validated against
[`workflow/internal/config.schema.yaml`](../workflow/internal/config.schema.yaml) (shape/types) and
against [`water_routefinder.config.WorkflowConfig`](../src/water_routefinder/config.py)
(cross-field rules, e.g. which provider can supply which variable family).

| key | meaning |
|---|---|
| `networks` | *Not set in the shipped file* — which network(s) to build is chosen per run (see below). If set (or empty/omitted) it lists the `resources/user/<name>/` directories to build; omitted means every one found there. |
| `time.start` / `time.end` | The window to fetch/build, as `YYYY-MM-DD`. `end` is exclusive. |
| `sample.densify_km` | Target spacing (km) to densify each route to before sampling, so bilinear interpolation is fine enough. `null` disables densification (samples exactly the input vertices). |
| `harmonise.target_step` | Common time step after harmonisation, e.g. `"1h"`, `"3h"`. |
| `bbox.margin_deg` | Degrees of padding added around the network's own extent before fetching source data. |
| `cache_dir` | Where downloaded source subsets are cached, keyed by (provider, dataset, variables, bbox, time span). |
| `diagnostics.basemap` | Overlay real land polygons behind the route map in `{network}_diag_plot.png` — a bundled, offline Natural Earth extract (`resources/basemap/`), no network call. Default `true`; set `false` for a bare-axes plot. |
| `sources.<current\|wave\|wind>.provider` | The workflow supports only two, live, network-hitting sources for now: `cmems` (Copernicus Marine — needs `CMEMS_USERNAME`/`CMEMS_PASSWORD`) or `era5` (Copernicus Climate Data Store — needs a `~/.cdsapirc` or `CDSAPI_URL`/`CDSAPI_KEY`). **`era5` is not valid for `current`** — ERA5 has no ocean-current product. (An offline mock provider may return in a later stage for demos/CI.) |
| `sources.<family>.dataset_id` | The provider's product id. `null` uses the default in `workflow/internal/settings.yaml`. |
| `sources.<family>.variables` | The provider's native variable names to request (each provider's source module converts them to the standard names in `docs/contract.md`). |

## One config, many networks

`config.yaml` is the single configuration for every network — there are no per-network config
files, and it doesn't name a network either. Everything in it (time window, densification, bbox
margin, providers, datasets) applies to each network you build; which network(s) to build is a
command-line choice:

```sh
pixi run run-network sherkin-island                # one network
pixi run run-network sherkin-island,aran-islands   # several, built in parallel where the DAG allows
pixi run run-demo                                  # the shipped example, dublin-bay
pixi run run-all                                   # every folder under resources/user/
pixi run dry-run-network sherkin-island            # print the plan only (no download, no credentials)
pixi run dry-run-all                               # ...for every network
```

`run-network`/`run-demo` run `snakemake --snakefile workflow/Snakefile --cores 1 --config
"networks=[...]"`: the Snakefile always loads `config/config.yaml`, and `--config` adds just the
`networks` key. `run-all` passes none, which means every folder under `resources/user/` with a
`routes.geojson`. (`--config` is only dependable for top-level keys like `networks`; to change a
nested setting such as `bbox.margin_deg`, edit `config.yaml`.) See
[docs/configuration.md](../docs/configuration.md) for the trade-off this implies.

## Multiple providers per family

`provider` is chosen independently per family, so e.g. wind can come from ERA5 while current and
wave come from CMEMS. When several networks are built in one run, each gets its own
`results/<network>/` bundle and diagnostic plots.

## Credentials

Three ways to authenticate, in order of preference:

1. **`copernicusmarine login`** (recommended) — run it once, interactively; it writes
   `~/.copernicusmarine-credentials` in your home directory. Nothing to configure in this repo,
   and your password never touches any file here. Similarly, for ERA5, `cdsapi` picks up a
   `~/.cdsapirc` file automatically if you've set one up (see
   https://cds.climate.copernicus.eu/how-to-api).
2. **A local `.env` file** — `cp .env.example .env`, fill in the values, save. It's gitignored
   (never commit it) and is loaded automatically by the Snakemake workflow
   (`workflow/Snakefile`) and by the test suite (`tests/conftest.py`).
3. **Real environment variables** — e.g. CI secrets (`CMEMS_USERNAME`, `CMEMS_PASSWORD`,
   `CDSAPI_URL`, `CDSAPI_KEY`; see `.github/workflows/integration.yml`).

Whichever you use, treat the account as sensitive: don't paste the password into a chat, commit
it, or put it anywhere other than `.env` (gitignored) or your own shell/CI secrets.
