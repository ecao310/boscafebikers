#!/usr/bin/env python3
"""Render a ride's route as a small self-contained SVG map.

Why a drawn map and not a screenshot of Google Maps: there is no browser in the
sync (so nothing to screenshot with), Google's Static Maps API needs a billed
key, and hotlinking a public OSM static-map service from a live site would
point every visitor's browser at someone else's tile server. Embedding raster
tiles instead would work but costs 100-500KB per ride, committed forever and
growing with the archive.

So the map is vector: the route polyline BRouter returns, projected to Web
Mercator and drawn in the café palette, with its endpoints, the distance, and
the OpenStreetMap credit the route geometry is owed. A few KB, no dependencies
beyond the stdlib, no external requests from the visitor's browser.

Used by scripts/render_route_maps.py; kept separate so the drawing has no
network code in it and can be tested on a fixed polyline.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

WIDTH = 800
# The canvas height follows the route's own shape, so a north-south ride fills
# a near-square frame instead of drawing a thin line down the middle of a
# letterbox. Clamped at both ends: too wide and the route is a hairline, too
# tall and the card has to shrink it to fit. The card renders map images with
# object-fit: contain, so whatever aspect comes out here is shown whole.
MIN_ASPECT = 0.45  # height / width — a very wide, flat route
MAX_ASPECT = 1.0   # a tall route stops at square
# Room for the route to breathe: the distance badge sits in the top-left
# corner and the endpoint labels along the bottom, so the drawing area has to
# clear both. The badge lives up there rather than centred at the bottom
# because a long café name in the "… · End" label would run straight over it.
PAD_X = 48
PAD_TOP = 66
PAD_BOTTOM = 74
# Georgia bold is about this fraction of the font size per character. Only used
# to keep the two bottom labels from colliding, so an estimate is enough.
CHAR_WIDTH_RATIO = 0.56
LABEL_SIZE = 20

# Café palette, copied from site/styles.css — an SVG can't read the page's
# custom properties, so these are the one place the hexes are duplicated.
LATTE = "#f6ece0"
OAT = "#e6d5c2"
CREMA = "#b07a4a"
ROAST = "#4a2c1a"
ESPRESSO = "#2e1d13"
FOAM = "#fffaf4"
MUTED = "#7a685a"


def mercator(lat: float, lon: float) -> tuple[float, float]:
    """Web Mercator, in unit square coordinates (0..1, y growing southwards)."""
    lat = max(min(lat, 85.05112878), -85.05112878)
    x = (lon + 180.0) / 360.0
    sin_lat = math.sin(math.radians(lat))
    y = 0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)
    return x, y


def canvas_size(points: list) -> tuple[int, int]:
    """Canvas dimensions whose shape follows the route's own bounding box."""
    if not points:
        return WIDTH, int(WIDTH * MIN_ASPECT)
    merc = [mercator(lat, lon) for lat, lon in points]
    span_x = max(x for x, _ in merc) - min(x for x, _ in merc)
    span_y = max(y for _, y in merc) - min(y for _, y in merc)
    box_w = WIDTH - 2 * PAD_X
    if span_x <= 0:
        aspect = MAX_ASPECT
    else:
        # The height the drawing area needs at the scale that fills the width,
        # turned back into a whole-canvas aspect ratio.
        needed = span_y / span_x * box_w + PAD_TOP + PAD_BOTTOM
        aspect = needed / WIDTH
    aspect = max(MIN_ASPECT, min(MAX_ASPECT, aspect))
    return WIDTH, int(round(WIDTH * aspect))


def project(points: list, width: int = WIDTH, height: int | None = None) -> list:
    """Project lat/lon points into the SVG box, fitted and centred.

    One scale for both axes, so the route keeps its real shape; whichever axis
    has slack gets the leftover as extra centring margin.
    """
    if not points:
        return []
    if height is None:
        height = canvas_size(points)[1]
    merc = [mercator(lat, lon) for lat, lon in points]
    xs = [x for x, _ in merc]
    ys = [y for _, y in merc]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    box_w = width - 2 * PAD_X
    box_h = height - PAD_TOP - PAD_BOTTOM
    # A single-point (or degenerate) route has no span to divide by; any scale
    # will do, since the centring below puts it in the middle either way.
    scale = min(
        box_w / span_x if span_x else float("inf"),
        box_h / span_y if span_y else float("inf"),
    )
    if scale == float("inf"):
        scale = 1.0
    offset_x = PAD_X + (box_w - span_x * scale) / 2
    offset_y = PAD_TOP + (box_h - span_y * scale) / 2
    return [
        (offset_x + (x - min(xs)) * scale, offset_y + (y - min(ys)) * scale)
        for x, y in merc
    ]


