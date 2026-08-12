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
# Optional sidecar mapping ride UID -> image URL, merged into each event as
# `image`. The ICS feed itself carries no photos, so this is how the organizer
# attaches a picture to a ride without touching the site code.
RIDE_IMAGES_PATH = REPO_ROOT / "scripts" / "ride_images.json"
FETCH_TIMEOUT_SECONDS = 30

# RSVP links sit in DESCRIPTION in one of three phrasings — "RSVP: <url>",
# "RSVP at <url>", or "View this event on Partiful at <url>" — and are
# line-folded across the phrase / URL boundary. Capture the URL regardless.
RSVP_RE = re.compile(
    r"(?:RSVP\s*(?::|\bat\b)|View this event on Partiful at)\s*(https?://\S+)",
    re.IGNORECASE,
)
# Partiful's ICS export uses the bare event id as the UID; the event's page is
# https://partiful.com/e/<id>. Used as a fallback when no link is in the text.
PARTIFUL_EVENT_URL = "https://partiful.com/e/"
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


def derive_partiful_url(uid: str) -> str | None:
    """Build the Partiful event URL from a bare UID.

    Partiful's ICS export uses the event id as a bare UID (no ``@…``). Leave
    descriptive or suffixed UIDs (e.g. ``evt-…@partiful.com``) alone — those
    aren't event ids, and a description usually carries the link anyway.
    """
    if not uid or "@" in uid or uid.startswith(("http://", "https://", "webcal://")):
        return None
    return PARTIFUL_EVENT_URL + uid


def load_ride_images(path: Path | None = None) -> dict:
    """Read the optional UID → image-URL sidecar. A missing file means "{}"."""
    path = Path(path) if path is not None else RIDE_IMAGES_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise FeedError(f"could not parse ride images ({path.name}): {scrub(exc)}") from None
    if not isinstance(data, dict):
        raise FeedError(f"ride images ({path.name}) must be a JSON object of UID → URL")
    return data


def _strip_rsvp(description: str) -> str:
    """The blurb without the RSVP/invite line (any of the three phrasings)."""
    return RSVP_RE.sub("", description).strip()


# Partiful appends " | Partiful" to every exported event title; strip it so the
# site shows the organizer's actual name. Real exports also carry stray runs of
# whitespace ("Boston Cafe Bikers        Ice Cream Crawl"), so tidy those too.
TITLE_SUFFIX_RE = re.compile(r"\s*\|\s*Partiful\s*$", re.IGNORECASE)


def _clean_title(title: str) -> str:
    """Strip Partiful's ' | Partiful' title suffix and collapse whitespace."""
    return re.sub(r"\s+", " ", TITLE_SUFFIX_RE.sub("", title)).strip()


def _clean_description(description: str) -> str:
    """Drop the RSVP/invite line, trim lines, and collapse runs of blank lines.

    Partiful prose is plain paragraphs; 3+ newlines (e.g. after the stripped
    invite line) should read as a single paragraph break, not a ragged gap.
    """
    body = _strip_rsvp(description)
    lines: list[str] = []
    blank = False
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            if not blank:
                lines.append("")
            blank = True
        else:
            lines.append(line)
            blank = False
    return "\n".join(lines).strip()


def parse_events(
    data: bytes, now: datetime | None = None, images: dict | None = None
) -> list[dict]:
    """Parse feed bytes into a sorted list of upcoming, non-cancelled rides.

    `images` is the optional UID → image-URL sidecar; each ride carries its
    photo URL as `image` (None when absent).
    """
    images = images or {}
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
        uid = _text(component, "UID")
        description = _text(component, "DESCRIPTION")
        dtend = component.get("DTEND")
        rides.append(
            {
                "uid": uid,
                "title": _clean_title(_text(component, "SUMMARY")) or "Café ride",
                "start": start.isoformat(),
                # End time is optional; the site's "add to calendar" ICS needs it
                # to block out the right slot, but not every feed event has one.
                "end": _as_local_datetime(dtend.dt).isoformat() if dtend is not None else None,
                "date_display": f"{start:%A, %B} {start.day}",
                "time_display": f"{start:%-I:%M %p}".replace("AM", "am").replace("PM", "pm"),
                "location": _text(component, "LOCATION"),
                "description": _clean_description(description),
                "rsvp_url": extract_rsvp_url(description) or derive_partiful_url(uid),
                "image": images.get(uid),
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
    parser.add_argument(
        "--ride-images",
        default=str(RIDE_IMAGES_PATH),
        help=f"UID → image-URL sidecar JSON (default: {RIDE_IMAGES_PATH})",
    )
    args = parser.parse_args(argv)

    try:
        data = load_source(args)
        rides = parse_events(data, images=load_ride_images(args.ride_images))
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
