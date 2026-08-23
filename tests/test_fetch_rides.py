"""Tests for scripts/fetch_rides.py — always offline, always on the fixture."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_rides  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample.ics"
EASTERN = ZoneInfo("America/New_York")
# Pinned "now": after the past event, well before the 2030 rides.
NOW = datetime(2025, 1, 1, 12, 0, tzinfo=EASTERN)


@pytest.fixture(scope="module")
def feed_bytes() -> bytes:
    return FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def rides(feed_bytes: bytes) -> list[dict]:
    return fetch_rides.parse_events(feed_bytes, now=NOW)


def test_keeps_only_the_two_future_rides(rides):
    assert [ride["uid"] for ride in rides] == [
        "evt-future-charles-loop@partiful.com",
        "evt-future-minuteman@partiful.com",
    ]


def test_past_event_is_dropped(rides):
    assert all("evt-past" not in ride["uid"] for ride in rides)


def test_cancelled_event_is_dropped(rides):
    """The Blue Hills ride is in 2030 but STATUS:CANCELLED."""
    assert all("blue-hills" not in ride["uid"] for ride in rides)


def test_sorted_by_start(rides):
    starts = [ride["start"] for ride in rides]
    assert starts == sorted(starts)


def test_rsvp_urls_extracted_despite_line_folding(rides):
    assert [ride["rsvp_url"] for ride in rides] == [
        "https://partiful.com/e/3mTnV6xJaQ9wLpEr",
        "https://partiful.com/e/5cXyB8kFgH2dNqUw",
    ]


def test_rsvp_line_stripped_from_description(rides):
    for ride in rides:
        assert "RSVP:" not in ride["description"]
        assert "partiful.com" not in ride["description"]
        assert ride["description"]


@pytest.mark.parametrize(
    "description, expected",
    [
        ("Ride then coffee.\n\nRSVP: https://partiful.com/e/abc123", "https://partiful.com/e/abc123"),
        ("rsvp:   https://partiful.com/e/abc123", "https://partiful.com/e/abc123"),
        ("See you there (RSVP: https://partiful.com/e/abc123).", "https://partiful.com/e/abc123"),
        ("RSVP at https://partiful.com/e/abc123", "https://partiful.com/e/abc123"),
        ("View this event on Partiful at https://partiful.com/e/abc123\n\nCome!", "https://partiful.com/e/abc123"),
        ("No link here at all.", None),
        ("", None),
    ],
)
def test_extract_rsvp_url(description, expected):
    assert fetch_rides.extract_rsvp_url(description) == expected


@pytest.mark.parametrize(
    "uid, expected",
    [
        ("TskpmnYxmCi7eGn1mb0G", "https://partiful.com/e/TskpmnYxmCi7eGn1mb0G"),
        ("evt-future-charles-loop@partiful.com", None),
        ("noend@example.com", None),
        ("https://partiful.com/e/abc123", None),
        ("", None),
        (None, None),
    ],
)
def test_derive_partiful_url(uid, expected):
    assert fetch_rides.derive_partiful_url(uid) == expected


def test_timezone_is_eastern_with_correct_offsets(rides):
    charles, minuteman = rides
    # Both fixture rides are in EDT (UTC-4), not UTC and not the runner's tz.
    assert charles["start"] == "2030-06-22T09:30:00-04:00"
    assert minuteman["start"] == "2030-07-06T10:00:00-04:00"
    assert datetime.fromisoformat(charles["start"]).utcoffset().total_seconds() == -4 * 3600


def test_end_time_extracted(rides):
    """The fixture carries DTEND on every event; it should flow through as `end`."""
    charles, minuteman = rides
    assert charles["end"] == "2030-06-22T12:00:00-04:00"
    assert minuteman["end"] == "2030-07-06T14:00:00-04:00"
    assert datetime.fromisoformat(charles["end"]).utcoffset().total_seconds() == -4 * 3600


def _real_feed(data: bytes):
    """Parse an inline feed at a fixed 'now', like the sync bot would."""
    return fetch_rides.parse_events(data, now=datetime(2025, 1, 1, tzinfo=EASTERN))


def test_real_partiful_rsvp_at_phrasing():
    """Current Partiful exports say 'RSVP at <url>' and use a bare UID."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:TskpmnYxmCi7eGn1mb0G\r\n"
        b"DTSTART;TZID=America/New_York:20300808T180000\r\n"
        b"SUMMARY:Dinner Party\r\n"
        b"DESCRIPTION:RSVP at https://partiful.com/e/TskpmnYxmCi7eGn1mb0G\\n\\n"
        b"You are cordially invited. Just showing up for the food is valid!\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = _real_feed(data)
    assert len(rides) == 1
    assert rides[0]["rsvp_url"] == "https://partiful.com/e/TskpmnYxmCi7eGn1mb0G"
    assert "RSVP at" not in rides[0]["description"]
    assert "partiful.com" not in rides[0]["description"]
    assert rides[0]["description"].startswith("You are cordially invited.")


