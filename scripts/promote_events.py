#!/usr/bin/env python3
"""Copy a freshly fetched events.json over the committed one, but only if the
rides actually changed.

fetch_rides.build_payload() stamps `updated_at` on every run, so a plain copy
would make the sync workflow commit a new timestamp every 6 hours forever.
Comparing the `events` list keeps the git history meaningful.

    python scripts/promote_events.py <new.json> <committed.json>

Exits 0 whether or not the file was replaced; nonzero only on real errors.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def load_events(path: Path) -> object:
    """The `events` list from a payload file, or None if it isn't readable."""
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle).get("events")
    except (OSError, ValueError, AttributeError):
        return None


def promote(new_path: Path, target_path: Path) -> bool:
    """Replace target with new when the rides differ. Returns True if copied."""
    new_events = load_events(new_path)
    if new_events is None:
        raise SystemExit(f"promote_events: {new_path} is missing or not valid JSON")
    if new_events == load_events(target_path):
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(new_path, target_path)
    return True


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    changed = promote(Path(args[0]), Path(args[1]))
    print("Rides changed; updated " + args[1] if changed else "Rides unchanged; keeping the committed file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
