#!/usr/bin/env python3
"""Merge rides that have already happened into site/events-past.json.

The site's calendar shows past rides as well as upcoming ones, but
site/events.json only ever holds the upcoming list — a ride vanishes from it
an hour after it starts (see GRACE_PERIOD). So the archive has to *accumulate*: it is the union of
everything it already held and every already-happened ride in the payload
files handed to it. That way history survives even if Partiful stops exporting
old events, which the feed gives no guarantee about.

    python scripts/archive_events.py --archive site/events-past.json \
        site/events.json "$RUNNER_TEMP/events-past.json"

Sources are ordered oldest → newest; a later source wins field by field, except
that a `null` never overwrites a value that is already there. That is what
keeps a ride's `image` after it moves into the past: it was enriched from its
Partiful event page while it was still upcoming, and the feed's own past-ride
export carries no photo.

Like promote_events.py this rewrites the archive only when the `events` list
actually changed, so the sync workflow doesn't commit a fresh timestamp every
6 hours. Exits 0 whether or not it wrote; nonzero only on real errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = REPO_ROOT / "site" / "events-past.json"
# The same grace hour fetch_rides.py keeps a just-started ride in the upcoming
# export for (a latecomer can still catch the group). It has to be the same
# number here: the sync feeds this script the *previous* site/events.json, so a
# shorter rule would archive a ride that the fresh fetch still lists as
# upcoming, and app.js — which just concatenates the archive with events.json —
# would draw it on the calendar twice, once dimmed and once live. This module
# is stdlib-only and can't import fetch_rides, so the constant is duplicated;
# tests/test_archive_events.py pins the two to each other.
GRACE_PERIOD = timedelta(hours=1)


class ArchiveError(Exception):
    """A source file could not be read as an events payload."""


def load_payload(path: Path, required: bool = True) -> dict:
    """Read an events payload. A missing optional file reads as empty."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if required:
            raise ArchiveError(f"{path} does not exist") from None
        return {"events": []}
    except (OSError, ValueError) as exc:
        raise ArchiveError(f"could not read {path}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ArchiveError(f"{path} is not an events payload (no `events` list)")
    return data


def ride_key(ride: dict) -> str:
    """Identity of a ride across syncs: its feed UID, else start + title."""
    uid = ride.get("uid")
    if uid:
        return str(uid)
    return f"{ride.get('start')}|{ride.get('title')}"


def merge_ride(old: dict, new: dict) -> dict:
    """`new` wins field by field, but never replaces a value with None.

    Rides come back from the feed stripped of anything the sync added later
    (most visibly `image`, backfilled from the ride's Partiful page while it
    was still upcoming), so a plain dict update would erase them.
    """
    merged = dict(old)
    for key, value in new.items():
        if value is None and merged.get(key) is not None:
            continue
        merged[key] = value
    return merged


def is_past(ride: dict, now: datetime) -> bool:
    """True when the ride's start is far enough behind us to be history.

    Not simply `start < now`: a ride inside its GRACE_PERIOD is still the one
    happening right now and still sits in site/events.json, so archiving it
    there and then would put it on the calendar twice. `start` is an ISO string
    that already carries its offset, so comparing the parsed values is
    timezone-correct wherever this runs.
    """
    start = ride.get("start")
    if not isinstance(start, str):
        return False
    try:
        moment = datetime.fromisoformat(start)
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOCAL_TZ)
    return moment + GRACE_PERIOD < now


def merge_archive(
    archive: list[dict], sources: list[list[dict]], now: datetime
) -> list[dict]:
    """Fold every already-happened ride from `sources` into `archive`.

    Rides already in the archive stay even if a source no longer mentions them
    — the feed pruning its history must not erase ours. Returns a new list
    sorted by start.
    """
    merged: dict[str, dict] = {}
    order: list[str] = []

    def absorb(rides: list[dict], past_only: bool) -> None:
        for ride in rides:
            if not isinstance(ride, dict):
                continue
            if past_only and not is_past(ride, now):
                continue
            key = ride_key(ride)
            if key in merged:
                merged[key] = merge_ride(merged[key], ride)
            else:
                merged[key] = dict(ride)
                order.append(key)

    # Whatever the archive holds is history by definition — never re-filter it
    # on `now`, or a clock skew could silently drop rides we already keep.
    absorb(archive, past_only=False)
    for rides in sources:
        absorb(rides, past_only=True)

    return sorted(
        (merged[key] for key in order),
        key=lambda ride: (str(ride.get("start") or ""), ride_key(ride)),
    )


def build_payload(rides: list[dict], now: datetime) -> dict:
    return {"updated_at": now.isoformat(), "count": len(rides), "events": rides}


def write_archive(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run(archive_path: Path, source_paths: list[Path], now: datetime | None = None) -> bool:
    """Update the archive from the sources. True when the file was rewritten."""
    now = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    existing = load_payload(archive_path, required=False)
    sources = [load_payload(path)["events"] for path in source_paths]
    rides = merge_archive(existing["events"], sources, now)
    if rides == existing["events"]:
        return False
    write_archive(build_payload(rides, now), archive_path)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        default=str(DEFAULT_ARCHIVE),
        help=f"the accumulating past-rides file (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "sources",
        nargs="+",
        metavar="SOURCE",
        help="events payload files to fold in, oldest first",
    )
    args = parser.parse_args(argv)

    archive_path = Path(args.archive)
    try:
        changed = run(archive_path, [Path(p) for p in args.sources])
    except ArchiveError as exc:
        print(f"archive_events: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"archive_events: could not write {archive_path}: {exc.strerror}", file=sys.stderr)
        return 1

    if changed:
        count = json.loads(archive_path.read_text(encoding="utf-8"))["count"]
        print(f"archive_events: {archive_path} now holds {count} past ride(s)")
    else:
        print("archive_events: no new past rides; keeping the committed file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
