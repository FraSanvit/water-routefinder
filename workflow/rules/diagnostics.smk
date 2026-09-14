"""One overview PNG per network: the route map, conditions over time, and a data-quality panel."""


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
