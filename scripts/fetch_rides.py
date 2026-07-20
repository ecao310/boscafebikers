#!/usr/bin/env python3
"""Fetch the Partiful ICS feed and write upcoming rides to site/events.json.

The feed URL comes from the PARTIFUL_ICS_URL env var and is never printed —
not in logs, not in error messages. For local runs and tests, point the script
at a file instead:

    python scripts/fetch_rides.py --ics-file tests/fixtures/sample.ics

Exits nonzero on any fetch or parse failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

LOCAL_TZ = ZoneInfo("America/New_York")
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "site" / "events.json"
FETCH_TIMEOUT_SECONDS = 30

# RSVP links sit at the end of DESCRIPTION as "RSVP: https://partiful.com/e/<id>".
RSVP_RE = re.compile(r"RSVP:\s*(https?://\S+)", re.IGNORECASE)
# Anything that looks like a URL, so it can be scrubbed from error text.
URL_RE = re.compile(r"\b(?:webcal|https?)://\S+", re.IGNORECASE)


class FeedError(Exception):
    """Fetching or parsing the feed failed."""


def scrub(text: object) -> str:
    """Strip URLs out of arbitrary text so the secret feed URL never leaks."""
    return URL_RE.sub("<url redacted>", str(text))


def fetch_ics(url: str) -> bytes:
    """Download the feed. Raises FeedError with a URL-free message."""
    try:
        response = requests.get(
            url,
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "boscafebikers-sync/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # Never echo the exception text: requests embeds the request URL (and
        # therefore the secret feed URL) in most of its messages.
        detail = type(exc).__name__
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status is not None:
            detail += f", HTTP {status}"
        raise FeedError(f"could not fetch the ICS feed ({detail})") from None
    if not response.content.strip():
        raise FeedError("the ICS feed was empty")
    return response.content


def _as_local_datetime(value: object) -> datetime:
    """Normalise a DTSTART value to an aware America/New_York datetime."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date):
        # All-day event: treat it as starting at midnight local time.
        moment = datetime(value.year, value.month, value.day)
    else:
        raise FeedError(f"unsupported DTSTART value: {type(value).__name__}")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOCAL_TZ)
    return moment.astimezone(LOCAL_TZ)


def _text(component, key: str) -> str:
    value = component.get(key)
    return "" if value is None else str(value).strip()


def extract_rsvp_url(description: str) -> str | None:
    match = RSVP_RE.search(description)
    return match.group(1).rstrip(".,);") if match else None


def _strip_rsvp(description: str) -> str:
    """The blurb without the trailing 'RSVP: <url>' line."""
    return RSVP_RE.sub("", description).strip()


def parse_events(data: bytes, now: datetime | None = None) -> list[dict]:
    """Parse feed bytes into a sorted list of upcoming, non-cancelled rides."""
    now = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    try:
        calendar = Calendar.from_ical(data)
    except Exception as exc:  # icalendar raises bare ValueError subclasses
        raise FeedError(f"could not parse the ICS feed: {scrub(exc)}") from None

    rides = []
    for component in calendar.walk("VEVENT"):
        if _text(component, "STATUS").upper() == "CANCELLED":
            continue
        dtstart = component.get("DTSTART")
        if dtstart is None:
            raise FeedError("an event in the feed has no DTSTART")
        start = _as_local_datetime(dtstart.dt)
        if start < now:
            continue
        description = _text(component, "DESCRIPTION")
        rides.append(
            {
                "uid": _text(component, "UID"),
                "title": _text(component, "SUMMARY") or "Café ride",
                "start": start.isoformat(),
                "date_display": f"{start:%A, %B} {start.day}",
                "time_display": f"{start:%-I:%M %p}".replace("AM", "am").replace("PM", "pm"),
                "location": _text(component, "LOCATION"),
                "description": _strip_rsvp(description),
                "rsvp_url": extract_rsvp_url(description),
            }
        )

    rides.sort(key=lambda ride: ride["start"])
    return rides


def build_payload(rides: list[dict], now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    return {
        "updated_at": now.isoformat(),
        "count": len(rides),
        "events": rides,
    }


def write_events(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_source(args: argparse.Namespace) -> bytes:
    if args.ics_file:
        path = Path(args.ics_file)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise FeedError(f"could not read {path}: {exc.strerror}") from None
    url = os.environ.get("PARTIFUL_ICS_URL", "").strip()
    if not url:
        raise FeedError(
            "PARTIFUL_ICS_URL is not set (or pass --ics-file for a local feed)"
        )
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    return fetch_ics(url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ics-file",
        help="read the feed from this file instead of PARTIFUL_ICS_URL",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUTPUT),
        help=f"where to write the JSON (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    try:
        data = load_source(args)
        rides = parse_events(data)
    except FeedError as exc:
        print(f"fetch_rides: {exc}", file=sys.stderr)
        return 1

    payload = build_payload(rides)
    try:
        write_events(payload, Path(args.out))
    except OSError as exc:
        print(f"fetch_rides: could not write {args.out}: {exc.strerror}", file=sys.stderr)
        return 1

    print(f"fetch_rides: wrote {len(rides)} upcoming ride(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
