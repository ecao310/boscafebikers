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
        ("No link here at all.", None),
        ("", None),
    ],
)
def test_extract_rsvp_url(description, expected):
    assert fetch_rides.extract_rsvp_url(description) == expected


def test_timezone_is_eastern_with_correct_offsets(rides):
    charles, minuteman = rides
    # Both fixture rides are in EDT (UTC-4), not UTC and not the runner's tz.
    assert charles["start"] == "2030-06-22T09:30:00-04:00"
    assert minuteman["start"] == "2030-07-06T10:00:00-04:00"
    assert datetime.fromisoformat(charles["start"]).utcoffset().total_seconds() == -4 * 3600


def test_display_strings_are_precomputed(rides):
    charles, minuteman = rides
    assert charles["date_display"] == "Saturday, June 22"
    assert charles["time_display"] == "9:30 am"
    assert minuteman["date_display"] == "Saturday, July 6"
    assert minuteman["time_display"] == "10:00 am"


def test_non_ascii_survives_the_round_trip(rides):
    assert "→" in rides[0]["title"]
    assert "Café" in rides[1]["location"]


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
