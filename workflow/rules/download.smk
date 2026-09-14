"""One rule, three families: download each variable family's native data and standardise it to the
v0.2 contract's names/units/conventions. The provider (cmems/era5) is chosen per-family in
config/config.yaml.
"""


rule download:
    message:
        "Download {wildcards.family} data for {wildcards.network} (provider: "
        "{params.spec[provider]})."
    params:
        spec=lambda wc: config["sources"][wc.family],
        time=config["time"],
        cache_dir=config.get("cache_dir", "resources/automatic/.cache"),
    input:
        bbox="resources/automatic/{network}/bbox.json",
    output:
        raw="resources/automatic/{network}/raw/{family}.nc",
    log:
        "logs/{network}/download_{family}.log",
    script:
        "../scripts/download.py"
