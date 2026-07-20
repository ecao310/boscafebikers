# CLAUDE.md — Boston Café Bikers

Static site + ICS sync for a casual Boston cycling group that rides to cafés.
Tagline: "exploring the city one café at a time".

## File map

| Path | Purpose |
| --- | --- |
| `PROMPT.md` | The Ralph loop spec (project spec + rules + backlog source of truth). |
| `PLAN.md` | Working copy of the backlog. Mark tasks `[x]` as they complete. |
| `CLAUDE.md` | This file — decisions, gotchas, conventions for the next iteration. |
| `requirements.txt` | Python deps: `icalendar`, `requests`, `pytest`. |
| `scripts/fetch_rides.py` | Fetches + parses the ICS feed → `site/events.json`. |
| `tests/fixtures/sample.ics` | Offline fixture (2 future, 1 past, 1 cancelled). See table below. |
| `tests/test_fetch_rides.py` | pytest suite for the fetch script. |
| `site/index.html` | The whole site: one page, inline CSS/JS, no build step. |
| `site/events.json` | Generated ride data (committed; the workflow updates it). |
| `.github/workflows/sync.yml` | Cron sync every 6h + manual dispatch. |

## Conventions & decisions

- **Never commit the ICS URL.** It lives only in env var `PARTIFUL_ICS_URL` /
  the GitHub secret of the same name. The script must never print it (including
  inside error messages — strip URLs from exception text).
- **Tests never hit the network.** Always parse `tests/fixtures/sample.ics`.
- Timezone for all displayed times: `America/New_York` (use `zoneinfo`).
- `site/` is plain static: single `index.html`, inline `<style>`/`<script>`,
  no frameworks, no bundler. Mobile-first, warm café palette, readable at 380px.
- Public Partiful profile (safe to commit, used as empty-state fallback):
  `https://partiful.com/u/Hs47uq5mucZyXLBJZCda`
- Instagram: `@bostoncafebikers`.
- Python: stdlib + the three deps above only. Script exits nonzero on
  fetch/parse failure.

## Gotchas

- Git default branch here is `master`; the repo's "main" branch for PRs is `main`.
- `ralph.log` is gitignored loop scratch — do not commit it.

## Fixture contents (`tests/fixtures/sample.ics`)

Partiful-style feed, 4 VEVENTs, deliberately **not** in chronological order so
sorting is exercised. All `DTSTART;TZID=America/New_York` (a VTIMEZONE block is
included, so `icalendar` returns tz-aware datetimes directly).

| UID prefix | Summary | Start | Status | Expected |
| --- | --- | --- | --- | --- |
| `evt-past-jamaica-pond` | Jamaica Pond Loop ☕ | 2024-05-04 09:00 | CONFIRMED | dropped (past) |
| `evt-cancelled-blue-hills` | Blue Hills Coffee Climb | 2030-09-14 08:30 | CANCELLED | dropped |
| `evt-future-charles-loop` | Charles River Loop → Tatte | 2030-06-22 09:30 | CONFIRMED | **kept, 1st** |
| `evt-future-minuteman` | Minuteman Bikeway to Lexington | 2030-07-06 10:00 | CONFIRMED | **kept, 2nd** |

- Future dates are in **2030** on purpose, so the fixture doesn't rot.
- RSVP links live at the end of DESCRIPTION as `RSVP: https://partiful.com/e/<id>`,
  after a `\n\n`, and are **line-folded** across the `RSVP:` / URL boundary — the
  parser must work on the unfolded value (`str(event['DESCRIPTION'])`), never on
  raw lines.
- Descriptions/locations contain non-ASCII (`é`, `☕`, `→`, `—`) and escaped
  commas — read the file as bytes and let `icalendar` decode.
- Local venv for verification: `python3 -m venv .venv && .venv/bin/pip install -r
  requirements.txt` (`.venv/` is gitignored).

## Status

Iteration 1: repo scaffolding (`.gitignore`, `PLAN.md`, `CLAUDE.md`,
`requirements.txt`).
Iteration 2: `tests/fixtures/sample.ics` (see table above); verified it parses
with `icalendar` and yields the expected 4 events. Next task is
`scripts/fetch_rides.py`.
