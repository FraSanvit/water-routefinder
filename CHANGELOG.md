# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- Initial repository: pixi-managed Snakemake workflow that downloads (CMEMS and/or ERA5 — the
  only two supported sources for now), harmonises, and samples met-ocean conditions onto route
  geometry, emitting the `water-path` v0.2 environmental-conditions bundle.
- `resources/user/dublin-bay` example network.
- Per-network diagnostic plot (`{network}_diag_plot.png`).
- Unit and input-format tests (offline); credential-gated CMEMS/ERA5/end-to-end workflow
  integration tests.
