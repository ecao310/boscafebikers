#!/usr/bin/env python3
"""Run the whole ride-data sync in one process, in the one order that works.

    python scripts/sync.py --data-dir _data      # on the sync runner
    python scripts/sync.py --data-dir site       # locally, after scripts/pull_data.sh

Fetch the feed, absorb the rides that have already happened, backfill a few
archived ones, geocode any new café, draw the maps that are missing, publish
the upcoming list, re-export the public calendar — then write only the files
whose content actually changed. A quiet sync writes zero bytes, which is the
property the workflow's "commit if changed" guard depends on.

The order used to live in the YAML of the sync workflow, where nothing could
test it. It lives in ``STEPS`` now, and tests/test_sync.py reorders that tuple
to prove each rule still bites:

* **archive before promote** — the archive is merged from the *previously*
  committed events.json, so a ride that has since started is kept even if
  Partiful already dropped it from the feed.
* **maps before promote** — render_route_maps adds ``map_image``, which a fresh
  fetch never carries; add it after publishing and the committed file can never
  equal the next fetch, so every run commits a new ``updated_at`` forever.
* **the ICS export after promote** — its DTSTAMP comes from the payload's
  ``updated_at``, which is stamped fresh every run. Exported from the freshly
  fetched payload the calendar would churn every 6 hours; exported from the
  published events.json it only moves when the rides do.

Offline: ``--ics-file`` reads a local feed and makes zero network calls (no
enrichment, no geocoding, no router, no tiles), exactly like
``fetch_rides.py --ics-file``. Tests get the same offline run *with* the
enrichment steps by injecting stubs through ``run()``'s keyword seams.

The feed URL comes from PARTIFUL_ICS_URL and is never printed — not in logs,
not in error messages. Exits nonzero only when the feed can't be fetched or
parsed (or a local data file is malformed); an enrichment miss is soft, as
everywhere else in this pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import archive_events  # noqa: E402
import enrich_archive  # noqa: E402
import export_ics  # noqa: E402
import fetch_rides  # noqa: E402
import geocode_cafes  # noqa: E402
import promote_events  # noqa: E402
import render_route_maps  # noqa: E402
import route_map  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "site"
DEFAULT_URL_PREFIX = render_route_maps.DEFAULT_URL_PREFIX
DEFAULT_ENRICH_LIMIT = enrich_archive.DEFAULT_LIMIT
LOCAL_TZ = fetch_rides.LOCAL_TZ


class SyncError(Exception):
    """A local data file is malformed. Fatal, like a feed parse failure."""


# --------------------------------------------------------------------------
# Configuration


@dataclass
class Config:
    """Where the data lives and how this run behaves.

    Every published path hangs off ``data_dir``; there is deliberately no
    hard-coded ``site/`` below this class, so the data can move out of the code
    branch by pointing --data-dir somewhere else.
    """

    data_dir: Path = DEFAULT_DATA_DIR
    ics_file: Optional[Path] = None
    ride_images: Path = fetch_rides.RIDE_IMAGES_PATH
    excluded_events: Path = fetch_rides.EXCLUDED_EVENTS_PATH
    now: Optional[datetime] = None
    enrich_limit: int = DEFAULT_ENRICH_LIMIT
    url_prefix: str = DEFAULT_URL_PREFIX
    dry_run: bool = False

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.ics_file = Path(self.ics_file) if self.ics_file else None
        self.ride_images = Path(self.ride_images)
        self.excluded_events = Path(self.excluded_events)
        self.url_prefix = str(self.url_prefix).strip("/")
        now = self.now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=LOCAL_TZ)
        # One `now` for the whole run: computing it per step could drop (or
        # duplicate) a ride that starts between two of them.
        self.now = now.astimezone(LOCAL_TZ)

    @property
    def events_path(self) -> Path:
        return self.data_dir / "events.json"

    @property
    def archive_path(self) -> Path:
        return self.data_dir / "events-past.json"

    @property
    def cafe_points_path(self) -> Path:
        return self.data_dir / "cafe-points.json"

    @property
    def rides_ics_path(self) -> Path:
        return self.data_dir / "rides.ics"

    @property
    def maps_dir(self) -> Path:
        return self.data_dir / "maps"

    @property
    def offline(self) -> bool:
        """A --ics-file run: the fixture UIDs aren't real Partiful event ids."""
        return self.ics_file is not None


