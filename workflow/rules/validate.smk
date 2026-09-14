"""Check the written bundle against the v0.2 contract; fail the build if it's off-spec."""


rule validate:
    message:
        "Validate the bundle against the contract ({wildcards.network})."
    input:
        harbours="results/{network}/network/harbours.csv",
        routes="results/{network}/network/routes.geojson",
        parquet="results/{network}/environment/conditions.parquet",
        meta="results/{network}/environment/conditions.meta.yaml",
    output:
        report="results/{network}/validation.txt",
    log:
        "logs/{network}/validate.log",
    script:
        "../scripts/validate_bundle.py"
