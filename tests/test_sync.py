"""Tests for scripts/sync.py — the one-process pipeline and its step order.

Fully offline. The feed is tests/fixtures/sample.ics, the Partiful event page
is tests/fixtures/event-page.html, the basemap "tiles" are the 8x8 fixture PNG,
and the router / geocoder are stubs, all injected through ``sync.run``'s
keyword seams.

The property under test is the one the workflow's commit guard depends on: a
sync that finds nothing new writes zero bytes. Each ordering rule gets its own
test, which reorders ``sync.STEPS`` and asserts the specific damage.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_rides  # noqa: E402
import geocode_cafes  # noqa: E402
import render_route_maps  # noqa: E402
import route_map  # noqa: E402
import sync  # noqa: E402

EASTERN = ZoneInfo("America/New_York")
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample.ics"
EVENT_PAGE = (REPO_ROOT / "tests" / "fixtures" / "event-page.html").read_text(
    encoding="utf-8"
)
TILE = (REPO_ROOT / "tests" / "fixtures" / "tile.png").read_bytes()

# Pinned clock: after the fixture's one past ride (2024) and well before its
# two future ones (2030), so the partition never depends on the wall clock.
NOW = datetime(2026, 1, 10, 12, 0, tzinfo=EASTERN)
# The second run happens a few minutes later — that is the whole point. Every
# run stamps a fresh `updated_at`; only the *files* have to stay still.
LATER = NOW + timedelta(minutes=7)

# A short Boston polyline, standing in for BRouter's geometry.
GEOMETRY = [
    (42.3355, -71.1506),
    (42.3400, -71.1600),
    (42.3500, -71.1700),
    (42.3668, -71.1868),
]

# What the fixture page's maps.app.goo.gl custom fields resolve to. Same pair
# tests/test_fetch_rides.py uses: one real directions URL (with the geocode
# tokens that give the route its coordinates) and one plain place pin.
RESOLVED_LINKS = {
    "https://maps.app.goo.gl/RouteShortLink1?g_st=ic": (
        "https://maps.google.com/?saddr=Bluebikes,+Cleveland+Circle,+Boston,+MA"
        "&daddr=Tatte+Bakery,+Boston,+MA&dirflg=b"
        "&geocode=FTf9hQId6lPC-ylRGlXiU3jjiTGY1w16bG3cRw%3D%3D;"
        "FWd3hgIdjcbB-ykdbpobJHnjiTGRSDuTYi0pzA%3D%3D"
    ),
    "https://maps.app.goo.gl/PlaceShortLink1?g_st=ic": (
        "https://maps.google.com?q=Bluebikes,+Cleveland+Circle&entry=gps"
    ),
}


# --- the stubbed network ---------------------------------------------------


def fake_page(url: str) -> str:
    """Every ride's Partiful page is the fixture page."""
    return EVENT_PAGE


def fake_resolve(url: str) -> str:
    if url in RESOLVED_LINKS:
        return RESOLVED_LINKS[url]
    raise ValueError(f"cannot resolve {url}")


def fake_length(points: list) -> float:
    """Stand-in for BRouter's distance: 1 km per leg."""
    return 1000.0 * (len(points) - 1)


def fake_geometry(points: list) -> list:
    return GEOMETRY


def fake_tile(zoom: int, x: int, y: int) -> bytes:
    return TILE


def fake_geocode(url: str) -> list:
    return [{"lat": "42.348765", "lon": "-71.123456"}]


def no_sleep(_seconds) -> None:
    pass


SEAMS = {
    "fetch_page": fake_page,
    "resolve_link": fake_resolve,
    "fetch_length": fake_length,
    "fetch_geometry": fake_geometry,
    "fetch_tile": fake_tile,
    "geocode_fetch": fake_geocode,
    "geocode_sleep": no_sleep,
}


# --- helpers ---------------------------------------------------------------


