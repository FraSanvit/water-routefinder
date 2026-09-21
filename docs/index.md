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

<figure markdown>
![Example diagnostic plot: a route map over real coastlines, with harbours marked](figures/example_route.png)
<figcaption>The route-map panel of a diagnostic plot, generated entirely offline from a bundled
Natural Earth extract — see <a href="architecture/#basemap">Architecture → basemap</a>.</figcaption>
</figure>

## Where to go next

- **[Quickstart](quickstart.md)** — install, run the example, build your own network.
- **[Configuration](configuration.md)** — every `config/config.yaml` key, and how to authenticate
  with Copernicus Marine / the Climate Data Store.
- **[Architecture](architecture.md)** — how the pieces fit together, and the design conventions.
- **[Bundle contract (v0.2)](contract.md)** — the exact file format this repo produces.
- **[Roadmap](roadmap.md)** — design history and what's not built yet.

Source on GitHub: [FraSanvit/water-routefinder](https://github.com/FraSanvit/water-routefinder).
