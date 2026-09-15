# Configuring a build

`config/config.yaml` is the only file you normally need to edit. It's validated against
[`workflow/internal/config.schema.yaml`](https://github.com/FraSanvit/water-routefinder/blob/main/workflow/internal/config.schema.yaml)
(shape/types) and against
[`water_routefinder.config.WorkflowConfig`](https://github.com/FraSanvit/water-routefinder/blob/main/src/water_routefinder/config.py)
(cross-field rules, e.g. which provider can supply which variable family).

| key | meaning |
|---|---|
| `networks` | Which `resources/user/<name>/` directories to build. Omit or leave empty to build every network found there. |
| `time.start` / `time.end` | The window to fetch/build, as `YYYY-MM-DD`. `end` is exclusive. |
| `sample.densify_km` | Target spacing (km) to densify each route to before sampling, so bilinear interpolation is fine enough. `null` disables densification (samples exactly the input vertices). |
| `harmonise.target_step` | Common time step after harmonisation, e.g. `"1h"`, `"3h"`. |
| `bbox.margin_deg` | Degrees of padding added around the network's own extent before fetching source data. |
| `cache_dir` | Where downloaded source subsets are cached, keyed by (provider, dataset, variables, bbox, time span). |
| `diagnostics.basemap` | Overlay real land polygons behind the route map in `{network}_diag_plot.png` — a bundled, offline Natural Earth extract (`resources/basemap/`), no network call. Default `true`; set `false` for a bare-axes plot. |
| `sources.<current\|wave\|wind>.provider` | The workflow supports only two, live, network-hitting sources for now: `cmems` (Copernicus Marine — needs `CMEMS_USERNAME`/`CMEMS_PASSWORD`) or `era5` (Copernicus Climate Data Store — needs a `~/.cdsapirc` or `CDSAPI_URL`/`CDSAPI_KEY`). **`era5` is not valid for `current`** — ERA5 has no ocean-current product. |
| `sources.<family>.dataset_id` | The provider's product id. `null` uses the default in `workflow/internal/settings.yaml`. |
| `sources.<family>.variables` | The provider's native variable names to request (each provider's source module converts them to the standard names in the [bundle contract](contract.md)). |

## Multiple networks / providers per family

`provider` is chosen independently per family, so e.g. wind can come from ERA5 while current and
wave come from CMEMS. `networks` can list several route sets — each gets its own
`results/<network>/` bundle and diagnostic plot, built in parallel where the DAG allows it.

## Credentials

Three ways to authenticate, in order of preference:

1. **`copernicusmarine login`** (recommended) — run it once, interactively; it writes
   `~/.copernicusmarine-credentials` in your home directory. Nothing to configure in this repo,
   and your password never touches any file here. Similarly, for ERA5, `cdsapi` picks up a
   `~/.cdsapirc` file automatically if you've set one up — see
   [cds.climate.copernicus.eu/how-to-api](https://cds.climate.copernicus.eu/how-to-api).
2. **A local `.env` file** — `cp .env.example .env`, fill in the values, save. It's gitignored
   (never commit it) and is loaded automatically by the Snakemake workflow
   (`workflow/Snakefile`) and by the test suite (`tests/conftest.py`).
3. **Real environment variables** — e.g. CI secrets (`CMEMS_USERNAME`, `CMEMS_PASSWORD`,
   `CDSAPI_URL`, `CDSAPI_KEY`; see `.github/workflows/integration.yml`).

Whichever you use, treat the account as sensitive: don't paste the password into a chat, commit
it, or put it anywhere other than `.env` (gitignored) or your own shell/CI secrets.

## Example configuration

```yaml
networks: ["dublin-bay"]

time:
  start: "2024-01-01"
  end: "2024-01-08" # exclusive -- 7 days, hourly

sample:
  densify_km: 1.5

harmonise:
  target_step: "1h"

bbox:
  margin_deg: 0.1

cache_dir: "resources/automatic/.cache"

sources:
  current: { provider: cmems, dataset_id: null, variables: [uo, vo] }
  wave: { provider: cmems, dataset_id: null, variables: [VHM0, VMDR, VTM10] }
  wind: { provider: cmems, dataset_id: null, variables: [eastward_wind, northward_wind] }
```
