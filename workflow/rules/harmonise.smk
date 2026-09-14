"""Regrid + time-align the three downloaded families onto one common grid."""


rule harmonise:
    message:
        "Harmonise current/wave/wind onto one grid ({wildcards.network})."
    params:
        target_step=config.get("harmonise", {}).get("target_step", "1h"),
    input:
        current="resources/automatic/{network}/raw/current.nc",
        wave="resources/automatic/{network}/raw/wave.nc",
        wind="resources/automatic/{network}/raw/wind.nc",
    output:
        grid="resources/automatic/{network}/grid.nc",
    log:
        "logs/{network}/harmonise.log",
    script:
        "../scripts/harmonise.py"
