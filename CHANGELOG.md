# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- Initial repository: pixi-managed Snakemake workflow that downloads (CMEMS and/or ERA5 — the
  only two supported sources for now), harmonises, and samples met-ocean conditions onto route
  geometry, emitting the `water-path` v0.2 environmental-conditions bundle.
- `resources/user/dublin-bay` example network.
- Per-network diagnostic plot (`{network}_diag_plot.png`).
- Per-network data-availability pixel map (`{network}_availability_map.png`): the harmonised
  grid's own spatial coverage for wind/current/wave (speed + direction), before route-sampling,
  with the routes overlaid so a masked grid cell along a route is directly visible.
- Unit and input-format tests (offline); credential-gated CMEMS/ERA5/end-to-end workflow
  integration tests.