def _no_network(*_args, **_kwargs):
    """Stand-in for a link resolver on an offline run.

    ValueError is what ``rides_routes`` already treats as "not a route", so an
    offline run simply finds no routes instead of failing.
    """
    raise ValueError("offline run: no network")


def _no_length(_points) -> None:
    """Stand-in for the router: ``measure_route`` expects None, never an error."""
    return None


@dataclass
class Seams:
    """The network calls, so a test can hand the run stubs instead.

    Each one falls back to its module's real implementation on a live run and
    is switched off on an offline (--ics-file) run — which is what keeps
    ``sync.py --ics-file`` byte-for-byte network-free while letting
    tests/test_sync.py exercise enrichment, geocoding and the maps offline.
    """

    fetch_page: Optional[Callable] = None
    resolve_link: Optional[Callable] = None
    fetch_length: Optional[Callable] = None
    fetch_geometry: Optional[Callable] = None
    fetch_tile: Optional[Callable] = None
    geocode_fetch: Optional[Callable] = None
    geocode_sleep: Optional[Callable] = None
    offline: bool = False

    @property
    def enrich_enabled(self) -> bool:
        return self.fetch_page is not None or not self.offline

    @property
    def geocode_enabled(self) -> bool:
        return self.geocode_fetch is not None or not self.offline

    @property
    def maps_enabled(self) -> bool:
        return self.fetch_geometry is not None or not self.offline

    def enrich_kwargs(self) -> dict:
        return {
            "fetch_page": self.fetch_page or fetch_rides._fetch_event_page,
            "resolve_link": self.resolve_link
            or (_no_network if self.offline else fetch_rides._resolve_link),
            "fetch_length": self.fetch_length
            or (_no_length if self.offline else fetch_rides._fetch_route_length),
        }

    def map_kwargs(self) -> dict:
        return {
            "fetch": self.fetch_geometry or render_route_maps.fetch_geometry,
            "fetch_tile": self.fetch_tile or render_route_maps.fetch_tile,
        }

    def geocode_kwargs(self) -> dict:
        return {
            "fetch": self.geocode_fetch or geocode_cafes.fetch_json,
            "sleep": self.geocode_sleep,
        }


# --------------------------------------------------------------------------
# Writes


class FileSet:
    """Every read and write of a published file goes through here.

    Two jobs. It compares against what was on disk when the run started, so
    "changed" means changed *for the commit*, however many steps touched a file
    on the way. And it holds an overlay of what has been written, so --dry-run
    can compute the whole run — including the steps that read back what an
    earlier step wrote — without touching the disk.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._original: dict = {}
        self._current: dict = {}

    def _seen(self, path) -> Path:
        path = Path(path)
        if path not in self._original:
            try:
                data = path.read_bytes()
            except OSError:
                data = None
            self._original[path] = data
            self._current[path] = data
        return path

    def read_bytes(self, path):
        return self._current[self._seen(path)]

    def read_text(self, path):
        data = self.read_bytes(path)
        return None if data is None else data.decode("utf-8")

    def read_json(self, path, default=None):
        text = self.read_text(path)
        if text is None:
            return default
        try:
            return json.loads(text)
        except ValueError:
            raise SyncError(f"{path} is not valid JSON") from None

    def write_bytes(self, path, data: bytes) -> bool:
        path = self._seen(path)
        if self._current[path] == data:
            return False
        self._current[path] = data
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return True

    def write_text(self, path, text: str) -> bool:
        return self.write_bytes(path, text.encode("utf-8"))

    def changed(self) -> list:
        """The paths whose bytes differ from what the run started with."""
        return sorted(
            (p for p in self._current if self._current[p] != self._original[p]),
            key=str,
        )


def _dump(payload: dict) -> str:
    """The JSON spelling every payload file in site/ is written with."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# The run


