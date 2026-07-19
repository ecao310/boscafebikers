You are one iteration of a loop. Each run: pick exactly ONE unchecked task from the
Backlog below (topmost first), complete it fully, verify it, mark it [x] in this
file's copy at PLAN.md in the repo root, commit, and exit. Do not attempt more
than one task per run.

Project spec

Build a static website for Boston Café Bikers ("exploring the city one café at a
time" — a casual Boston cycling group that rides to cafés) with a ride schedule
auto-synced from the organizer's Partiful ICS calendar feed.

Architecture:


scripts/fetch_rides.py — fetches the ICS feed (URL from env var PARTIFUL_ICS_URL),
parses with the icalendar package, keeps only future events, extracts title,
start (America/New_York), location, and Partiful RSVP link from the description,
handles STATUS:CANCELLED, writes sorted site/events.json. Exits nonzero on
fetch/parse failure. Never prints the feed URL.
.github/workflows/sync.yml — cron every 6 hours + manual dispatch; runs the
script with PARTIFUL_ICS_URL from repo secrets; commits site/events.json
only if changed.
site/ — single-page static site (one index.html, inline CSS/JS, no build
step, no frameworks). Sections: hero with the group one-liner; upcoming rides
rendered from events.json with "RSVP on Partiful" buttons and a
"last updated" timestamp; "Your first ride" (no-drop, all levels, BlueBikes
welcome); about; links to Instagram @bostoncafebikers and Partiful. If
events.json is missing/empty, show a fallback link to
https://partiful.com/u/Hs47uq5mucZyXLBJZCda instead of an empty list.
Mobile-first, warm café palette, readable at 380px wide.


Rules


One task per iteration. Small, complete, verified.
Verify before committing: run the script against tests/fixtures/sample.ics
(never the live feed in tests), open/lint the HTML, run any tests you wrote.
If you find a bug from a previous iteration, fixing it IS your task this
iteration: fix it, note it under "Discovered work" in PLAN.md, exit.
If a task is blocked, mark it [blocked: reason] in PLAN.md, pick the next
task instead.
Never commit secrets. The real ICS URL only ever lives in the
PARTIFUL_ICS_URL GitHub secret / env var.
Keep CLAUDE.md updated with anything the next iteration needs to know
(decisions, gotchas, file map). You have no memory between runs — these files
are your memory.
When every Backlog task is [x], verify the whole system end-to-end once
(script on fixture → events.json → page renders), then print exactly
RALPH_DONE and exit.


Backlog


 Init repo: git init, .gitignore, PLAN.md (copy of this Backlog),
CLAUDE.md with file map and conventions, requirements.txt (icalendar, requests)
 Create tests/fixtures/sample.ics with 4 realistic Partiful-style events:
2 future, 1 past, 1 cancelled; include RSVP URLs in descriptions
 Write scripts/fetch_rides.py per spec; run it on the fixture and confirm
site/events.json contains exactly the 2 future events, sorted by date
 Add tests/test_fetch_rides.py (pytest): past-event filtering, cancelled
filtering, RSVP link extraction, timezone correctness, malformed-feed exit code
 Write site/index.html hero + about + first-ride + links sections with
placeholder schedule area
 Add schedule rendering JS: load events.json, render ride cards
(date, time, start location, RSVP button), last-updated stamp, empty-state
fallback to the Partiful profile
 Create .github/workflows/sync.yml per spec (cron 0 */6 * * *,
workflow_dispatch, commit-if-changed guard)
 Add README.md: what this is, how to get the ICS URL from Partiful
(Settings → Calendar Sync → Apple Calendar, swap webcal:// for https://),
how to set the repo secret, how to deploy on GitHub Pages
 End-to-end check: fresh clone simulation — script on fixture, open site,
confirm rides render; fix anything broken


Discovered work

(append new tasks here as - [ ] items; treat them as part of the Backlog)
