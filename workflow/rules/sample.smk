"""Densify route geometry (if configured) and bilinear-sample the grid onto every vertex."""


rule sample:
    message:
        "Sample the grid onto route vertices ({wildcards.network})."
    params:
        densify_km=config.get("sample", {}).get("densify_km"),
    input:
        grid="resources/automatic/{network}/grid.nc",
        harbours="resources/user/{network}/harbours.csv",
        routes="resources/user/{network}/routes.geojson",
    output:
        table="resources/automatic/{network}/table.parquet",
        harbours="resources/automatic/{network}/densified/harbours.csv",
        routes="resources/automatic/{network}/densified/routes.geojson",
    log:
        "logs/{network}/sample.log",
    script:
        "../scripts/sample.py"