def config(data_dir: Path, now: datetime = NOW, **extra) -> sync.Config:
    return sync.Config(data_dir=data_dir, ics_file=FIXTURE, now=now, **extra)


def do_run(data_dir: Path, now: datetime = NOW, steps=None, **extra) -> sync.Run:
    return sync.run(config(data_dir, now, **extra), steps=steps, **SEAMS)


def ordered(*names) -> tuple:
    """``sync.STEPS`` in a different order — the same steps, nothing dropped."""
    by_name = dict(sync.STEPS)
    assert set(names) == set(by_name), "an ordering test must keep every step"
    return tuple((name, by_name[name]) for name in names)


def snapshot(data_dir: Path) -> dict:
    """Every file under the data dir, by relative path → bytes."""
    return {
        str(path.relative_to(data_dir)): path.read_bytes()
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
    }


def payload_of(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def uids(path: Path) -> set:
    """The UIDs in a payload. A file that was never written holds nothing —
    an archive with no rides in it is not written at all."""
    if not path.exists():
        return set()
    return {ride["uid"] for ride in payload_of(path)["events"]}


def feed_rides(now: datetime = NOW, past: bool = False) -> list:
    return fetch_rides.parse_events(FIXTURE.read_bytes(), now=now, past=past)


def write_payload(path: Path, rides: list, now: datetime = NOW) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            fetch_rides.build_payload(rides, now=now), indent=2, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )


def dropped_ride() -> dict:
    """A ride that has already happened and is no longer in the feed.

    Partiful gives no guarantee it keeps exporting old events, so the only copy
    of this one is the previously committed events.json — which is exactly what
    the archive step reads, and exactly what it loses if it runs after the
    promote overwrites that file.
    """
    start = NOW - timedelta(hours=2)
    return {
        "uid": "evt-dropped-somerville@partiful.com",
        "title": "Somerville coffee crawl",
        "start": start.isoformat(),
        "end": None,
        "date_display": f"{start:%A, %B} {start.day}",
        "time_display": "10:00 am",
        "location": "Diesel Café, 257 Elm St, Somerville, MA 02144",
        "location_hidden": False,
        "location_url": None,
        "description": "Three stops, one pastry each.",
        "rsvp_url": None,
        "image": None,
        "routes": None,
    }


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    target = tmp_path / "site"
    target.mkdir()
    return target


@pytest.fixture
def seeded(data_dir: Path) -> Path:
    """A data dir that already holds a plausible previous sync's output."""
    write_payload(data_dir / "events.json", feed_rides(), now=NOW - timedelta(hours=6))
    write_payload(
        data_dir / "events-past.json", feed_rides(past=True), now=NOW - timedelta(hours=6)
    )
    return data_dir


# --- the run-twice invariant ----------------------------------------------


def test_a_second_run_over_an_empty_dir_changes_nothing(data_dir):
    first = do_run(data_dir)
    assert first.files.changed(), "the first run has to write something"
    before = snapshot(data_dir)

    second = do_run(data_dir, now=LATER)
    assert second.files.changed() == []
    assert snapshot(data_dir) == before


def test_a_second_run_over_a_seeded_dir_changes_nothing(seeded):
    do_run(seeded)
    before = snapshot(seeded)

    second = do_run(seeded, now=LATER)
    assert second.files.changed() == []
    assert snapshot(seeded) == before


def test_the_first_run_produces_the_whole_site_payload(data_dir):
    state = do_run(data_dir)
    written = {path.name for path in state.files.changed()}
    assert {"events.json", "events-past.json", "cafe-points.json", "rides.ics"} <= written
    assert any(path.suffix == ".svg" for path in state.files.changed())
    # Everything hangs off --data-dir, nothing off a hard-coded site/.
    for path in state.files.changed():
        assert data_dir in path.parents