def test_real_partiful_view_event_phrasing():
    """Some Partiful exports say 'View this event on Partiful at <url>'."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:LjbmPGgu1Z3Zc7bJTibI\r\n"
        b"DTSTART;TZID=America/New_York:20300622T093000\r\n"
        b"SUMMARY:Celebration\r\n"
        b"DESCRIPTION:View this event on Partiful at https://partiful.com/e/LjbmPGgu1Z3Zc7bJTibI\\n\\n"
        b"Come celebrate with us.\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = _real_feed(data)
    assert len(rides) == 1
    assert rides[0]["rsvp_url"] == "https://partiful.com/e/LjbmPGgu1Z3Zc7bJTibI"
    assert "Partiful at" not in rides[0]["description"]
    assert rides[0]["description"].startswith("Come celebrate with us.")


def test_rsvp_url_derived_from_bare_uid_without_link():
    """No link in the text at all → a bare Partiful UID still yields the page."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:Z50H1Zr8gbbyZtSyH75e\r\n"
        b"DTSTART;TZID=America/New_York:20300622T093000\r\n"
        b"SUMMARY:No link here\r\n"
        b"DESCRIPTION:Just ride details. See you at the start.\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = _real_feed(data)
    assert len(rides) == 1
    assert rides[0]["rsvp_url"] == "https://partiful.com/e/Z50H1Zr8gbbyZtSyH75e"


def test_rsvp_url_not_derived_from_suffixed_uid():
    """A descriptive '<name>@partiful.com' UID must not be treated as an id."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:evt-future-charles-loop@partiful.com\r\n"
        b"DTSTART;TZID=America/New_York:20300622T093000\r\n"
        b"SUMMARY:No RSVP line\r\n"
        b"DESCRIPTION:No link anywhere here.\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = _real_feed(data)
    assert len(rides) == 1
    assert rides[0]["rsvp_url"] is None


def test_clean_title_strips_partiful_suffix():
    """Partiful exports append ' | Partiful' to every title; the site shouldn't show it."""
    assert (
        fetch_rides._clean_title("The journey is really the best part | Partiful")
        == "The journey is really the best part"
    )
    assert fetch_rides._clean_title("Post PMC Celebration!! | Partiful") == "Post PMC Celebration!!"
    assert fetch_rides._clean_title("Salt Bread and Coffee pop-up | Partiful") == "Salt Bread and Coffee pop-up"
    assert fetch_rides._clean_title("Café Ride | partiful") == "Café Ride"  # case-insensitive
    assert fetch_rides._clean_title("No suffix here") == "No suffix here"
    assert fetch_rides._clean_title("") == ""


def test_clean_title_collapses_whitespace():
    """Real exports carry stray runs of spaces; collapse them to one."""
    assert (
        fetch_rides._clean_title("Boston Cafe Bikers        Ice Cream Crawl | Partiful")
        == "Boston Cafe Bikers Ice Cream Crawl"
    )
    assert fetch_rides._clean_title("  Leading and  trailing  ") == "Leading and trailing"


def test_clean_description_collapses_blank_lines():
    """3+ newlines (e.g. left after the stripped invite line) read as one break."""
    dirty = "RSVP at https://partiful.com/e/abc\n\nYou are invited!\n\n\n\nBring a lock."
    assert fetch_rides._clean_description(dirty) == "You are invited!\n\nBring a lock."


