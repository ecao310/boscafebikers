#!/usr/bin/env python3
"""Render a ride's route as a small self-contained SVG map.

Why a drawn map and not a screenshot of Google Maps: there is no browser in the
sync (so nothing to screenshot with), Google's Static Maps API needs a billed
key, and hotlinking a public tile server from a live site would point every
visitor's browser at someone else's tile server.

So the map is an SVG: the route polyline BRouter returns, projected to Web
Mercator and drawn in the café palette over a basemap of raster map tiles that
the sync fetched once and embedded as data: URIs — placed in the same Mercator
projection, so streets and route line up. The tiles are what make the picture
read as a map; they are also almost all of its bytes, so the zoom is chosen so
a handful of them cover the canvas (`MIN_TILE_SIDE`), the edge ones are
cropped to it, and a map with no tiles (the tile server was unreachable) still
draws the route on a plain latte canvas rather than failing the sync.

This module is stdlib-only and never touches the network: `tile_plan()` says
which tiles a route needs, the caller fetches them, and `render_route_svg()`
takes their bytes. Used by scripts/render_route_maps.py; kept separate so the
drawing can be tested on a fixed polyline and a fixture tile.
"""

from __future__ import annotations

import base64
import math
import re
import struct
import zlib
from xml.sax.saxutils import escape


def _attr(value: str) -> str:
    """Escape a value for a double-quoted attribute (``escape`` leaves ``"`` alone)."""
    return escape(str(value), {'"': "&quot;"})

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
# The credit line is doing licence work once tiles are on the map (OSM asks
# for attribution "clearly on the map"), and the card shows an 800-unit
# canvas at ~280-600 CSS px, so 12 units was ~4px on a phone. 16 is the
# smallest that still reads there.
CREDIT_SIZE = 16

# Basemap tiles: standard 256px slippy-map tiles (z/x/y, Web Mercator). Edge
# tiles are cropped to the canvas before they are embedded, so what a map
# costs is the tile *pixels the canvas shows*, and that scales with
# 1 / (tile side on the canvas)². The zoom is the deepest one whose tiles are
# still at least MIN_TILE_SIDE canvas px across: one zoom deeper would double
# the sharpness and quadruple the bytes. At 320 the whole canvas is at most
# ~6 tile-areas (~150-220KB of base64 for a square map, ~50-100KB for a flat
# one) and a tile is drawn at 1.0-2.0x — on a desktop card (~600 CSS px for
# an 800-unit canvas, 420 for a tall one) that is close to 1:1.
TILE_SIZE = 256
MIN_TILE_SIDE = 320
# What that rule implies for the count: ceil(800 / 320) + 1 per axis.
MAX_TILES = 16
MAX_ZOOM = 18
MIN_ZOOM = 1
# The tiles are drawn under a translucent latte wash so they take the café
# palette and the route stays the strongest thing on the map; the bottom of
# the canvas fades to solid latte so the endpoint labels sit on plain ground.
WASH_OPACITY = 0.42
# Marker on the <svg> root that says a basemap was embedded — the renderer
# uses it to tell a finished map from one drawn while the tile server was
# down, so the latter gets another go on the next sync.
BASEMAP_ATTR = "data-basemap"
BASEMAP_ATTR_RE = re.compile(r'<svg\b[^>]*\s' + BASEMAP_ATTR + r'="([^"]*)"')

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


def fit(points: list, width: int = WIDTH, height: int | None = None) -> tuple:
    """The projection that fits `points` on the canvas.

    Returns ``(scale, offset_x, offset_y, min_x, min_y)``: a Mercator point
    lands at ``offset + (merc - min) * scale``. One scale for both axes, so
    the route keeps its real shape; whichever axis has slack gets the leftover
    as extra centring margin. The tiles use the same numbers, which is what
    keeps the streets under the route line.
    """
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
    return scale, offset_x, offset_y, min(xs), min(ys)


def project(points: list, width: int = WIDTH, height: int | None = None) -> list:
    """Project lat/lon points into the SVG box, fitted and centred."""
    if not points:
        return []
    scale, offset_x, offset_y, min_x, min_y = fit(points, width, height)
    return [
        (offset_x + (x - min_x) * scale, offset_y + (y - min_y) * scale)
        for x, y in (mercator(lat, lon) for lat, lon in points)
    ]


# --- basemap tiles ---