def _path_data(projected: list) -> str:
    if not projected:
        return ""
    head = f"M{projected[0][0]:.1f},{projected[0][1]:.1f}"
    rest = "".join(f"L{x:.1f},{y:.1f}" for x, y in projected[1:])
    return head + rest


def _dot(x: float, y: float, fill: str, stroke: str) -> str:
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="4"/>'
    )


def _text(x: float, y: float, content: str, size: int, fill: str,
          weight: str = "400", anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Georgia, \'Iowan Old Style\', '
        f"'Times New Roman', serif\" font-size=\"{size}\" font-weight=\"{weight}\" "
        f'fill="{fill}" text-anchor="{anchor}">{escape(content)}</text>'
    )


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _place_name(address: str) -> str:
    """"Tatte Bakery, 100 Main St, …" → "Tatte Bakery"."""
    return " ".join(str(address or "").split(",")[0].split())


def fit_labels(start: str, end: str, width: int, limit: int = 24) -> tuple[str, str]:
    """Clip the two bottom labels until they can sit side by side.

    They're drawn from opposite edges, so the only thing that matters is that
    their combined width plus a gap fits between the margins.
    """
    available = width - 2 * PAD_X - 24  # 24px of breathing room in the middle
    while limit > 6:
        left = ("Start · " + _clip(_place_name(start), limit)) if start else ""
        right = (_clip(_place_name(end), limit) + " · End") if end else ""
        needed = (len(left) + len(right)) * LABEL_SIZE * CHAR_WIDTH_RATIO
        if needed <= available:
            return left, right
        limit -= 1
    return left, right


def render_route_svg(
    geometry: list,
    start: str = "",
    end: str = "",
    distance: str = "",
    title: str = "",
) -> str:
    """An SVG map of `geometry` (a list of (lat, lon)).

    `title` becomes the accessible name; the endpoint labels and distance are
    drawn along the bottom. Returns the SVG source.
    """
    width, height = canvas_size(geometry)
    projected = project(geometry, width, height)
    label = _clip(title or "Ride route", 90)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{escape(label)}">',
        f"<title>{escape(label)}</title>",
        f'<rect width="{width}" height="{height}" fill="{LATTE}"/>',
    ]

    if projected:
        data = _path_data(projected)
        # Casing underneath, then the route on top: the pale outline keeps the
        # line readable where it doubles back on itself.
        parts.append(
            f'<path d="{data}" fill="none" stroke="{OAT}" stroke-width="13" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
        parts.append(
            f'<path d="{data}" fill="none" stroke="{CREMA}" stroke-width="6" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
        first_x, first_y = projected[0]
        last_x, last_y = projected[-1]
        parts.append(_dot(first_x, first_y, FOAM, ROAST))
        parts.append(_dot(last_x, last_y, ROAST, FOAM))

    # Distance badge, top-left corner (PAD_TOP keeps the route clear of it).
    if distance:
        pill_w = int(12 * len(distance)) + 34
        parts.append(
            f'<rect x="{PAD_X}" y="24" width="{pill_w}" height="34" rx="17" '
            f'fill="{ESPRESSO}"/>'
        )
        parts.append(_text(PAD_X + pill_w / 2, 48, distance, 19, FOAM, "700", "middle"))

    # Endpoint labels along the bottom: start from the left edge, end from the
    # right, clipped by fit_labels so they can't run into each other.
    baseline = height - 40
    left_label, right_label = fit_labels(start, end, width)
    if left_label:
        parts.append(_text(PAD_X, baseline, left_label, LABEL_SIZE, ROAST, "700"))
    if right_label:
        parts.append(_text(width - PAD_X, baseline, right_label, LABEL_SIZE, ROAST, "700", "end"))

    # ODbL: the geometry is derived from OpenStreetMap data, so the map that
    # shows it has to say so.
    parts.append(_text(width - PAD_X, height - 14, "Route © OpenStreetMap contributors", 12, MUTED, "400", "end"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