def test_the_maps_are_drawn_with_their_basemap(data_dir):
    do_run(data_dir)
    svgs = sorted((data_dir / "maps").glob("*.svg"))
    assert svgs, "the enriched rides carry routes with coordinates"
    for svg in svgs:
        assert route_map.has_basemap(svg.read_text(encoding="utf-8"))
    # …and the ride points at the map, under the --url-prefix.
    events = payload_of(data_dir / "events.json")["events"]
    assert all(ride["map_image"].startswith("maps/") for ride in events)


def test_the_second_run_redraws_no_maps(data_dir):
    do_run(data_dir)
    drawn = do_run(data_dir, now=LATER).drawn
    assert drawn == 0


def test_the_calendar_is_byte_stable_though_updated_at_moves(data_dir):
    first = do_run(data_dir)
    calendar = (data_dir / "rides.ics").read_bytes()
    stamp = payload_of(data_dir / "events.json")["updated_at"]

    second = do_run(data_dir, now=LATER)
    # Each run really did stamp a fresh time on the payload it built…
    assert first.payload["updated_at"] != second.payload["updated_at"]
    # …and neither the published list nor the calendar moved because of it.
    assert payload_of(data_dir / "events.json")["updated_at"] == stamp
    assert (data_dir / "rides.ics").read_bytes() == calendar
    assert b"DTSTAMP:" in calendar


# --- one test per ordering rule -------------------------------------------


MAPS_AFTER_PROMOTE = ordered(
    "fetch", "archive", "enrich_archive", "geocode", "promote", "maps", "export_ics"
)
ICS_BEFORE_PROMOTE = ordered(
    "fetch", "archive", "enrich_archive", "geocode", "maps", "export_ics", "promote"
)
ARCHIVE_AFTER_PROMOTE = ordered(
    "fetch", "promote", "archive", "enrich_archive", "geocode", "maps", "export_ics"
)


def test_maps_after_the_promote_restamps_events_json_every_run(data_dir):
    """`map_image` is added by the maps step and never by a fetch.

    Publish before drawing and the committed file can never equal the next
    fetch, so every run commits a fresh `updated_at` — forever.
    """
    do_run(data_dir, steps=MAPS_AFTER_PROMOTE)
    stamp = payload_of(data_dir / "events.json")["updated_at"]

    second = do_run(data_dir, now=LATER, steps=MAPS_AFTER_PROMOTE)
    assert config(data_dir).events_path in second.files.changed()
    assert payload_of(data_dir / "events.json")["updated_at"] != stamp
    # The rides themselves are identical; only the timestamp moved.
    assert [ride["uid"] for ride in second.payload["events"]] == [
        ride["uid"] for ride in payload_of(data_dir / "events.json")["events"]
    ]


def test_the_correct_order_leaves_events_json_alone(data_dir):
    """The mirror of the test above: drawn before publishing, nothing churns."""
    do_run(data_dir)
    stamp = payload_of(data_dir / "events.json")["updated_at"]
    second = do_run(data_dir, now=LATER)
    assert config(data_dir).events_path not in second.files.changed()
    assert payload_of(data_dir / "events.json")["updated_at"] == stamp


def test_exporting_the_calendar_before_the_promote_restamps_it_every_run(data_dir):
    """DTSTAMP comes from `updated_at`, which is fresh on every fetch.

    Built from the freshly fetched payload the .ics changes every 6 hours;
    built from the published events.json it moves only when the rides do.
    """
    do_run(data_dir, steps=ICS_BEFORE_PROMOTE)
    calendar = (data_dir / "rides.ics").read_bytes()

    second = do_run(data_dir, now=LATER, steps=ICS_BEFORE_PROMOTE)
    assert config(data_dir).rides_ics_path in second.files.changed()
    assert (data_dir / "rides.ics").read_bytes() != calendar
    # Nothing about the rides changed — only the stamp the export was given.
    assert config(data_dir).events_path not in second.files.changed()


