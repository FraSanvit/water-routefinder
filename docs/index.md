# water-routefinder

Downloads met-ocean data (currents, waves, wind), harmonises it onto one grid, and samples it onto
vessel-route geometry — producing the environmental-conditions bundle
[`water-path`](https://github.com/FraSanvit/water-path) consumes. A
[Snakemake](https://snakemake.github.io/) workflow, managed with [pixi](https://pixi.sh).

```text
resources/user/{network}/{routes.geojson,harbours.csv}   <- your input
        |
   make_bbox -> download (cmems|era5, per family) -> harmonise -> sample -> bundle -> validate -> diagnostics
        |
results/{network}/{network,environment,validation.txt,{network}_diag_plot.png}
```

## What it produces

For every network you point it at, `water-routefinder` writes:

- `network/{harbours.csv,routes.geojson}` and `environment/{conditions.parquet,conditions.meta.yaml}`
  — the [v0.2 bundle](contract.md) `water-path` reads.
- `validation.txt` — `OK`, or every contract violation found.
- `{network}_diag_plot.png` — a route map (real coastlines, rendered fully offline), per-variable
  conditions over time, and a data-quality summary.
- `{network}_availability_map.png` — one map per variable (wind, current, wave × speed/direction)
  of the source grid's own coverage, with the route overlaid, so a route crossing a gap in the
  data is directly visible.

<figure markdown="span">
  ![Data availability map for the Rosslare–Roscoff example: time-mean wind, current and wave fields on the source grid, with the route overlaid](figures/example_route.png){ width="900" }
  <figcaption>The availability map for the Rosslare–Roscoff example. Cells the source model masks
  (land, coast) are transparent, so the coastline shows through; the dashed line is the route.
  Rendered entirely offline over a bundled Natural Earth basemap — see
  <a href="architecture/#basemap">Architecture → basemap</a>.</figcaption>
</figure>

## Where to go next

- **[Quickstart](quickstart.md)** — install, run the example, build your own network.
- **[Configuration](configuration.md)** — every `config/config.yaml` key, and how to authenticate
  with Copernicus Marine / the Climate Data Store.
- **[Architecture](architecture.md)** — how the pieces fit together, and the design conventions.
- **[Bundle contract (v0.2)](contract.md)** — the exact file format this repo produces.
- **[Roadmap](roadmap.md)** — design history and what's not built yet.

Source on GitHub: [FraSanvit/water-routefinder](https://github.com/FraSanvit/water-routefinder).