def test_clean_description_keeps_single_paragraph_break():
    """One blank line between paragraphs is legitimate prose, not cruft."""
    assert (
        fetch_rides._clean_description("Meet at the café.\n\nThen we ride.")
        == "Meet at the café.\n\nThen we ride."
    )
    assert fetch_rides._clean_description("Just prose.") == "Just prose."


def test_real_partiful_title_suffix_stripped():
    """A real Partiful-style title comes out clean end-to-end."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:gRzH7L3EoMRl3q8pl7OS\r\n"
        b"DTSTART;TZID=America/New_York:20300622T093000\r\n"
        b"SUMMARY:The journey is really the best part | Partiful\r\n"
        b"DESCRIPTION:View this event on Partiful at https://partiful.com/e/gRzH7L3EoMRl3q8pl7OS\\n\\n"
        b"Yippee! Another Saturday, another ride.\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = _real_feed(data)
    assert len(rides) == 1
    assert rides[0]["title"] == "The journey is really the best part"
    assert "Partiful" not in rides[0]["title"]
    assert rides[0]["description"] == "Yippee! Another Saturday, another ride."


def test_fixture_title_suffix_stripped(rides):
    """The fixture's Charles title carries ' | Partiful'; it must come out clean."""
    charles = rides[0]
    assert charles["title"] == "Charles River Loop → Tatte"
    assert charles["title"].endswith("Partiful") is False


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Location available once RSVP'd", ("", True)),
        ("location available once rsvp'd", ("", True)),  # case-insensitive
        ("Location available after RSVP", ("", True)),   # variant wording
        (
            "Tatte Bakery & Café, 1003 Beacon St, Brookline, MA 02446",
            ("Tatte Bakery & Café, 1003 Beacon St, Brookline, MA 02446", False),
        ),
        ("   ", ("", False)),
        ("", ("", False)),
    ],
)
def test_clean_location(raw, expected):
    assert fetch_rides._clean_location(raw) == expected


def test_hidden_placeholder_cleaned_from_fixture(rides):
    """Partiful hides some addresses until RSVP; the placeholder must not leak."""
    charles, minuteman = rides
    assert charles["location"] == "Tatte Bakery & Café, 1003 Beacon St, Brookline, MA 02446"
    assert charles["location_hidden"] is False
    assert minuteman["location"] is None
    assert minuteman["location_hidden"] is True
    # The placeholder text never reaches events.json / the site.
    assert all("RSVP'd" not in (ride["location"] or "") for ride in rides)


def test_real_partiful_hidden_location():
    """A hidden address exports as the placeholder; parse it to null + flag."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:HddenL0c8Zc7bJTibI\r\n"
        b"DTSTART;TZID=America/New_York:20300808T180000\r\n"
        b"SUMMARY:Salt Bread and Coffee pop-up\r\n"
        b"LOCATION:Location available once RSVP'd\r\n"
        b"DESCRIPTION:RSVP at https://partiful.com/e/HddenL0c8Zc7bJTibI\\n\\n"
        b"Ride with us from Boston Common.\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = fetch_rides.parse_events(data, now=datetime(2029, 1, 1, tzinfo=EASTERN))
    assert len(rides) == 1
    assert rides[0]["location"] is None
    assert rides[0]["location_hidden"] is True


def test_missing_dtend_yields_null_end():
    """A feed event with no DTEND must still parse, with `end` null."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:noend@example.com\r\n"
        b"DTSTART;TZID=America/New_York:20300101T100000\r\n"
        b"SUMMARY:No End\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = fetch_rides.parse_events(data, now=datetime(2029, 1, 1, tzinfo=EASTERN))
    assert len(rides) == 1
    assert rides[0]["uid"] == "noend@example.com"
    assert rides[0]["end"] is None


def test_display_strings_are_precomputed(rides):
    charles, minuteman = rides
    assert charles["date_display"] == "Saturday, June 22"
    assert charles["time_display"] == "9:30 am"
    assert minuteman["date_display"] == "Saturday, July 6"
    assert minuteman["time_display"] == "10:00 am"


def test_non_ascii_survives_the_round_trip(rides):
    assert "→" in rides[0]["title"]
    assert "Café" in rides[0]["location"]


