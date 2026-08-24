"""Tests for scripts/archive_events.py — the accumulating past-rides archive."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import archive_events  # noqa: E402

EASTERN = ZoneInfo("America/New_York")
# Pinned "now" so "past" never depends on the clock.
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=EASTERN)


def ride(uid: str, start: str, **extra) -> dict:
    base = {
        "uid": uid,
        "title": "Café ride",
        "start": start,
        "end": None,
        "date_display": "Saturday, May 2",
        "time_display": "11:00 am",
        "location": None,
        "location_hidden": False,
        "location_url": None,
        "description": "",
        "rsvp_url": None,
        "image": None,
    }
    base.update(extra)
    return base


def write_payload(path: Path, rides: list[dict]) -> Path:
    path.write_text(
        json.dumps({"updated_at": "x", "count": len(rides), "events": rides}),
        encoding="utf-8",
    )
    return path


# --- merge_archive ---


def test_only_past_rides_are_absorbed():
    sources = [[ride("a", "2026-05-02T11:00:00-04:00"), ride("b", "2026-07-04T11:00:00-04:00")]]
    merged = archive_events.merge_archive([], sources, NOW)
    assert [r["uid"] for r in merged] == ["a"]


def test_archive_entries_survive_a_source_that_forgot_them():
    """Partiful pruning its history must not erase rides we already archived."""
    archive = [ride("old", "2025-09-01T11:00:00-04:00")]
    merged = archive_events.merge_archive(archive, [[ride("a", "2026-05-02T11:00:00-04:00")]], NOW)
    assert [r["uid"] for r in merged] == ["old", "a"]


def test_archive_entries_are_kept_without_re_testing_now():
    """A future-dated ride already in the archive is not re-filtered out."""
    archive = [ride("weird", "2030-01-01T11:00:00-05:00")]
    merged = archive_events.merge_archive(archive, [], NOW)
    assert [r["uid"] for r in merged] == ["weird"]


def test_result_is_sorted_by_start():
    sources = [[
        ride("b", "2026-05-20T11:00:00-04:00"),
        ride("a", "2026-05-02T11:00:00-04:00"),
    ]]
    merged = archive_events.merge_archive([], sources, NOW)
    assert [r["start"] for r in merged] == sorted(r["start"] for r in merged)


def test_a_later_source_wins_field_by_field():
    old = [ride("a", "2026-05-02T11:00:00-04:00", title="Old name")]
    new = [[ride("a", "2026-05-02T11:00:00-04:00", title="Real name")]]
    merged = archive_events.merge_archive(old, new, NOW)
    assert len(merged) == 1
    assert merged[0]["title"] == "Real name"


def test_none_never_overwrites_an_existing_value():
    """The feed's past export has no image; the enriched archive entry keeps it."""
    photo = "https://example.invalid/ride.jpg"
    archived = [ride("a", "2026-05-02T11:00:00-04:00", image=photo, rsvp_url="https://p/e/a")]
    from_feed = [[ride("a", "2026-05-02T11:00:00-04:00")]]
    merged = archive_events.merge_archive(archived, from_feed, NOW)
    assert merged[0]["image"] == photo
    assert merged[0]["rsvp_url"] == "https://p/e/a"


def test_a_known_location_url_survives_a_source_without_one():
    """The pasted meeting-point link is kept when a re-export carries none.

    The feed's past export re-derives `location_url` every time, but an older
    archive entry may predate the key entirely — neither a null nor a missing
    key may drop a link we already have.
    """
    link = "https://maps.app.goo.gl/7zBmEn5ZTHEhJtSZ7"
    archived = [ride("a", "2026-05-02T11:00:00-04:00", location_url=link)]
    with_null = [[ride("a", "2026-05-02T11:00:00-04:00", location_url=None)]]
    assert archive_events.merge_archive(archived, with_null, NOW)[0]["location_url"] == link
    # A source that never learned about the field at all.
    without_key = [dict(ride("a", "2026-05-02T11:00:00-04:00"), title="Renamed")]
    without_key[0].pop("location_url", None)
    merged = archive_events.merge_archive(archived, [without_key], NOW)
    assert merged[0]["location_url"] == link
    assert merged[0]["title"] == "Renamed"


def test_a_missing_location_url_is_filled_in_from_a_source():
    """An archive entry from before the key gains it without a crash."""
    old_entry = ride("a", "2026-05-02T11:00:00-04:00")
    old_entry.pop("location_url", None)
    link = "https://maps.app.goo.gl/KafN4kidaBpozyew9?g_st=ic"
    fresh = [[ride("a", "2026-05-02T11:00:00-04:00", location_url=link)]]
    assert archive_events.merge_archive([old_entry], fresh, NOW)[0]["location_url"] == link


def test_rides_without_uids_fall_back_to_start_and_title():
    a = ride("", "2026-05-02T11:00:00-04:00", title="One")
    b = ride("", "2026-05-02T11:00:00-04:00", title="Two")
    merged = archive_events.merge_archive([], [[a, b]], NOW)
    assert len(merged) == 2


def test_naive_and_offset_starts_are_both_comparable():
    """A start without an offset is read as Eastern, not crashed on."""
    merged = archive_events.merge_archive([], [[ride("a", "2026-05-02T11:00:00")]], NOW)
    assert [r["uid"] for r in merged] == ["a"]


def test_unparseable_start_is_not_treated_as_past():
    merged = archive_events.merge_archive([], [[ride("a", "not a date")]], NOW)
    assert merged == []


# --- run() / the file layer ---


def test_run_creates_a_missing_archive(tmp_path):
    src = write_payload(tmp_path / "events.json", [ride("a", "2026-05-02T11:00:00-04:00")])
    archive = tmp_path / "events-past.json"
    assert archive_events.run(archive, [src], now=NOW) is True
    payload = json.loads(archive.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["events"][0]["uid"] == "a"


def test_run_is_idempotent(tmp_path):
    """A second run with nothing new must not rewrite the file (no churn commit)."""
    src = write_payload(tmp_path / "events.json", [ride("a", "2026-05-02T11:00:00-04:00")])
    archive = tmp_path / "events-past.json"
    archive_events.run(archive, [src], now=NOW)
    before = archive.read_text(encoding="utf-8")
    assert archive_events.run(archive, [src], now=NOW) is False
    assert archive.read_text(encoding="utf-8") == before


def test_run_reports_a_missing_source(tmp_path):
    with pytest.raises(archive_events.ArchiveError):
        archive_events.run(tmp_path / "past.json", [tmp_path / "nope.json"], now=NOW)


def test_run_rejects_a_non_payload_source(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"nope": true}', encoding="utf-8")
    with pytest.raises(archive_events.ArchiveError):
        archive_events.run(tmp_path / "past.json", [bad], now=NOW)


def test_main_exits_nonzero_on_a_missing_source(tmp_path, capsys):
    code = archive_events.main(["--archive", str(tmp_path / "past.json"), str(tmp_path / "nope.json")])
    assert code == 1
    assert "archive_events" in capsys.readouterr().err


def test_main_merges_sources_in_order(tmp_path):
    older = write_payload(
        tmp_path / "older.json", [ride("a", "2026-05-02T11:00:00-04:00", title="Old")]
    )
    newer = write_payload(
        tmp_path / "newer.json", [ride("a", "2026-05-02T11:00:00-04:00", title="New")]
    )
    archive = tmp_path / "events-past.json"
    assert archive_events.main(["--archive", str(archive), str(older), str(newer)]) == 0
    assert json.loads(archive.read_text(encoding="utf-8"))["events"][0]["title"] == "New"