def test_archiving_after_the_promote_loses_a_ride_the_feed_dropped(seeded):
    """The archive is merged from the *previously* committed events.json.

    Promote first and that file has already been overwritten with the fresh
    upcoming list, where the ride that has since started simply isn't.
    """
    rides = feed_rides() + [dropped_ride()]
    rides.sort(key=lambda ride: ride["start"])
    write_payload(seeded / "events.json", rides, now=NOW - timedelta(hours=6))

    do_run(seeded, steps=ARCHIVE_AFTER_PROMOTE)
    assert "evt-dropped-somerville@partiful.com" not in uids(seeded / "events-past.json")


def test_archiving_before_the_promote_keeps_a_ride_the_feed_dropped(seeded):
    """The correct order: the ride is absorbed before its only copy is replaced."""
    rides = feed_rides() + [dropped_ride()]
    rides.sort(key=lambda ride: ride["start"])
    write_payload(seeded / "events.json", rides, now=NOW - timedelta(hours=6))

    do_run(seeded)
    assert "evt-dropped-somerville@partiful.com" in uids(seeded / "events-past.json")
    # …and it is out of the upcoming list, so the calendar can't draw it twice.
    assert "evt-dropped-somerville@partiful.com" not in uids(seeded / "events.json")


def test_the_dropped_ride_stays_archived_on_later_runs(seeded):
    rides = feed_rides() + [dropped_ride()]
    rides.sort(key=lambda ride: ride["start"])
    write_payload(seeded / "events.json", rides, now=NOW - timedelta(hours=6))
    do_run(seeded)
    before = snapshot(seeded)

    second = do_run(seeded, now=LATER)
    assert second.files.changed() == []
    assert snapshot(seeded) == before


# --- --dry-run -------------------------------------------------------------


def test_dry_run_writes_nothing_but_says_what_it_would(data_dir):
    state = sync.run(config(data_dir, dry_run=True), **SEAMS)
    assert state.files.changed(), "it still computes the whole run"
    assert snapshot(data_dir) == {}


def test_dry_run_over_a_finished_dir_reports_nothing(data_dir):
    do_run(data_dir)
    before = snapshot(data_dir)
    state = sync.run(config(data_dir, now=LATER, dry_run=True), **SEAMS)
    assert state.files.changed() == []
    assert snapshot(data_dir) == before


def test_dry_run_reports_every_path_it_would_write(data_dir):
    """Under --dry-run the later steps still see what an earlier one wrote."""
    state = sync.run(config(data_dir, dry_run=True), **SEAMS)
    names = {path.name for path in state.files.changed()}
    # rides.ics is built from the events.json the promote step "wrote": if the
    # overlay didn't work, the export would have had nothing to read.
    assert {"events.json", "events-past.json", "rides.ics"} <= names


# --- excluded events -------------------------------------------------------


def test_excluded_uids_reach_neither_output(data_dir, tmp_path):
    excluded = tmp_path / "excluded.json"
    excluded.write_text(
        json.dumps(
            {
                "evt-future-minuteman@partiful.com": "not a ride",
                "evt-past-jamaica-pond@partiful.com": "a birthday",
            }
        ),
        encoding="utf-8",
    )
    do_run(data_dir, excluded_events=excluded)

    upcoming = uids(data_dir / "events.json")
    assert "evt-future-minuteman@partiful.com" not in upcoming
    assert "evt-past-jamaica-pond@partiful.com" not in uids(data_dir / "events-past.json")
    assert "evt-future-charles-loop@partiful.com" in upcoming


def test_an_excluded_uid_is_purged_from_an_archive_that_already_holds_it(data_dir):
    do_run(data_dir)
    assert "evt-past-jamaica-pond@partiful.com" in uids(data_dir / "events-past.json")

    excluded = data_dir.parent / "excluded.json"
    excluded.write_text(
        json.dumps({"evt-past-jamaica-pond@partiful.com": "a birthday"}),
        encoding="utf-8",
    )
    do_run(data_dir, now=LATER, excluded_events=excluded)
    assert payload_of(data_dir / "events-past.json")["events"] == []


# --- offline is really offline --------------------------------------------


