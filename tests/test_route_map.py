"""Tests for the drawn route map — scripts/route_map.py and render_route_maps.py.

Fully offline: the geometry is a fixed polyline and the router is stubbed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import render_route_maps  # noqa: E402
import route_map  # noqa: E402

# A short south-west → north-east line through Boston, plus a wiggle.
GEOMETRY = [
    (42.3355, -71.1506),
    (42.3400, -71.1600),
    (42.3500, -71.1700),
    (42.3668, -71.1868),
]
# A route that is much wider than it is tall.
FLAT = [(42.3500, -71.2000), (42.3505, -71.0500)]
# ...and one much taller than it is wide.
TALL = [(42.2500, -71.1000), (42.4500, -71.1005)]


def svg_tree(svg: str):
    return ElementTree.fromstring(svg)


# --- projection ---


def test_mercator_is_monotonic():
    """North is up (smaller y) and east is right (larger x)."""
    south = route_map.mercator(42.0, -71.0)
    north = route_map.mercator(43.0, -71.0)
    east = route_map.mercator(42.0, -70.0)
    assert north[1] < south[1]
    assert east[0] > south[0]


def test_projected_points_stay_inside_the_drawing_area():
    width, height = route_map.canvas_size(GEOMETRY)
    projected = route_map.project(GEOMETRY, width, height)
    assert len(projected) == len(GEOMETRY)
    for x, y in projected:
        assert route_map.PAD_X - 0.5 <= x <= width - route_map.PAD_X + 0.5
        assert route_map.PAD_TOP - 0.5 <= y <= height - route_map.PAD_BOTTOM + 0.5


def test_projection_preserves_the_route_shape():
    """One scale for both axes — a map that stretches to fill would lie."""
    projected = route_map.project(GEOMETRY)
    span_x = max(x for x, _ in projected) - min(x for x, _ in projected)
    span_y = max(y for _, y in projected) - min(y for _, y in projected)
    merc = [route_map.mercator(lat, lon) for lat, lon in GEOMETRY]
    true_x = max(x for x, _ in merc) - min(x for x, _ in merc)
    true_y = max(y for _, y in merc) - min(y for _, y in merc)
    assert abs((span_x / span_y) - (true_x / true_y)) < 0.01


def test_projection_survives_a_degenerate_route():
    """Two identical points have no span to divide by."""
    projected = route_map.project([(42.0, -71.0), (42.0, -71.0)])
    assert len(projected) == 2
    assert all(isinstance(value, float) for point in projected for value in point)


def test_project_empty_is_empty():
    assert route_map.project([]) == []


# --- canvas shape ---


def test_canvas_follows_the_route_shape():
    flat_w, flat_h = route_map.canvas_size(FLAT)
    tall_w, tall_h = route_map.canvas_size(TALL)
    assert flat_h < tall_h
    assert flat_w == tall_w == route_map.WIDTH


def test_canvas_aspect_is_clamped_at_both_ends():
    for points in (FLAT, TALL, GEOMETRY, []):
        width, height = route_map.canvas_size(points)
        assert route_map.MIN_ASPECT - 0.01 <= height / width <= route_map.MAX_ASPECT + 0.01


# --- the SVG itself ---


def test_svg_is_well_formed_and_sized():
    svg = route_map.render_route_svg(GEOMETRY, "A, Boston", "B, Watertown", "~4.0 mi", "Ride")
    root = svg_tree(svg)
    assert root.tag.endswith("svg")
    width, height = route_map.canvas_size(GEOMETRY)
    assert root.get("viewBox") == f"0 0 {width} {height}"


def test_svg_draws_the_route_and_both_endpoints():
    svg = route_map.render_route_svg(GEOMETRY)
    root = svg_tree(svg)
    paths = [el for el in root.iter() if el.tag.endswith("path")]
    circles = [el for el in root.iter() if el.tag.endswith("circle")]
    assert len(paths) == 2  # casing + route
    assert len(circles) == 2  # start + end
    assert paths[0].get("d").count("L") == len(GEOMETRY) - 1


def test_svg_carries_the_labels_and_the_osm_credit():
    svg = route_map.render_route_svg(
        GEOMETRY, "JP Licks, Boston", "Tatte Bakery, Cambridge", "~4.0 mi", "Sunday ride"
    )
    text = " ".join(el.text or "" for el in svg_tree(svg).iter() if el.tag.endswith("text"))
    assert "Start · JP Licks" in text
    assert "Tatte Bakery · End" in text
    assert "~4.0 mi" in text
    assert "OpenStreetMap" in text


def test_svg_escapes_text_from_the_feed():
    """Titles and place names come from Partiful — they can't inject markup."""
    svg = route_map.render_route_svg(GEOMETRY, "<script>x</script>, Boston", "B", "", "A & B")
    assert "<script>" not in svg
    svg_tree(svg)  # still parses


def test_svg_without_a_distance_has_no_badge():
    svg = route_map.render_route_svg(GEOMETRY, "A", "B", "", "Ride")
    rects = [el for el in svg_tree(svg).iter() if el.tag.endswith("rect")]
    assert len(rects) == 1  # just the background