def tile_index(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """The slippy-map tile (x, y) that contains this point at `zoom`."""
    n = 2 ** zoom
    x, y = mercator(lat, lon)
    return min(int(x * n), n - 1), min(int(y * n), n - 1)


def _tile_range(fitted: tuple, width: int, height: int, zoom: int) -> tuple:
    """(x0, x1, y0, y1), inclusive, of the tiles the canvas touches."""
    scale, offset_x, offset_y, min_x, min_y = fitted
    n = 2 ** zoom

    def span(offset, low, extent):
        first = low + (0 - offset) / scale
        last = low + (extent - offset) / scale
        # A tile that starts exactly on the far edge contributes nothing.
        lo = max(0, min(n - 1, math.floor(first * n)))
        hi = max(0, min(n - 1, math.ceil(last * n) - 1))
        return lo, max(lo, hi)

    x0, x1 = span(offset_x, min_x, width)
    y0, y1 = span(offset_y, min_y, height)
    return x0, x1, y0, y1


def tile_side(fitted: tuple, zoom: int) -> float:
    """How many canvas px one tile spans at `zoom` under this projection."""
    return fitted[0] / 2 ** zoom


def choose_zoom(fitted: tuple, min_side: float = MIN_TILE_SIDE) -> int:
    """The deepest zoom whose tiles are still at least `min_side` px across."""
    for zoom in range(MAX_ZOOM, MIN_ZOOM, -1):
        if tile_side(fitted, zoom) >= min_side:
            return zoom
    return MIN_ZOOM


def tile_plan(points: list, width: int | None = None, height: int | None = None) -> tuple:
    """(zoom, [(x, y), …]) — the tiles a basemap under this route needs.

    Pure arithmetic on the route, so the caller can fetch exactly these and
    hand the bytes to `render_route_svg`, which recomputes the same plan.
    """
    if not points:
        return MIN_ZOOM, []
    if width is None:
        width = WIDTH
    if height is None:
        height = canvas_size(points)[1]
    fitted = fit(points, width, height)
    zoom = choose_zoom(fitted)
    x0, x1, y0, y1 = _tile_range(fitted, width, height, zoom)
    return zoom, [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def tile_rect(fitted: tuple, zoom: int, x: int, y: int) -> tuple[float, float, float]:
    """Where tile (x, y) lands on the canvas: (left, top, side)."""
    scale, offset_x, offset_y, min_x, min_y = fitted
    n = 2 ** zoom
    side = scale / n
    return (
        offset_x + (x / n - min_x) * scale,
        offset_y + (y / n - min_y) * scale,
        side,
    )


def tile_mime(data: bytes) -> str | None:
    """The image type of a tile from its magic bytes; None if it isn't one."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


# --- cropping edge tiles ---
#
# Only a slice of each edge tile is inside the canvas, and the tiles are nearly
# all of a map's bytes, so the invisible part is worth cutting off before it is
# embedded. There is no image library in the sync, but a tile PNG is a simple
# thing (8-bit, non-interlaced, one filter byte per row — OpenStreetMap's
# standard tiles are palette images filtered with "None" throughout), so a
# crop is: inflate, drop the
# filter bytes, slice, deflate. Nothing is resampled and the palette is copied
# as is, so the pixels that remain are exactly the ones served. Anything more
# exotic (16-bit, interlaced, an unknown chunk layout) is embedded whole.

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# colour type → bytes per pixel at bit depth 8
PNG_BPP = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _png_chunks(data: bytes) -> list:
    chunks = []
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise ValueError("truncated PNG chunk")
        chunks.append((tag, body))
        pos += 12 + length
    return chunks


def _png_chunk(tag: bytes, body: bytes) -> bytes:
    crc = zlib.crc32(tag + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", crc)


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> list:
    """The image rows of a non-interlaced PNG, with the filters undone."""
    stride = width * bpp
    if len(raw) < height * (stride + 1):
        raise ValueError("short PNG image data")
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        kind = raw[pos]
        row = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += stride + 1
        if kind == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif kind == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 255
        elif kind == 3:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 255
        elif kind == 4:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (row[i] + pred) & 255
        elif kind != 0:
            raise ValueError(f"unknown PNG filter {kind}")
        rows.append(row)
        prev = row
    return rows


def png_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) of a PNG, or None if `data` isn't one."""
    if data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR" or len(data) < 24:
        return None
    return struct.unpack(">II", data[16:24])


def crop_png(data: bytes, left: int, top: int, width: int, height: int) -> bytes | None:
    """The `width`×`height` window of `data` at (left, top), as a new PNG.

    None when the PNG is one this doesn't handle (anything but 8-bit,
    non-interlaced) or the window doesn't fit — the caller embeds the whole
    tile instead. Palette and transparency chunks are carried over unchanged.
    """
    try:
        if data[:8] != PNG_SIGNATURE:
            return None
        chunks = _png_chunks(data)
        if not chunks or chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13:
            return None
        src_w, src_h, depth, colour, compression, filt, interlace = struct.unpack(
            ">IIBBBBB", chunks[0][1]
        )
        bpp = PNG_BPP.get(colour)
        if depth != 8 or bpp is None or compression or filt or interlace:
            return None
        if width <= 0 or height <= 0 or left < 0 or top < 0:
            return None
        if left + width > src_w or top + height > src_h:
            return None
        raw = zlib.decompress(b"".join(body for tag, body in chunks if tag == b"IDAT"))
        rows = _unfilter(raw, src_w, src_h, bpp)
    except (ValueError, zlib.error, struct.error):
        return None
    window = b"".join(
        b"\x00" + bytes(rows[y][left * bpp:(left + width) * bpp])
        for y in range(top, top + height)
    )
    header = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0)
    out = [PNG_SIGNATURE, _png_chunk(b"IHDR", header)]
    for tag, body in chunks[1:]:
        if tag not in (b"IDAT", b"IEND"):
            out.append(_png_chunk(tag, body))  # PLTE, tRNS, gAMA, … as they were
    out.append(_png_chunk(b"IDAT", zlib.compress(window, 9)))
    out.append(_png_chunk(b"IEND", b""))
    return b"".join(out)


def visible_window(left: float, top: float, side: float, width: int, height: int) -> tuple:
    """The part of a tile drawn at (left, top, side) that the canvas shows.

    In tile pixels: (x, y, w, h), rounded outwards so nothing visible is cut,
    and the full (0, 0, TILE_SIZE, TILE_SIZE) for a tile entirely inside.
    """
    per_px = TILE_SIZE / side
    x0 = max(0, math.floor((0 - left) * per_px))
    y0 = max(0, math.floor((0 - top) * per_px))
    x1 = min(TILE_SIZE, math.ceil((width - left) * per_px))
    y1 = min(TILE_SIZE, math.ceil((height - top) * per_px))
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def has_basemap(svg: str) -> bool:
    """Whether this SVG source was drawn with tiles under the route."""
    match = BASEMAP_ATTR_RE.search(svg[:2000])
    return bool(match and match.group(1))


def _basemap(
    projected_fit: tuple, width: int, height: int, zoom: int, plan: list, tiles: dict
) -> list:
    """The <image> elements for a complete tile set, or [] if any is missing.

    All or nothing: a basemap with holes in it looks broken, and an incomplete
    one must not be marked finished.
    """
    if not plan:
        return []
    encoded = []
    for x, y in plan:
        data = tiles.get((zoom, x, y))
        mime = tile_mime(data) if isinstance(data, (bytes, bytearray)) else None
        if not mime:
            return []
        window = (0, 0, TILE_SIZE, TILE_SIZE)
        if png_size(data) == (TILE_SIZE, TILE_SIZE):
            # An edge tile is mostly off the canvas: embed only the strip that
            # shows. Tiles in any other shape are embedded whole and stretched.
            wx, wy, ww, wh = visible_window(*tile_rect(projected_fit, zoom, x, y), width, height)
            if (ww, wh) != (TILE_SIZE, TILE_SIZE):
                cropped = crop_png(data, wx, wy, ww, wh)
                if cropped is not None:
                    data, window = cropped, (wx, wy, ww, wh)
        encoded.append((x, y, mime, window, base64.b64encode(data).decode("ascii")))
    x0 = min(x for x, _ in plan)
    y0 = min(y for _, y in plan)
    left, top, side = tile_rect(projected_fit, zoom, x0, y0)
    # One transform for the whole grid and integer tile positions inside it:
    # placing each scaled tile at its own fractional offset leaves hairline
    # seams between them in most rasterisers.
    parts = [
        f'<g transform="translate({left:.3f} {top:.3f}) scale({side / TILE_SIZE:.6f})">'
    ]
    for x, y, mime, (wx, wy, ww, wh), b64 in encoded:
        parts.append(
            f'<image x="{(x - x0) * TILE_SIZE + wx}" y="{(y - y0) * TILE_SIZE + wy}" '
            f'width="{ww}" height="{wh}" href="data:{mime};base64,{b64}"/>'
        )
    parts.append("</g>")
    # The wash tints the tiles toward the palette; the fade gives the labels
    # plain ground to sit on.
    parts.append(
        f'<rect width="{width}" height="{height}" fill="{LATTE}" opacity="{WASH_OPACITY}"/>'
    )
    fade_top = max(0, height - PAD_BOTTOM - 36)
    parts.append(
        '<defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{LATTE}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{LATTE}" stop-opacity="1"/>'
        "</linearGradient></defs>"
    )
    parts.append(
        f'<rect x="0" y="{fade_top}" width="{width}" height="{height - fade_top}" fill="url(#fade)"/>'
    )
    return parts


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
          weight: str = "400", anchor: str = "start", halo: bool = False) -> str:
    # paint-order="stroke" draws the halo underneath the glyphs, so text over
    # tiles stays readable whatever happens to be under it.
    outline = (
        f' stroke="{FOAM}" stroke-width="{max(3, size // 4)}" stroke-linejoin="round" '
        'paint-order="stroke"'
    ) if halo else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Georgia, \'Iowan Old Style\', '
        f"'Times New Roman', serif\" font-size=\"{size}\" font-weight=\"{weight}\" "
        f'fill="{fill}" text-anchor="{anchor}"{outline}>{escape(content)}</text>'
    )


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _place_name(address: str) -> str:
    """"Tatte Bakery, 100 Main St, …" → "Tatte Bakery"."""
    return " ".join(str(address or "").split(",")[0].split())