def test_an_ics_file_run_switches_every_network_seam_off():
    seams = sync.Seams(offline=True)
    assert not seams.enrich_enabled
    assert not seams.geocode_enabled
    assert not seams.maps_enabled
    live = sync.Seams(offline=False)
    assert live.enrich_enabled and live.geocode_enabled and live.maps_enabled


def test_the_cli_makes_no_network_calls_on_an_ics_file_run(data_dir, monkeypatch, capsys):
    """--ics-file is the offline contract: no page fetch, no router, no tiles,
    no Nominatim. Every transport this pipeline can reach is booby-trapped."""

    def forbidden(*args, **kwargs):
        raise AssertionError("an --ics-file run must not touch the network")

    monkeypatch.setattr(fetch_rides.requests, "get", forbidden)
    monkeypatch.setattr(render_route_maps.requests, "get", forbidden)
    monkeypatch.setattr(geocode_cafes.urllib.request, "urlopen", forbidden)
    monkeypatch.delenv("PARTIFUL_ICS_URL", raising=False)

    code = sync.main(
        [
            "--data-dir", str(data_dir),
            "--ics-file", str(FIXTURE),
            "--now", NOW.isoformat(),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "wrote" in out and "file(s) changed" in out
    assert (data_dir / "events.json").exists()
    # Nothing that needs the network was produced.
    assert not (data_dir / "cafe-points.json").exists()
    assert not (data_dir / "maps").exists()


def test_the_cli_dry_run_writes_nothing(data_dir, capsys):
    code = sync.main(
        [
            "--data-dir", str(data_dir),
            "--ics-file", str(FIXTURE),
            "--now", NOW.isoformat(),
            "--dry-run",
        ]
    )
    assert code == 0
    assert "would write" in capsys.readouterr().out
    assert snapshot(data_dir) == {}


def test_a_quiet_cli_run_says_no_changes(data_dir, capsys):
    sync.main(["--data-dir", str(data_dir), "--ics-file", str(FIXTURE),
               "--now", NOW.isoformat()])
    capsys.readouterr()
    sync.main(["--data-dir", str(data_dir), "--ics-file", str(FIXTURE),
               "--now", LATER.isoformat()])
    assert "no changes" in capsys.readouterr().out


def test_a_missing_feed_is_the_one_fatal_error(data_dir, capsys, monkeypatch):
    monkeypatch.delenv("PARTIFUL_ICS_URL", raising=False)
    assert sync.main(["--data-dir", str(data_dir)]) == 1
    assert "PARTIFUL_ICS_URL" in capsys.readouterr().err


def test_an_enrichment_miss_is_not_a_failure(data_dir):
    """Fail-soft everywhere: an unreachable event page leaves the sync green."""

    def unreachable(url):
        raise fetch_rides.requests.RequestException("nope")

    state = sync.run(
        config(data_dir),
        **{**SEAMS, "fetch_page": unreachable},
    )
    assert state.payload["count"] == 2
    assert all(ride["image"] is None for ride in state.payload["events"])
    assert (data_dir / "events.json").exists()


# --- the paths all hang off --data-dir ------------------------------------


def test_every_published_path_derives_from_the_data_dir(tmp_path):
    cfg = sync.Config(data_dir=tmp_path / "elsewhere")
    for path in (
        cfg.events_path,
        cfg.archive_path,
        cfg.cafe_points_path,
        cfg.rides_ics_path,
        cfg.maps_dir,
    ):
        assert path.parent == cfg.data_dir or path.parent.parent == cfg.data_dir
    # The sidecars are code, not data: they stay in scripts/.
    assert cfg.ride_images == fetch_rides.RIDE_IMAGES_PATH
    assert cfg.excluded_events == fetch_rides.EXCLUDED_EVENTS_PATH


def test_the_step_list_is_the_documented_pipeline():
    assert [name for name, _ in sync.STEPS] == [
        "fetch",
        "archive",
        "enrich_archive",
        "geocode",
        "maps",
        "promote",
        "export_ics",
    ]