@dataclass
class Run:
    """One sync, start to finish: the data in flight plus what was written."""

    config: Config
    seams: Seams
    files: FileSet
    payload: Optional[dict] = None
    feed_past: list = field(default_factory=list)
    excluded: set = field(default_factory=set)
    archive: Optional[list] = None
    archive_before: list = field(default_factory=list)
    # True once events.json holds *this* run's upcoming payload. It is what
    # tells the later steps which file is "the published list" — and it is why
    # reordering the steps changes the result instead of quietly working.
    promoted: bool = False
    drawn: int = 0
    notes: list = field(default_factory=list)

    def note(self, message: str) -> None:
        self.notes.append(message)

    # -- the two payload files ------------------------------------------
    def save_events(self) -> bool:
        return self.files.write_text(self.config.events_path, _dump(self.payload))

    def save_archive(self) -> bool:
        """Write the archive, but only when the rides in it actually moved.

        The same no-churn rule as the upcoming list: a fresh ``updated_at`` on
        an unchanged archive would make the workflow commit every 6 hours.
        """
        if self.archive is None or self.archive == self.archive_before:
            return False
        payload = archive_events.build_payload(self.archive, self.config.now)
        return self.files.write_text(self.config.archive_path, _dump(payload))

    def write_map(self, target, svg: str) -> None:
        """The write seam render_route_maps draws each SVG through."""
        self.files.write_text(Path(target), svg)


# --- steps -----------------------------------------------------------------


def _load_feed(config: Config) -> bytes:
    """The feed bytes, from --ics-file or from the secret URL. Never logged."""
    return fetch_rides.load_source(
        Namespace(ics_file=str(config.ics_file) if config.ics_file else None)
    )


def step_fetch(run: Run) -> None:
    """Parse the feed into the upcoming payload and the feed's past export.

    Both passes share one `now`, so upcoming and past stay exact complements.
    """
    config = run.config
    data = _load_feed(config)
    images = fetch_rides.load_ride_images(config.ride_images)
    run.excluded = fetch_rides.load_excluded_events(config.excluded_events)
    rides = fetch_rides.parse_events(
        data, now=config.now, images=images, excluded=run.excluded
    )
    run.feed_past = fetch_rides.parse_events(
        data, now=config.now, images=images, past=True, excluded=run.excluded
    )
    if run.seams.enrich_enabled:
        backfilled = fetch_rides.enrich_rides(rides, **run.seams.enrich_kwargs())
        if backfilled:
            run.note(f"pulled images for {backfilled} upcoming ride(s)")
    run.payload = fetch_rides.build_payload(rides, now=config.now)
    run.note(
        f"{len(rides)} upcoming ride(s), {len(run.feed_past)} already-happened "
        "ride(s) in the feed"
    )


def step_archive(run: Run) -> None:
    """Fold the rides that have happened into the accumulating archive.

    Reads events.json *as it stands*, which is the whole point of running
    before the promote: it still holds the previous upcoming list, so a ride
    that has since started is archived even if the feed has dropped it.
    """
    config = run.config
    committed = run.files.read_json(config.events_path, default={}) or {}
    existing = run.files.read_json(config.archive_path, default={}) or {}
    run.archive_before = existing.get("events") or []
    sources = [committed.get("events") or [], run.feed_past]
    run.archive = archive_events.merge_archive(
        run.archive_before, sources, config.now, excluded=run.excluded
    )
    run.save_archive()
    run.note(f"archive holds {len(run.archive)} past ride(s)")


def step_enrich_archive(run: Run) -> None:
    """Backfill a few never-checked archived rides from their event pages."""
    if run.archive is None or not run.seams.enrich_enabled:
        return
    limit = run.config.enrich_limit
    batch = enrich_archive.pending(run.archive)[:limit] if limit > 0 else []
    if not batch:
        return
    fetch_rides.enrich_rides(batch, **run.seams.enrich_kwargs())
    run.save_archive()
    remaining = len(enrich_archive.pending(run.archive))
    run.note(f"looked at {len(batch)} archived ride(s); {remaining} still unchecked")


