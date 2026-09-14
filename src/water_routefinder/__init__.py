"""water-routefinder: build the environmental-conditions bundle water-path consumes.

A Snakemake workflow harmonises met-ocean source products onto a common grid and
samples them onto vessel-route geometry, emitting the v0.2 bundle defined by
``water-path``'s ``docs/environment-data-format.md`` (mirrored here in
``docs/contract.md``).

This package holds the reusable, unit-tested core; ``workflow/`` orchestrates it.
"""

from __future__ import annotations

__version__ = "0.0.0"
