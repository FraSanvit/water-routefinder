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

## Limitations & best practices

!!! warning "Coastal/enclosed networks can come back mostly `NaN` for current and wave"
    CMEMS's global current and wave products (`cmems_mod_glo_phy_anfc_0.083deg_PT1H-m`,
    `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i`) are gridded at **~0.083° (~9 km) resolution**. Their
    ocean/wave models land-mask any grid cell too close to the coast or inside a channel/bay
    narrower than that — real examples caught while building the bundled example networks:

    - **Sherkin Island / Baltimore / Cape Clear**: routes run through channels only 1-3 km wide.
      At 9 km resolution almost every nearby grid cell was land-masked; current and wave came back
      100% `NaN` on every route.
    - **Dublin Bay**: a small, semi-enclosed bay. The *entire* bay — both routes, all three
      harbours — sat inside the land mask; current and wave were 100% `NaN`.

    **`bbox.margin_deg` can help, but only if there's nearby open water to reach.** Raising it
    (e.g. `0.1` → `0.5`) pulls more of the source grid into the fetch, giving `harmonise`'s
    bilinear interpolation valid neighbouring cells to work with — this fully recovered wind for
    both networks above, and meaningfully improved current for Sherkin Island (one route went
    from 100% to 0% `NaN`). It did **not** help Dublin Bay's current/wave at all: the route
    vertices themselves sit inside the masked interior of the bay, with no valid cell close enough
    for interpolation to reach regardless of how wide the fetch is — widening the margin only adds
    more masked or irrelevant open-ocean cells further away, none of which are the *route's own*
    neighbours.

    **Best practices:**

    - Check `results/<network>/<network>_diag_plot.png`'s "Data quality" panel (NaN fraction per
      route) after any build against a new network — don't assume coverage.
    - If NaN fraction is high, try raising `bbox.margin_deg` first — cheap to test, sometimes
      enough (see Sherkin Island above).
    - If that doesn't help, the network is likely too enclosed/narrow for this dataset's native
      resolution (Dublin Bay above) — no config value fixes that. The real fix is a
      **higher-resolution, coastal-specific gridded product** (e.g. a regional CMEMS Baltic/IBI/
      Atlantic-European-Shelf product, or a locally-forced coastal model) in place of the global
      0.083° one — a different `sources.<family>.dataset_id`, not a bigger margin.
    - Wind tends to hold up better in these cases: CMEMS's wind product
      (`cmems_obs-wind_glo_phy_my_l4_0.125deg_PT1H`) is a satellite-derived, gap-filled L4 product
      with less aggressive coastal masking than the physics/wave models.

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