def test_now_boundary_keeps_events_starting_exactly_now(feed_bytes):
    exact = datetime(2030, 6, 22, 9, 30, tzinfo=EASTERN)
    kept = fetch_rides.parse_events(feed_bytes, now=exact)
    assert len(kept) == 2
    just_after = datetime(2030, 6, 22, 9, 31, tzinfo=EASTERN)
    assert len(fetch_rides.parse_events(feed_bytes, now=just_after)) == 1


def test_all_events_in_the_past_yields_empty_list(feed_bytes):
    assert fetch_rides.parse_events(feed_bytes, now=datetime(2031, 1, 1, tzinfo=EASTERN)) == []


def test_malformed_feed_raises_feed_error():
    with pytest.raises(fetch_rides.FeedError):
        fetch_rides.parse_events(b"this is not an ics file at all")


def test_build_payload_shape(rides):
    payload = fetch_rides.build_payload(rides, now=NOW)
    assert payload["count"] == 2
    assert payload["updated_at"] == NOW.isoformat()
    assert payload["events"] == rides


def test_image_is_null_without_sidecar(rides):
    """No images passed in → every ride carries image: None."""
    assert all(ride["image"] is None for ride in rides)


def test_image_merged_from_sidecar(feed_bytes):
    images = {"evt-future-charles-loop@partiful.com": "https://example.com/img/charles.jpg"}
    rides = fetch_rides.parse_events(feed_bytes, now=NOW, images=images)
    charles, minuteman = rides
    assert charles["image"] == "https://example.com/img/charles.jpg"
    assert minuteman["image"] is None


# --- Event-page image enrichment -------------------------------------------

EVENT_PAGE = REPO_ROOT / "tests" / "fixtures" / "event-page.html"
CHARLES_IMAGE = (
    "https://firebasestorage.googleapis.com/v0/b/getpartiful.appspot.com/o/"
    "rides%2Fcharles-loop.jpg?alt=media"
)


def test_extract_event_image_from_fixture_page():
    html = EVENT_PAGE.read_text(encoding="utf-8")
    assert fetch_rides._extract_event_image(html) == CHARLES_IMAGE


def test_extract_event_image_string_image():
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"event":{"image":"' + CHARLES_IMAGE + '"}}}}'
        "</script>"
    )
    assert fetch_rides._extract_event_image(html) == CHARLES_IMAGE


def test_extract_event_image_falls_back_to_first_firebase_url():
    """No __NEXT_DATA__ → a Firebase Storage URL anywhere in the page wins."""
    html = (
        '<img src="https://firebasestorage.googleapis.com/v0/b/getpartiful'
        '.appspot.com/o/a%2Fb.jpg?alt=media">'
    )
    assert fetch_rides._extract_event_image(html) == (
        "https://firebasestorage.googleapis.com/v0/b/getpartiful.appspot.com/o/a%2Fb.jpg?alt=media"
    )


def test_extract_event_image_blank_page_is_none():
    assert fetch_rides._extract_event_image("<html><body></body></html>") is None


def _fake_event_page(url: str) -> str:
    if url == "https://partiful.com/e/3mTnV6xJaQ9wLpEr":
        return EVENT_PAGE.read_text(encoding="utf-8")
    raise fetch_rides.requests.RequestException(f"no page at {url}")


def test_enrich_rides_sets_image_on_fixture_ride(feed_bytes):
    """The sync pipeline over the fixture + a stubbed transport backfills image."""
    rides = fetch_rides.parse_events(feed_bytes, now=NOW)
    assert all(ride["image"] is None for ride in rides)
    assert fetch_rides.enrich_rides(rides, fetch_page=_fake_event_page) == 1
    charles, minuteman = rides
    assert charles["image"] == CHARLES_IMAGE
    assert minuteman["image"] is None  # page fetch failed → soft, stays null


def test_enrich_rides_sidecar_wins(feed_bytes):
    """An explicit ride_images.json entry is never overwritten by enrichment."""
    rides = fetch_rides.parse_events(
        feed_bytes,
        now=NOW,
        images={
            "evt-future-charles-loop@partiful.com": "https://example.com/img/curated.jpg"
        },
    )
    charles, minuteman = rides
    assert fetch_rides.enrich_rides(rides, fetch_page=_fake_event_page) == 0
    assert charles["image"] == "https://example.com/img/curated.jpg"
    assert minuteman["image"] is None


