"""Diagnostic PNGs per network: the route map/conditions/data-quality plot, and a per-variable
data-availability pixel map."""


rule diagnostics:
    message:
        "Build the diagnostic plot ({wildcards.network})."
    input:
        harbours="results/{network}/network/harbours.csv",
        routes="results/{network}/network/routes.geojson",
        parquet="results/{network}/environment/conditions.parquet",
        meta="results/{network}/environment/conditions.meta.yaml",
    output:
        png="results/{network}/{network}_diag_plot.png",
    log:
        "logs/{network}/diagnostics.log",
    script:
        "../scripts/make_diag_plot.py"


rule availability:
    message:
        "Build the data-availability pixel map ({wildcards.network})."
    input:
        harbours="results/{network}/network/harbours.csv",
        routes="results/{network}/network/routes.geojson",
        # The harmonised grid, not the bundle -- this plot shows the source data's own spatial
        # footprint before route-sampling, which conditions.parquet (already interpolated onto
        # the route) can't show.
        grid="resources/automatic/{network}/grid.nc",
    output:
        png="results/{network}/{network}_availability_map.png",
    log:
        "logs/{network}/availability.log",
    script:
        "../scripts/make_availability_plot.py"
