# `data` — the generated ride data

This orphan branch holds the **only** copy of the ride data the Boston Café
Bikers site publishes. It shares no history with `master` or `dev`: it carries
no code, and no code branch carries the data.

```
events.json        upcoming rides
events-past.json   the accumulating archive of rides that already happened
cafe-points.json   café lat/lon cache (the pins on cafes.html)
rides.ics          the public, subscribable calendar
maps/<uid>.svg     one drawn route map per ride
sync-report.json   the last sync run's counts (photos / routes / distances on the
                   upcoming list, archive size and how many are still unchecked,
                   cafés placed vs unplaced, maps without a basemap) — written by
                   scripts/sync.py, deliberately not copied into the site
```

Each ride in `events.json` / `events-past.json` also carries the display fields
`scripts/ride_fields.py` precomputes — `grace_until`, `place_name`, `address`,
`year`, and `start_name`/`end_name` on each route — so the site reads them
instead of deriving anything in the browser.

**The layout mirrors `site/`.** Every path here sits at the same place it used
to sit inside `site/`, so the published URLs are unchanged —
`…/boscafebikers/events.json`, `…/rides.ics`, `…/maps/<uid>.svg` — and anyone
subscribed to `webcal://ecao310.github.io/boscafebikers/rides.ics` never notices
this branch exists.

**Written by the sync bot.** `.github/workflows/sync.yml` (cron every 6 hours)
checks this branch out beside the code, runs `scripts/sync.py --data-dir _data`,
and commits + pushes here only when something actually changed. Don't hand-edit
these files: the next sync rewrites them from the Partiful feed. To take an
event off the site, add its UID to `scripts/excluded_events.json` on the code
branch instead.

**Read it into a local checkout** with `scripts/pull_data.sh` (on `master` /
`dev`), which extracts this branch's files into `site/`.

**Published by** `.github/workflows/pages.yml`, which checks out `master`, `dev`
and this branch and copies these files into both trees of the one Pages
artifact.

## Re-rooting when the history gets heavy

Roughly four bot commits a day land here, and each new ride adds a 55–140 KB
route map, so the branch grows without bound. Nothing depends on its history —
`master` and `dev` are the record of *decisions*; this is a snapshot of what
Partiful says today. So whenever it gets heavy, flatten it to a single commit:

```bash
git checkout --orphan data-fresh data
git commit -m "Re-root the data branch"
git push --force boscafebikers data-fresh:data
```

No code history is touched, and the next sync carries on from the new root.