def test_enrich_rides_fetch_failure_is_soft(feed_bytes):
    def boom(url: str) -> str:
        raise fetch_rides.requests.RequestException("nope")

    rides = fetch_rides.parse_events(feed_bytes, now=NOW)
    assert fetch_rides.enrich_rides(rides, fetch_page=boom) == 0
    assert all(ride["image"] is None for ride in rides)


def test_enrich_rides_skips_rides_without_event_page():
    """No rsvp link and a non-id UID → there is no page to fetch."""
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        b"BEGIN:VEVENT\r\nUID:evt-no-link@partiful.com\r\n"
        b"DTSTART;TZID=America/New_York:20300101T100000\r\n"
        b"SUMMARY:No Link\r\n"
        b"DESCRIPTION:No RSVP line at all.\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    rides = fetch_rides.parse_events(data, now=datetime(2029, 1, 1, tzinfo=EASTERN))
    assert rides[0]["rsvp_url"] is None

    def unreachable(url: str) -> str:  # pragma: no cover - must not be called
        raise AssertionError("fetch_page must not be called for a ride with no page")

    assert fetch_rides.enrich_rides(rides, fetch_page=unreachable) == 0
    assert rides[0]["image"] is None


def test_main_enriches_only_on_live_feed(tmp_path, monkeypatch):
    """--ics-file stays offline; only a network feed run reaches event pages."""
    out = tmp_path / "events.json"
    calls = []
    monkeypatch.setattr(
        fetch_rides, "enrich_rides", lambda rides: calls.append(rides) or len(rides)
    )
    assert fetch_rides.main(["--ics-file", str(FIXTURE), "--out", str(out)]) == 0
    assert calls == []


def test_main_enriches_when_feed_comes_from_live_url(tmp_path, monkeypatch):
    out = tmp_path / "events.json"
    enriched = []
    monkeypatch.setattr(
        fetch_rides, "enrich_rides", lambda rides: enriched.append(rides) or 2
    )
    monkeypatch.setattr(fetch_rides, "fetch_ics", lambda url: FIXTURE.read_bytes())
    monkeypatch.setenv("PARTIFUL_ICS_URL", "https://partiful.example.invalid/feed.ics")
    assert fetch_rides.main(["--out", str(out)]) == 0
    assert len(enriched) == 1
    assert [ride["uid"] for ride in enriched[0]] == [
        "evt-future-charles-loop@partiful.com",
        "evt-future-minuteman@partiful.com",
    ]


def test_load_ride_images_missing_file_is_empty(tmp_path):
    assert fetch_rides.load_ride_images(tmp_path / "nope.json") == {}


def test_load_ride_images_valid_object(tmp_path):
    sidecar = tmp_path / "ride_images.json"
    sidecar.write_text('{"abc@partiful.com": "https://example.com/img/a.jpg"}', encoding="utf-8")
    assert fetch_rides.load_ride_images(sidecar) == {
        "abc@partiful.com": "https://example.com/img/a.jpg"
    }


def test_load_ride_images_malformed_raises(tmp_path):
    sidecar = tmp_path / "ride_images.json"
    sidecar.write_text("{not json", encoding="utf-8")
    with pytest.raises(fetch_rides.FeedError):
        fetch_rides.load_ride_images(sidecar)


def test_load_ride_images_non_object_raises(tmp_path):
    sidecar = tmp_path / "ride_images.json"
    sidecar.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(fetch_rides.FeedError):
        fetch_rides.load_ride_images(sidecar)


def test_main_writes_image_from_sidecar(tmp_path):
    sidecar = tmp_path / "ride_images.json"
    sidecar.write_text(
        '{"evt-future-charles-loop@partiful.com": "https://example.com/img/c.jpg"}',
        encoding="utf-8",
    )
    out = tmp_path / "events.json"
    assert fetch_rides.main(
        ["--ics-file", str(FIXTURE), "--ride-images", str(sidecar), "--out", str(out)]
    ) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["events"][0]["image"] == "https://example.com/img/c.jpg"
    assert payload["events"][1]["image"] is None


