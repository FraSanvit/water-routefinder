"""Assemble the water-path v0.2 bundle: network/ pass-through (densified) + environment/*."""


rule bundle:
    message:
        "Assemble the bundle ({wildcards.network})."
    params:
        title=lambda wc: f"Environmental conditions - {wc.network}",
        target_step=config.get("harmonise", {}).get("target_step", "1h"),
        sources=lambda wc: [
            f"{family}:{config['sources'][family]['provider']}"
            for family in ("current", "wave", "wind")
        ],
    input:
        table="resources/automatic/{network}/table.parquet",
        harbours="resources/automatic/{network}/densified/harbours.csv",
        routes="resources/automatic/{network}/densified/routes.geojson",
    output:
        harbours="results/{network}/network/harbours.csv",
        routes="results/{network}/network/routes.geojson",
        parquet="results/{network}/environment/conditions.parquet",
        meta="results/{network}/environment/conditions.meta.yaml",
    log:
        "logs/{network}/bundle.log",
    script:
        "../scripts/write_bundle.py"