# Mirror of ride-card.js startName(): rides start at Bluebikes docks, whose
# address is "Bluebikes, <station>, <city>, MA <zip>", so the leading word says
# nothing and the station detail is what the label should carry.
BLUEBIKES_RE = re.compile(r"^bluebikes\b[\s:\-–—]*(.*)$", re.IGNORECASE)
STATE_RE = re.compile(r"^[A-Z]{2}(\s+\d{5}(-\d{4})?)?$")


def _start_name(address: str) -> str:
    """"Bluebikes, Cleveland Circle, Boston, MA 02135" → "Cleveland Circle".

    A two-segment station ("Bunker Hill Mall, Main St at Austin St") survives
    whole when the address ends in a "<city>, <ST> [zip]" pair; anything that
    isn't a Bluebikes dock keeps its leading segment, like ``_place_name``.
    """
    raw = " ".join(str(address or "").split())
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return ""
    match = BLUEBIKES_RE.match(parts[0])
    if not match:
        return parts[0]
    detail = ([match.group(1)] if match.group(1) else []) + parts[1:]
    if not detail:
        return raw
    if len(detail) >= 3 and STATE_RE.match(detail[-1]):
        return ", ".join(detail[:-2])
    return detail[0]


def fit_labels(start: str, end: str, width: int, limit: int = 24) -> tuple[str, str]:
    """Clip the two bottom labels until they can sit side by side.

    They're drawn from opposite edges, so the only thing that matters is that
    their combined width plus a gap fits between the margins.
    """
    available = width - 2 * PAD_X - 24  # 24px of breathing room in the middle
    while limit > 6:
        left = ("Start · " + _clip(_start_name(start), limit)) if start else ""
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
    tiles: dict | None = None,
    tile_source: str = "",
    tile_credit: str = "",
) -> str:
    """An SVG map of `geometry` (a list of (lat, lon)).

    `title` becomes the accessible name; the endpoint labels and distance are
    drawn along the bottom. `tiles` maps ``(zoom, x, y)`` to the bytes of the
    tiles `tile_plan(geometry)` asked for; when every one is present they are
    embedded under the route, the root gets ``data-basemap="<tile_source>"``,
    and `tile_credit` joins the OpenStreetMap credit. Missing or malformed
    tiles mean no basemap — the route still draws on plain latte, unmarked,
    so the caller knows to try again. Returns the SVG source.
    """
    width, height = canvas_size(geometry)
    projected = project(geometry, width, height)
    label = _clip(title or "Ride route", 90)

    basemap: list = []
    if projected and tiles:
        zoom, plan = tile_plan(geometry, width, height)
        basemap = _basemap(fit(geometry, width, height), width, height, zoom, plan, tiles)
    marker = f' {BASEMAP_ATTR}="{_attr(tile_source or "tiles")}"' if basemap else ""

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{_attr(label)}"{marker}>',
        f"<title>{escape(label)}</title>",
        f'<rect width="{width}" height="{height}" fill="{LATTE}"/>',
    ]
    parts.extend(basemap)

    if projected:
        data = _path_data(projected)
        # Casing underneath, then the route on top: the pale outline keeps the
        # line readable where it doubles back on itself, and lifts it off the
        # streets in the basemap.
        casing = FOAM if basemap else OAT
        parts.append(
            f'<path d="{data}" fill="none" stroke="{casing}" stroke-width="13" '
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
    halo = bool(basemap)
    baseline = height - 40
    left_label, right_label = fit_labels(start, end, width)
    if left_label:
        parts.append(_text(PAD_X, baseline, left_label, LABEL_SIZE, ROAST, "700", halo=halo))
    if right_label:
        parts.append(_text(width - PAD_X, baseline, right_label, LABEL_SIZE, ROAST, "700", "end", halo=halo))

    # ODbL: the geometry (and the tiles) derive from OpenStreetMap data, so
    # the map that shows them has to say so; a tile provider with its own
    # credit line (OSM's own tiles need none) is appended.
    credit = "Route © OpenStreetMap contributors"
    if basemap:
        credit = "Map © OpenStreetMap contributors" + (f" · {tile_credit}" if tile_credit else "")
    parts.append(_text(width - PAD_X, height - 14, credit, CREDIT_SIZE, MUTED, "400", "end", halo=halo))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
