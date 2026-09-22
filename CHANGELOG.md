# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- Initial repository: pixi-managed Snakemake workflow that downloads (CMEMS and/or ERA5 — the
  only two supported sources for now), harmonises, and samples met-ocean conditions onto route
  geometry, emitting the `water-path` v0.2 environmental-conditions bundle.
- `resources/user/dublin-bay` example network.
- Per-network diagnostic plot (`{network}_diag_plot.png`).
- `pixi run run-network <name>[,<name>...]` / `dry-run-network` / `run-all` / `dry-run-all`: build
  any network(s) with the one shared `config/config.yaml`, which no longer names a network (the
  tasks add `networks` via `--config`; with none, every folder under `resources/user/` is built).
  The per-network example configs were removed.
- The route `n_segments` property is no longer read, written or shipped (it was a `water-path`
  setting this repo never used, and `water-path`'s spec no longer includes it). Any such property
  in an input `routes.geojson` is simply ignored; the golden test bundle was regenerated without it.
- Per-network data-availability pixel map (`{network}_availability_map.png`): the harmonised
  grid's own spatial coverage for wind/current/wave (speed + direction), before route-sampling,
  with the routes overlaid so a masked grid cell along a route is directly visible.
- Unit and input-format tests (offline); credential-gated CMEMS/ERA5/end-to-end workflow
  integration tests.
