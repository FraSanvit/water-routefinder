"""Compute each network's bounding box (+ margin), used by every download rule."""


rule make_bbox:
    message:
        "Compute the bounding box for {wildcards.network}."
    input:
        harbours="resources/user/{network}/harbours.csv",
        routes="resources/user/{network}/routes.geojson",
    output:
        bbox="resources/automatic/{network}/bbox.json",
    log:
        "logs/{network}/make_bbox.log",
    script:
        "../scripts/make_bbox.py"