def test_main_writes_expected_json(tmp_path):
    out = tmp_path / "nested" / "events.json"
    assert fetch_rides.main(["--ics-file", str(FIXTURE), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["count"] == 2
    assert payload["events"][0]["title"] == "Charles River Loop → Tatte"
    assert payload["events"][0]["rsvp_url"].startswith("https://partiful.com/e/")


def test_main_exits_nonzero_on_malformed_feed(tmp_path, capsys):
    bad = tmp_path / "bad.ics"
    bad.write_text("BEGIN:VCALENDAR\nthis is broken\n", encoding="utf-8")
    out = tmp_path / "events.json"
    assert fetch_rides.main(["--ics-file", str(bad), "--out", str(out)]) == 1
    assert not out.exists()
    assert "fetch_rides:" in capsys.readouterr().err


def test_main_exits_nonzero_on_missing_file(tmp_path):
    assert fetch_rides.main(["--ics-file", str(tmp_path / "nope.ics")]) == 1


def test_main_exits_nonzero_without_env_var(monkeypatch, capsys):
    monkeypatch.delenv("PARTIFUL_ICS_URL", raising=False)
    assert fetch_rides.main([]) == 1
    assert "PARTIFUL_ICS_URL" in capsys.readouterr().err


def test_feed_url_never_appears_in_fetch_errors(monkeypatch):
    """A network failure must not leak the secret URL into the message."""
    secret = "https://partiful.com/secret-feed-token/calendar.ics"

    class Boom(fetch_rides.requests.RequestException):
        def __str__(self) -> str:  # pragma: no cover - defensive
            return f"connection failed for url: {secret}"

    monkeypatch.setattr(
        fetch_rides.requests, "get", lambda *a, **kw: (_ for _ in ()).throw(Boom())
    )
    with pytest.raises(fetch_rides.FeedError) as excinfo:
        fetch_rides.fetch_ics(secret)
    assert secret not in str(excinfo.value)
    assert "secret-feed-token" not in str(excinfo.value)


def test_scrub_removes_urls():
    scrubbed = fetch_rides.scrub("failed: webcal://p.com/a.ics and https://p.com/b")
    assert "p.com" not in scrubbed
    assert "<url redacted>" in scrubbed


# --- past rides: the feed's already-happened events and the archive ---


@pytest.fixture(scope="module")
def past_rides(feed_bytes: bytes) -> list[dict]:
    return fetch_rides.parse_events(feed_bytes, now=NOW, past=True)


def test_past_mode_returns_only_the_past_ride(past_rides):
    assert [ride["uid"] for ride in past_rides] == [
        "evt-past-jamaica-pond@partiful.com"
    ]


def test_past_mode_still_drops_cancelled_events(feed_bytes):
    """The cancelled Blue Hills ride is in 2030 — past-mode from 2031 skips it."""
    later = datetime(2031, 1, 1, 12, 0, tzinfo=EASTERN)
    uids = [r["uid"] for r in fetch_rides.parse_events(feed_bytes, now=later, past=True)]
    assert all("blue-hills" not in uid for uid in uids)
    assert len(uids) == 3  # the past ride plus the two 2030 rides


def test_past_and_upcoming_partition_the_feed(feed_bytes, rides, past_rides):
    """Every non-cancelled event lands in exactly one of the two lists."""
    both = {r["uid"] for r in rides} & {r["uid"] for r in past_rides}
    assert both == set()
    assert len(rides) + len(past_rides) == 3


def test_past_ride_carries_the_same_shape(past_rides):
    ride = past_rides[0]
    assert set(ride) == {
        "uid", "title", "start", "end", "date_display", "time_display",
        "location", "location_hidden", "description", "rsvp_url", "image",
    }


def test_main_writes_the_past_file_only_when_asked(tmp_path):
    out = tmp_path / "events.json"
    past_out = tmp_path / "events-past.json"
    assert fetch_rides.main(["--ics-file", str(FIXTURE), "--out", str(out)]) == 0
    assert not past_out.exists()
    assert fetch_rides.main(
        ["--ics-file", str(FIXTURE), "--out", str(out), "--past-out", str(past_out)]
    ) == 0
    payload = json.loads(past_out.read_text(encoding="utf-8"))
    assert payload["count"] == len(payload["events"]) == 1
    assert payload["events"][0]["uid"] == "evt-past-jamaica-pond@partiful.com"
