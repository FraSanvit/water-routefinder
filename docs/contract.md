# Environmental conditions — format spec (v0.2), frozen copy

> Vendored from `water-path`'s `docs/environment-data-format.md` v0.2, for reference without
> checking out the other repo. **`water-path`'s copy is authoritative** — if the two disagree,
> `water-path`'s wins, and this file is stale (there's no CI schema-sync yet; see
> `docs/roadmap.md` §8). `water_routefinder.schema` is this repo's code-level mirror; `validate.py`
> checks bundles against it.

`water-path` does **not** download or derive environmental conditions. `water-routefinder`
produces a standardised bundle; `water-path` only reads it.

## Bundle layout

```
<study>/
  network/
    harbours.csv           # pass-through from the input network
    routes.geojson         # pass-through; MAY be densified by water-routefinder
  environment/
    conditions.parquet     # primary; conditions.csv also accepted
    conditions.meta.yaml   # sidecar: units, CRS, conventions, provenance, schema version
```

## Sample-point model

Conditions are provided **at the vertices of each route's `LineString` path** in
`routes.geojson`. Point identity is shared with the network file, so it cannot drift spatially.

- `water-routefinder` MAY densify a route's geometry before sampling (recommended vertex spacing
  ≈ 1–2 km for environmental fidelity — `config.sample.densify_km`). If it does, it writes the
  **updated `routes.geojson`** into `network/`.
- `water-path` derives `s_along_m` (cumulative along-track distance, origin → destination) from
  the geometry itself — it is **not** a column in `conditions.parquet`.

## Table — `conditions.parquet` (or `conditions.csv`)

One row per `(route_id, vertex_index, time)`. Wide form, one column per variable.

| column | dtype | units | notes |
|---|---|---|---|
| `route_id` | string | — | must match a `route_id` in `routes.geojson` |
| `vertex_index` | int32 | — | 0-based, contiguous, ordered origin → destination |
| `time` | timestamp, UTC | — | ISO-8601; strictly increasing; uniform step |
| `wind_speed` | float32 | `m s-1` | wind speed at 10 m |
| `wind_from_direction` | float32 | `degree` | direction the wind blows **from** |
| `current_speed` | float32 | `m s-1` | surface current speed |
| `current_to_direction` | float32 | `degree` | direction the current flows **towards** |
| `wave_height` | float32 | `m` | significant wave height, Hs |
| `wave_from_direction` | float32 | `degree` | mean direction waves propagate **from** |
| `wave_period` | float32 | `s` | mean wave period, Tm |

- `NaN` is permitted. `water-path` raises if a `(route_id, vertex_index, time)` it actually needs
  is absent or `NaN`.
- Rows sorted by `route_id, vertex_index, time`.

### Direction convention

Degrees in `[0, 360)`, clockwise from true north (0 = N, 90 = E).

- **wind**, **waves** use `from` (meteorological; matches Copernicus `VMDR`, ERA5 wind dir).
- **current** uses `to` (oceanographic; matches how `uo` / `vo` resolve).

## Sidecar — `conditions.meta.yaml`

```yaml
waterpath_env_schema: "0.2"          # semver; major bump = breaking change
crs: "EPSG:4326"
title: "Environmental conditions — <network>"
network_ref:                          # what this bundle was built against
  routes_sha256: "<hex of network/routes.geojson>"
  harbours_sha256: "<hex of network/harbours.csv>"
time_coverage: { start: "...", stop: "...", step: "PT1H" }
variables:                            # units asserted here, checked on read
  wind_speed: { units: "m s-1" }
  wind_from_direction: { units: "degree", convention: "from" }
  current_speed: { units: "m s-1" }
  current_to_direction: { units: "degree", convention: "to" }
  wave_height: { units: "m" }
  wave_from_direction: { units: "degree", convention: "from" }
  wave_period: { units: "s" }
provenance:
  sources: ["current:cmems", "wave:cmems", "wind:era5"]
  builder: "water-routefinder <version> <git sha>"
  created: "<ISO-8601 UTC>"
```

## Validation on read (`water-path`, and this repo's own `validate_bundle`)

- every `route_id` in `routes.geojson` appears in the table;
- per route, `vertex_index` is `0 … k-1` contiguous and `k` equals the path vertex count;
- `time` is uniform and strictly increasing;
- sidecar `variables[*].units` match the table's expected units;
- `waterpath_env_schema` major version equals the reader's;
- `network_ref` hashes match the bundled `network/` files.
