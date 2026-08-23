#!/usr/bin/env python3
"""Draw a route map for every ride that has one, and point the ride at it.

    python scripts/render_route_maps.py --out-dir site/maps --url-prefix maps \\
        site/events.json site/events-past.json

For each ride whose first measured route carries coordinates, this fetches the
route geometry from BRouter, renders it with scripts/route_map.py, writes
``<out-dir>/<uid>.svg``, and sets the ride's ``map_image`` to the site-relative
path. The ride card prefers ``map_image`` over the Partiful poster.

Idempotent by design: a ride whose SVG already exists is skipped, so the 6-hour
sync only ever draws maps for rides it hasn't drawn yet, and re-running costs
nothing. Fail-soft everywhere — a ride with no route, no coordinates, or an
unreachable router simply keeps whatever image it had.

Exits nonzero only if a payload file is missing or unparseable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import route_map  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "site" / "maps"
DEFAULT_URL_PREFIX = "maps"
BROUTER_URL = "https://brouter.de/brouter"
BROUTER_PROFILE = "trekking"
TIMEOUT_SECONDS = 30
# UIDs become filenames, so keep them to something a URL and a filesystem can
# both hold without escaping.
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(uid: str) -> str:
    name = SAFE_NAME_RE.sub("-", str(uid or ""))
    # No separators survive the substitution above, but collapse dot runs too
    # so a ".." can never appear in a path this filename is joined into, and
    # tidy the dash runs the substitutions leave behind.
    name = re.sub(r"\.{2,}", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-.")
    return name[:80] or "ride"


def fetch_geometry(points: list) -> list:
    """The cycling route through `points` as [(lat, lon), …]. [] on failure."""
    lonlats = "|".join(f"{point[1]},{point[0]}" for point in points)
    try:
        response = requests.get(
            BROUTER_URL,
            params={
                "lonlats": lonlats,
                "profile": BROUTER_PROFILE,
                "alternativeidx": "0",
                "format": "geojson",
            },
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": "boscafebikers-sync/1.0"},
        )
        response.raise_for_status()
        coordinates = response.json()["features"][0]["geometry"]["coordinates"]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return []
    # GeoJSON is [lon, lat, elevation?]; the renderer wants (lat, lon).
    return [(point[1], point[0]) for point in coordinates if len(point) >= 2]


def mappable_route(ride: dict) -> dict | None:
    """The first route on the ride that has enough coordinates to draw."""
    for route in ride.get("routes") or []:
        if isinstance(route, dict) and len(route.get("points") or []) >= 2:
            return route
    return None


def render_for_ride(
    ride: dict, out_dir: Path, url_prefix: str, fetch=fetch_geometry
) -> str | None:
    """Draw this ride's map if it needs one. Returns the new path, or None."""
    route = mappable_route(ride)
    if route is None:
        return None
    target = out_dir / f"{safe_name(ride.get('uid'))}.svg"
    url = f"{url_prefix}/{target.name}" if url_prefix else target.name
    if target.exists():
        # Already drawn — just make sure the ride points at it.
        ride["map_image"] = url
        return None
    geometry = fetch(route["points"])
    if len(geometry) < 2:
        return None
    svg = route_map.render_route_svg(
        geometry,
        start=route.get("start", ""),
        end=route.get("end", ""),
        distance=route.get("distance_display", ""),
        title=f"{ride.get('title', 'Ride')} — route map",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")
    ride["map_image"] = url
    return url


def process(payload_path: Path, out_dir: Path, url_prefix: str, fetch=fetch_geometry) -> int:
    """Render maps for one payload file. Returns how many were drawn."""
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"render_route_maps: could not read {payload_path}: {exc}")
    events = payload.get("events")
    if not isinstance(events, list):
        raise SystemExit(f"render_route_maps: {payload_path} has no `events` list")

    before = json.dumps(payload, sort_keys=True)
    drawn = 0
    for ride in events:
        if not isinstance(ride, dict):
            continue
        if render_for_ride(ride, out_dir, url_prefix, fetch):
            drawn += 1
    after = json.dumps(payload, sort_keys=True)
    if before != after:
        payload_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return drawn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payloads", nargs="+", metavar="PAYLOAD",
                        help="events payload files to render maps for")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                        help=f"where the SVGs go (default: {DEFAULT_OUT_DIR})")
    parser.add_argument("--url-prefix", default=DEFAULT_URL_PREFIX,
                        help="path prefix written into map_image "
                             f"(default: {DEFAULT_URL_PREFIX}); must stay relative")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    total = 0
    for payload in args.payloads:
        total += process(Path(payload), out_dir, args.url_prefix.strip("/"))
    print(f"render_route_maps: drew {total} new route map(s) into {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