def step_geocode(run: Run) -> None:
    """Place any café we haven't got coordinates for yet.

    Reads the archive this run just updated *and* the fresh upcoming payload,
    so a café is already on the map by the time its ride moves into the past.
    Cannot churn: a location already in the cache (hit or recorded miss) is
    never queried again, and the file is rewritten only when the mapping moved.
    """
    if not run.seams.geocode_enabled:
        return
    config = run.config
    payloads = [run.payload or {}, {"events": run.archive or []}]
    locations = geocode_cafes.cafe_locations(payloads)
    try:
        cache = geocode_cafes.load_cache(config.cafe_points_path)
    except geocode_cafes.GeocodeError as exc:
        raise SyncError(str(exc)) from None
    stats = geocode_cafes.update_cache(locations, cache, **run.seams.geocode_kwargs())
    run.files.write_text(config.cafe_points_path, geocode_cafes.serialize(cache))
    if stats["queried"]:
        run.note(
            f"geocoded {stats['queried']} café location(s) "
            f"({stats['found']} found, {stats['missed']} missed, "
            f"{stats['deferred']} deferred)"
        )


def step_maps(run: Run) -> None:
    """Draw the route map of every ride that hasn't got a finished one.

    Idempotent: a ride whose SVG already carries its basemap is skipped and
    only re-pointed at it. The rides it touches gain ``map_image``, which is
    why this has to happen before the promote — see the module docstring.
    """
    if not run.seams.maps_enabled:
        return
    config = run.config
    kwargs = run.seams.map_kwargs()
    drawn = 0
    for rides in ((run.payload or {}).get("events") or [], run.archive or []):
        for ride in rides:
            if not isinstance(ride, dict):
                continue
            if render_route_maps.render_for_ride(
                ride,
                config.maps_dir,
                config.url_prefix,
                write=run.write_map,
                **kwargs,
            ):
                drawn += 1
    run.drawn = drawn
    run.save_archive()
    if run.promoted:
        # events.json already holds this payload, so the map_image just added
        # has to go in with it — which is exactly the churn the correct order
        # avoids, since the promote below would have carried it for free.
        run.save_events()
    if drawn:
        run.note(f"drew {drawn} route map(s)")


def step_promote(run: Run) -> None:
    """Publish the upcoming list — but only when the rides themselves moved."""
    config = run.config
    committed = run.files.read_json(config.events_path, default=None)
    current = committed.get("events") if isinstance(committed, dict) else None
    if promote_events.rides_changed(run.payload["events"], current):
        run.save_events()
    run.promoted = True


def step_export_ics(run: Run) -> None:
    """Re-export the public subscribable calendar from the published list.

    From the *published* file, never the fresh payload: DTSTAMP comes from
    ``updated_at``, so exporting the fetch would restamp rides.ics every run.
    """
    config = run.config
    payload = None
    if run.promoted:
        payload = run.files.read_json(config.events_path, default=None)
    if not isinstance(payload, dict):
        payload = run.payload or {}
    run.files.write_bytes(
        config.rides_ics_path, export_ics.build_calendar(payload).encode("utf-8")
    )


# The pipeline, as data. Reordering this tuple is how tests/test_sync.py shows
# each ordering rule earning its place; nothing else depends on the sequence.
STEPS = (
    ("fetch", step_fetch),
    ("archive", step_archive),
    ("enrich_archive", step_enrich_archive),
    ("geocode", step_geocode),
    ("maps", step_maps),
    ("promote", step_promote),
    ("export_ics", step_export_ics),
)


