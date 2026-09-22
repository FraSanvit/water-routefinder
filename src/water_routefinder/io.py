"""Read/write a network from/to prepared local files.

Vendored from ``water-path``'s ``src/waterpath/io/routes.py`` (same file layout, same
``harbours.csv`` / ``routes.geojson`` shapes) plus a writer, since this repo may densify routes
and must re-emit ``routes.geojson`` per the v0.2 contract.

Expected layout (file names overridable)::

    <network_dir>/
        harbours.csv      # harbour_id,name,lat,lon[,country_code]
        routes.geojson     # FeatureCollection of LineStrings

``routes.geojson`` follows GeoJSON's ``(lon, lat)`` coordinate order; each feature::

    {
      "type": "Feature",
      "properties": {"route_id": "R1", "origin": "H1", "destination": "H2", "name": "optional"},
      "geometry": {"type": "LineString", "coordinates": [[lon, lat], ...]}
    }

Any other feature property is ignored on read and not written back.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pydantic import ValidationError

from water_routefinder.network import Harbour, Network, Point, Route

HARBOURS_FILE = "harbours.csv"
ROUTES_FILE = "routes.geojson"

_HARBOUR_REQUIRED = ("harbour_id", "name", "lat", "lon")
_ROUTE_REQUIRED = ("route_id", "origin", "destination")
_HARBOUR_FIELDS = ("harbour_id", "name", "lat", "lon", "country_code")


class NetworkInputError(ValueError):
    """Raised when network input files are missing, malformed, or inconsistent."""


def load_network(
    network_dir: str | Path,
    *,
    harbours_file: str = HARBOURS_FILE,
    routes_file: str = ROUTES_FILE,
) -> Network:
    """Load and validate the network under ``network_dir``."""
    network_dir = Path(network_dir)
    harbours = _load_harbours(network_dir / harbours_file)
    routes = _load_routes(network_dir / routes_file)
    try:
        return Network(harbours=tuple(harbours), routes=tuple(routes))
    except ValidationError as exc:
        raise NetworkInputError(f"invalid network in {network_dir}:\n{exc}") from exc


def write_harbours_csv(network: Network, path: str | Path) -> None:
    """Write ``harbours.csv`` for ``network`` (stable column order)."""
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as fh:
        # lineterminator="\n": deliberately not RFC 4180's "\r\n" default -- this file's bytes
        # get sha256'd into the bundle's network_ref (provenance.py) and must be identical
        # regardless of the OS that built the bundle (see write_routes_geojson's `newline="\n"`
        # for the same reasoning).
        writer = csv.DictWriter(fh, fieldnames=_HARBOUR_FIELDS, lineterminator="\n")
        writer.writeheader()
        for h in network.harbours:
            writer.writerow(
                {
                    "harbour_id": h.harbour_id,
                    "name": h.name,
                    "lat": h.lat,
                    "lon": h.lon,
                    "country_code": h.country_code or "",
                }
            )


def write_routes_geojson(network: Network, path: str | Path) -> None:
    """Write ``routes.geojson`` for ``network`` (deterministic key order, GeoJSON lon/lat)."""
    path = Path(path)
    features = []
    for r in network.routes:
        properties: dict[str, object] = {
            "route_id": r.route_id,
            "origin": r.origin,
            "destination": r.destination,
        }
        if r.name is not None:
            properties["name"] = r.name
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p.lon, p.lat] for p in r.path],
                },
            }
        )
    doc = {"type": "FeatureCollection", "features": features}
    # newline="\n": Path.write_text's default translates "\n" to the platform line separator
    # (\r\n on Windows) -- this file's bytes get sha256'd into the bundle's network_ref
    # (provenance.py) and must be identical regardless of the OS that built the bundle.
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")


def _load_harbours(path: Path) -> list[Harbour]:
    if not path.is_file():
        raise NetworkInputError(f"harbours file not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        missing = [c for c in _HARBOUR_REQUIRED if c not in fields]
        if missing:
            raise NetworkInputError(f"{path}: missing required column(s): {', '.join(missing)}")

        harbours: list[Harbour] = []
        for lineno, row in enumerate(reader, start=2):
            try:
                harbours.append(
                    Harbour(
                        harbour_id=(row["harbour_id"] or "").strip(),
                        name=(row["name"] or "").strip(),
                        lat=_as_float(row["lat"], path, lineno, "lat"),
                        lon=_as_float(row["lon"], path, lineno, "lon"),
                        country_code=(row.get("country_code") or "").strip() or None,
                    )
                )
            except ValidationError as exc:
                raise NetworkInputError(f"{path} line {lineno}: {exc}") from exc

    if not harbours:
        raise NetworkInputError(f"{path}: no harbour rows")
    return harbours


def _load_routes(path: Path) -> list[Route]:
    if not path.is_file():
        raise NetworkInputError(f"routes file not found: {path}")

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise NetworkInputError(f"{path}: invalid JSON: {exc}") from exc

    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        raise NetworkInputError(f"{path}: expected a GeoJSON FeatureCollection")

    features = doc.get("features")
    if not isinstance(features, list) or not features:
        raise NetworkInputError(f"{path}: FeatureCollection has no features")

    routes: list[Route] = []
    for i, feature in enumerate(features):
        where = f"{path} feature {i}"
        if not isinstance(feature, dict):
            raise NetworkInputError(f"{where}: not an object")

        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "LineString":
            raise NetworkInputError(f"{where}: geometry must be a LineString")

        coords = geometry.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            raise NetworkInputError(f"{where}: LineString needs >= 2 coordinates")

        props = feature.get("properties") or {}
        missing = [k for k in _ROUTE_REQUIRED if not props.get(k)]
        if missing:
            raise NetworkInputError(
                f"{where}: missing required propert(y/ies): {', '.join(missing)}"
            )

        try:
            path_points = tuple(
                Point(lat=_coord(c, where, 1), lon=_coord(c, where, 0)) for c in coords
            )
            routes.append(
                Route(
                    route_id=str(props["route_id"]),
                    origin=str(props["origin"]),
                    destination=str(props["destination"]),
                    path=path_points,
                    name=(str(props["name"]) if props.get("name") else None),
                )
            )
        except ValidationError as exc:
            raise NetworkInputError(f"{where}: {exc}") from exc

    return routes


def _as_float(value: str, path: Path, lineno: int, column: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise NetworkInputError(
            f"{path} line {lineno}: column {column!r} is not a number: {value!r}"
        ) from None


def _coord(pair: object, where: str, index: int) -> float:
    if not isinstance(pair, (list, tuple)) or len(pair) < 2:
        raise NetworkInputError(f"{where}: coordinate is not a [lon, lat] pair: {pair!r}")
    try:
        return float(pair[index])
    except (TypeError, ValueError):
        raise NetworkInputError(f"{where}: non-numeric coordinate: {pair!r}") from None
