# Quickstart

## Install

```sh
pixi install
```

Creates the project environment from `pixi.toml` — Snakemake, the `water_routefinder` package,
and every runtime dependency (`geopandas`, `xarray`, `pyproj`, ...) in one place. See
[pixi.sh](https://pixi.sh) if you don't have `pixi` yet.

## Try it offline first

```sh
pixi run test-unit   # offline unit + input-format tests, no credentials needed
pixi run dry-run       # sanity-check the DAG without running anything, no credentials needed
```

## Authenticate

The workflow supports two live, network-hitting sources — `cmems` (Copernicus Marine) and `era5`
(Copernicus Climate Data Store) — and both need a free account. Simplest path:

```sh
cp .env.example .env   # then fill in CMEMS_USERNAME/CMEMS_PASSWORD
```

See [Configuration → Credentials](configuration.md#credentials) for the other two ways to
authenticate (`copernicusmarine login`, or real environment variables for CI), and why
`copernicusmarine login` is the one that never puts your password in any file in this repo.

## Build the example network

```sh
pixi run run-demo
```

Builds `resources/user/dublin-bay/` end to end and writes:

```text
results/dublin-bay/
  network/{harbours.csv, routes.geojson}
  environment/{conditions.parquet, conditions.meta.yaml}
  validation.txt
  dublin-bay_diag_plot.png
  dublin-bay_availability_map.png
```

## Build your own network

Put a network directory under `resources/user/<name>/`:

- **`routes.geojson`** — a GeoJSON `FeatureCollection` of route `LineString`s (see
  `resources/user/dublin-bay/routes.geojson` for the exact shape: `route_id`, `origin`,
  `destination` properties per feature).
- **`harbours.csv`** — `harbour_id,name,lat,lon[,country_code]`.

Every route's path must start and end within 2 km of its origin/destination harbour, or the whole
network is rejected with a clear error — see [Architecture](architecture.md#network-validation).

There is **one** configuration file, `config/config.yaml`, and it applies to every network — you
don't write a config per network. Set the `time` window (and anything else) there once, then pick
which network to build:

```sh
pixi run run-network my-network                  # build resources/user/my-network/
pixi run run-network my-network,another-network  # or several at once, same config
pixi run dry-run-network my-network              # just print the plan: no download, no credentials
```

(`config/config.yaml` doesn't name a network, so you never edit it to switch networks.
`pixi run run-demo` builds the shipped example, `dublin-bay`; `pixi run run-all` builds every
folder under `resources/user/`.) See [Configuration](configuration.md) for every key, including
per-family provider choice (`cmems`/`era5`) and the diagnostic plot's basemap toggle.

## Run the tests

```sh
pixi run test-unit             # offline: unit tests + input-format tests
pixi run test                  # same, minus any @pytest.mark.integration test
pixi run test-integration-live # needs credentials -- includes the full live-CMEMS workflow test
```