def run(
    config: Config,
    *,
    fetch_page: Optional[Callable] = None,
    resolve_link: Optional[Callable] = None,
    fetch_length: Optional[Callable] = None,
    fetch_geometry: Optional[Callable] = None,
    fetch_tile: Optional[Callable] = None,
    geocode_fetch: Optional[Callable] = None,
    geocode_sleep: Optional[Callable] = None,
    steps=None,
) -> Run:
    """Run the pipeline. Returns the finished Run (``.files.changed()`` etc.).

    The keyword arguments are the network seams — pass one and that call is
    stubbed, which is how the tests run the whole sync offline. ``steps``
    overrides ``STEPS`` for the ordering tests.
    """
    seams = Seams(
        fetch_page=fetch_page,
        resolve_link=resolve_link,
        fetch_length=fetch_length,
        fetch_geometry=fetch_geometry,
        fetch_tile=fetch_tile,
        geocode_fetch=geocode_fetch,
        geocode_sleep=geocode_sleep,
        offline=config.offline,
    )
    state = Run(config=config, seams=seams, files=FileSet(dry_run=config.dry_run))
    for _name, step in (steps or STEPS):
        step(state)
    return state


# --------------------------------------------------------------------------
# CLI


def parse_now(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--now needs an ISO timestamp, not {value!r}"
        ) from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOCAL_TZ)
    return moment.astimezone(LOCAL_TZ)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="where events.json, events-past.json, cafe-points.json, rides.ics "
        f"and maps/ live (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--ics-file",
        help="read the feed from this file instead of PARTIFUL_ICS_URL; makes "
        "the whole run offline (no enrichment, geocoding, router or tiles)",
    )
    parser.add_argument(
        "--ride-images",
        default=str(fetch_rides.RIDE_IMAGES_PATH),
        help=f"UID → image-URL sidecar (default: {fetch_rides.RIDE_IMAGES_PATH})",
    )
    parser.add_argument(
        "--excluded-events",
        default=str(fetch_rides.EXCLUDED_EVENTS_PATH),
        help="UID → note sidecar of feed events that are not group rides "
        f"(default: {fetch_rides.EXCLUDED_EVENTS_PATH})",
    )
    parser.add_argument(
        "--now",
        type=parse_now,
        help="pin the clock to this ISO timestamp (tests; Eastern if naive)",
    )
    parser.add_argument(
        "--enrich-limit",
        type=int,
        default=DEFAULT_ENRICH_LIMIT,
        help="most archived rides to backfill per run "
        f"(default: {DEFAULT_ENRICH_LIMIT}, 0 for none)",
    )
    parser.add_argument(
        "--url-prefix",
        default=DEFAULT_URL_PREFIX,
        help=f"path prefix written into map_image (default: {DEFAULT_URL_PREFIX}); "
        "must stay relative",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compute everything and write nothing; report what would change",
    )
    return parser


def main(argv: list = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config(
        data_dir=args.data_dir,
        ics_file=args.ics_file,
        ride_images=args.ride_images,
        excluded_events=args.excluded_events,
        now=args.now,
        enrich_limit=args.enrich_limit,
        url_prefix=args.url_prefix,
        dry_run=args.dry_run,
    )
    try:
        state = run(config)
    except (
        fetch_rides.FeedError,
        archive_events.ArchiveError,
        export_ics.ExportError,
        SyncError,
    ) as exc:
        print(f"sync: {fetch_rides.scrub(exc)}", file=sys.stderr)
        return 1
    except OSError as exc:
        target = getattr(exc, "filename", None) or config.data_dir
        print(f"sync: could not write {target}: {exc.strerror}", file=sys.stderr)
        return 1

    for note in state.notes:
        print(f"sync: {note}")
    verb = "would write" if config.dry_run else "wrote"
    changed = state.files.changed()
    for path in changed:
        print(f"sync: {verb} {path}")
    print(f"sync: {len(changed)} file(s) changed" if changed else "sync: no changes")
    unfinished = unfinished_maps(config.maps_dir)
    if unfinished:
        print(
            f"sync: {len(unfinished)} map(s) still without a basemap "
            f"(will retry next run): {', '.join(unfinished)}"
        )
    return 0


def unfinished_maps(maps_dir: Path) -> list:
    """Maps drawn while the tile server was unreachable — retried next run."""
    if not maps_dir.is_dir():
        return []
    return [
        path.name
        for path in sorted(maps_dir.glob("*.svg"))
        if not route_map.has_basemap(path.read_text(encoding="utf-8"))
    ]


if __name__ == "__main__":
    sys.exit(main())
