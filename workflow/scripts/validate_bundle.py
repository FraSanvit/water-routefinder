"""Snakemake script for rule `validate`: check the bundle, fail the build if it's off-spec."""

from pathlib import Path

from water_routefinder.validate import validate_bundle

bundle_dir = Path(snakemake.input.parquet).parent.parent  # noqa: F821  (results/{network})
violations = validate_bundle(bundle_dir)

report = "\n".join(violations) + "\n" if violations else "OK\n"
Path(snakemake.output.report).write_text(report)  # noqa: F821

if violations:
    raise SystemExit(
        f"{bundle_dir}: bundle failed validation ({len(violations)} issue(s)):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
