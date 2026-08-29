#!/usr/bin/env python3
"""Backfill images and route links onto archived rides, a few per run.

    python scripts/enrich_archive.py --limit 8 site/events-past.json

Only the *upcoming* list is enriched during a sync, so rides that reach
site/events-past.json straight from the feed's past export arrive bare — no
image, no routes, no map. The feed turned out to carry years of history (34
rides on the first run), and enriching all of them every 6 hours would be
dozens of page fetches for data that never changes.

So this walks the archive newest-first, takes the rides that have never been
looked at (`routes is None`), and enriches at most `--limit` of them. A few
syncs later the whole archive is filled in, and from then on the run is a no-op
because there is nothing left unchecked.

Rewrites the file only when something actually changed. Exits nonzero only if a
payload is missing or unparseable; enrichment failures are soft, as everywhere
else.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_rides  # noqa: E402

DEFAULT_LIMIT = 8


def pending(events: list) -> list:
    """Archived rides never enriched, newest first — recent history matters most."""
    unchecked = [
        ride for ride in events
        if isinstance(ride, dict) and ride.get("routes") is None
    ]
    unchecked.sort(key=lambda ride: str(ride.get("start") or ""), reverse=True)
    return unchecked


def enrich_payload(path: Path, limit: int = DEFAULT_LIMIT, **enrich_kwargs) -> int:
    """Enrich up to `limit` unchecked rides in `path`. Returns how many it tried."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"enrich_archive: could not read {path}: {exc}")
    events = payload.get("events")
    if not isinstance(events, list):
        raise SystemExit(f"enrich_archive: {path} has no `events` list")

    batch = pending(events)[:limit] if limit > 0 else []
    if not batch:
        return 0
    before = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    fetch_rides.enrich_rides(batch, **enrich_kwargs)
    after = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    if before != after:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return len(batch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payloads", nargs="+", metavar="PAYLOAD",
                        help="archive files to backfill")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"most rides to enrich per run (default: {DEFAULT_LIMIT})")
    args = parser.parse_args(argv)

    for payload in args.payloads:
        path = Path(payload)
        tried = enrich_payload(path, args.limit)
        remaining = len(pending(json.loads(path.read_text(encoding="utf-8"))["events"]))
        print(
            f"enrich_archive: looked at {tried} ride(s) in {path}; "
            f"{remaining} still unchecked"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