def test_svg_with_no_geometry_still_renders():
    svg = route_map.render_route_svg([], "A", "B", "~1.0 mi", "Ride")
    root = svg_tree(svg)
    assert not [el for el in root.iter() if el.tag.endswith("path")]


def test_long_place_names_are_clipped_to_fit_side_by_side():
    left, right = route_map.fit_labels(
        "The Extremely Long Café Name On Beacon Street, Boston, MA",
        "Another Extremely Long Destination Name, Watertown, MA",
        route_map.WIDTH,
    )
    budget = route_map.WIDTH - 2 * route_map.PAD_X - 24
    assert (len(left) + len(right)) * route_map.LABEL_SIZE * route_map.CHAR_WIDTH_RATIO <= budget
    assert left.startswith("Start · ")
    assert right.endswith(" · End")


def test_short_place_names_are_left_alone():
    left, right = route_map.fit_labels("Tatte, Boston, MA", "Merai, Brookline, MA", route_map.WIDTH)
    assert left == "Start · Tatte"
    assert right == "Merai · End"


# --- render_route_maps ---


def ride(uid="ride-1", **extra):
    base = {
        "uid": uid,
        "title": "Café ride",
        "routes": [{
            "label": "Estimated Route",
            "url": "https://maps.app.goo.gl/x",
            "start": "A, Boston",
            "end": "B, Watertown",
            "distance_display": "~4.0 mi",
            "points": [[42.3355, -71.1506], [42.3668, -71.1868]],
        }],
    }
    base.update(extra)
    return base


def fake_geometry(points):
    return GEOMETRY


def test_render_writes_the_svg_and_points_the_ride_at_it(tmp_path):
    r = ride()
    url = render_route_maps.render_for_ride(r, tmp_path, "maps", fetch=fake_geometry)
    assert url == "maps/ride-1.svg"
    assert r["map_image"] == "maps/ride-1.svg"
    assert (tmp_path / "ride-1.svg").read_text(encoding="utf-8").startswith("<svg")


def test_render_is_skipped_when_the_map_already_exists(tmp_path):
    (tmp_path / "ride-1.svg").write_text("<svg/>", encoding="utf-8")

    def unreachable(points):
        raise AssertionError("an existing map must not be re-drawn")

    r = ride()
    assert render_route_maps.render_for_ride(r, tmp_path, "maps", fetch=unreachable) is None
    assert r["map_image"] == "maps/ride-1.svg"  # still wired up


def test_render_skips_a_ride_with_no_route(tmp_path):
    r = ride(routes=[])
    assert render_route_maps.render_for_ride(r, tmp_path, "maps", fetch=fake_geometry) is None
    assert "map_image" not in r


def test_render_skips_a_route_without_coordinates(tmp_path):
    r = ride(routes=[{"label": "Route", "url": "x", "start": "A", "end": "B"}])
    assert render_route_maps.render_for_ride(r, tmp_path, "maps", fetch=fake_geometry) is None
    assert "map_image" not in r


def test_render_is_soft_when_the_router_is_down(tmp_path):
    r = ride()
    assert render_route_maps.render_for_ride(r, tmp_path, "maps", fetch=lambda p: []) is None
    assert "map_image" not in r
    assert not list(tmp_path.iterdir())


def test_render_picks_the_first_route_with_coordinates(tmp_path):
    r = ride(routes=[
        {"label": "No points", "url": "x", "start": "A", "end": "B"},
        {"label": "Has points", "url": "y", "start": "C", "end": "D",
         "points": [[42.0, -71.0], [42.1, -71.1]]},
    ])
    assert render_route_maps.mappable_route(r)["label"] == "Has points"


def test_uids_are_made_filename_safe(tmp_path):
    r = ride(uid="evt-past/../weird uid@partiful.com")
    render_route_maps.render_for_ride(r, tmp_path, "maps", fetch=fake_geometry)
    written = [p.name for p in tmp_path.iterdir()]
    assert written == ["evt-past-weird-uid-partiful.com.svg"]
    # The point of the exercise: no separators, and no traversal.
    assert ".." not in written[0]
    assert "/" not in r["map_image"].split("/")[-1]


def test_a_uid_that_is_all_punctuation_still_gets_a_name(tmp_path):
    r = ride(uid="///...")
    render_route_maps.render_for_ride(r, tmp_path, "maps", fetch=fake_geometry)
    assert [p.name for p in tmp_path.iterdir()] == ["ride.svg"]


def test_process_rewrites_the_payload(tmp_path):
    payload = tmp_path / "events.json"
    payload.write_text(json.dumps({"count": 1, "events": [ride()]}), encoding="utf-8")
    drawn = render_route_maps.process(payload, tmp_path / "maps", "maps", fetch=fake_geometry)
    assert drawn == 1
    written = json.loads(payload.read_text(encoding="utf-8"))
    assert written["events"][0]["map_image"] == "maps/ride-1.svg"


def test_process_leaves_the_payload_alone_when_nothing_changed(tmp_path):
    payload = tmp_path / "events.json"
    payload.write_text(json.dumps({"count": 1, "events": [ride(routes=[])]}), encoding="utf-8")
    before = payload.read_text(encoding="utf-8")
    assert render_route_maps.process(payload, tmp_path / "maps", "maps", fetch=fake_geometry) == 0
    assert payload.read_text(encoding="utf-8") == before
