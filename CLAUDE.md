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
| `scripts/promote_events.py` | Copies fetched JSON over the committed one only if `events` differ. |
| `tests/fixtures/sample.ics` | Offline fixture (2 future, 1 past, 1 cancelled). See table below. |
| `tests/test_fetch_rides.py` | pytest suite for the fetch script (offline only). |
| `site/index.html` | The whole site: one page, inline CSS/JS, no build step. |
| `site/events.json` | Generated ride data (committed; the workflow updates it). |
| `.github/workflows/sync.yml` | Cron sync every 6h + manual dispatch. |
| `README.md` | Human-facing: how it works, ICS URL, secret, Pages deploy, local dev. |

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

## `scripts/fetch_rides.py`

Run it on the fixture (never the live feed) with:

```
.venv/bin/python scripts/fetch_rides.py --ics-file tests/fixtures/sample.ics
```

- CLI: `--ics-file PATH` (bypasses the network) and `--out PATH`
  (default `site/events.json`). With no `--ics-file` it reads
  `PARTIFUL_ICS_URL`, rewriting a leading `webcal://` to `https://`.
- Importable API for tests: `parse_events(data: bytes, now=None) -> list[dict]`,
  `extract_rsvp_url(description)`, `build_payload(rides, now=None)`,
  `write_events(payload, path)`, `main(argv) -> int`, and `FeedError`.
  Injecting `now` is how the tests pin "future" without depending on the clock.
- **Never echo `requests` exception text** — it embeds the request URL. The
  fetch path reports only `type(exc).__name__` (+ HTTP status when present).
  `scrub()` strips URLs from any other text that gets surfaced.
- Output shape: `{"updated_at", "count", "events": [...]}`; each event has
  `uid, title, start (ISO+offset), date_display, time_display, location,
  description (RSVP line stripped), rsvp_url (may be null)`. Display strings
  are precomputed in Python so the page doesn't render in the visitor's tz.
- Filtering is `start >= now` in `America/New_York`; `STATUS:CANCELLED` dropped.
  All-day `DATE` values become local midnight.
- The venv here is **Python 3.9**, so the module uses
  `from __future__ import annotations` for `X | None` hints. Keep that import.

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

## `.github/workflows/sync.yml`

Cron `0 */6 * * *` (UTC) + `workflow_dispatch`. Ubuntu, Python 3.11, pip cache
keyed on `requirements.txt`, `permissions: contents: write`, and a
`concurrency: sync-rides` group so two runs can't race a push.

- **The commit-if-changed guard needs `promote_events.py`.** `build_payload()`
  stamps a fresh `updated_at` on every run, so `git diff` on `site/events.json`
  would *always* be dirty and the bot would commit a new timestamp every 6h
  forever. So the workflow writes the fetch to `$RUNNER_TEMP/events.json`, then
  `scripts/promote_events.py <new> site/events.json` copies it into place only
  when the `events` lists differ. The final step is a plain
  `git diff --quiet -- site/events.json` guard. Don't "simplify" this back into
  a single fetch-in-place step.
- `promote_events.py` is stdlib-only, exits 0 whether or not it copied, and
  exits nonzero only if the new file is missing/unparseable. No tests yet
  (verified by hand: unchanged → no diff, edited title → diff, missing file →
  exit 1).
- Committer identity is the `github-actions[bot]` noreply address.
- The secret is passed as `env: PARTIFUL_ICS_URL: ${{ secrets.PARTIFUL_ICS_URL }}`
  on the fetch step only — never as a CLI arg (args show up in logs).
- No `yaml` module in the venv; validate the workflow with
  `ruby -ryaml -rjson -e 'puts JSON.pretty_generate(YAML.load_file(".github/workflows/sync.yml"))'`.

## Status

Iteration 1: repo scaffolding (`.gitignore`, `PLAN.md`, `CLAUDE.md`,
`requirements.txt`).
Iteration 2: `tests/fixtures/sample.ics` (see table above); verified it parses
with `icalendar` and yields the expected 4 events.
Iteration 3: `scripts/fetch_rides.py` + generated `site/events.json` (2 future
rides, sorted).
Iteration 4: `tests/test_fetch_rides.py` — 24 tests, all green, all offline.
Iteration 5: `site/index.html` — hero, upcoming-rides section (placeholder
schedule area), "Your first ride", about, links, footer.
Iteration 6: schedule rendering `<script>` in `site/index.html` (ride cards,
last-updated stamp, empty/error fallback).
Iteration 7: `.github/workflows/sync.yml` + `scripts/promote_events.py` (see
above).
Iteration 8: `README.md` — how it works, getting the ICS URL (Partiful
Settings → Calendar Sync → Apple Calendar, `webcal://` → `https://`), setting
the `PARTIFUL_ICS_URL` secret, GitHub Pages deploy (branch + `/site` folder),
local dev (`python -m http.server -d site 8000`; the page must be served over
HTTP, not `file://`, for `fetch("events.json")` to work). Next and last task is
the end-to-end check.

## `site/index.html`

Single file, no build step: inline `<style>` in `<head>`, one IIFE `<script>`
just before `</body>`.

- CSS custom properties on `:root` are the warm café palette (`--espresso`,
  `--roast`, `--crema`, `--latte`, `--foam`, `--oat`, `--ink`, `--muted`).
  Reuse them; don't introduce new hex values.
- Layout is mobile-first: `.wrap` (max-width 680px, 20px gutters) and one
  `@media (min-width: 560px)` block that only bumps vertical padding. Verified
  readable at 380px.
- **Rendering script** (bottom of the file): `fetch("events.json")` →
  `<div id="schedule">` gets a `<ul class="rides">` of `<li class="ride">`
  cards (`.when` = `date_display · time_display`, `.where` = location, a `<p>`
  description, `<a class="btn">RSVP on Partiful`), and
  `<p class="note" id="updated">` gets the "Last updated … ET." stamp.
  Zero events, a non-OK response, or bad JSON all fall back to a note plus a
  "See all rides on Partiful" button pointing at the profile URL. A missing
  `rsvp_url` also falls back to the profile URL.
- `events.json` display strings (`date_display`, `time_display`) are
  precomputed; the JS must **not** re-format dates with `Date`, or visitors
  outside Eastern see wrong times. `updated_at` is likewise formatted by
  **regex-slicing the ISO string** (it already carries the Eastern offset) —
  keep it that way.
- The DOM is built with `createElement`/`textContent`, never `innerHTML`, so
  feed text can't inject markup. Keep that.
- Verifying the JS: no browser here, but `node` (v25) is installed. Shim a
  tiny `document`/`fetch`, pull the script out of the HTML with a regex, and
  `eval` it — that's how the happy path, empty, missing-rsvp and 404 cases
  were checked this iteration.
- Sections/ids: `#rides`, `#first-ride`, `#about`, `#links`. The hero CTA
  anchors to `#rides`.
- Verified well-formed by feeding it through `html.parser` (no unclosed or
  mismatched tags).

## `tests/test_fetch_rides.py`

Run with `.venv/bin/python -m pytest tests/ -q` (24 passing). Notes:

- There is no `conftest.py` / packaging; the test file puts `scripts/` on
  `sys.path` itself and does `import fetch_rides`.
- Pinned clock is `NOW = 2025-01-01 12:00 America/New_York`, passed as
  `parse_events(..., now=NOW)`. Never call the parser without `now` in a test.
- Coverage: past + cancelled filtering, sort order, folded-RSVP extraction,
  RSVP line stripped from description, `-04:00` offsets, precomputed display
  strings, non-ASCII round-trip, `now` boundary (`>=` keeps an event starting
  exactly now), empty result, malformed feed → `FeedError`, `main()` exit codes
  (0 happy path, 1 for broken feed / missing file / unset env var), and two
  leak tests asserting the feed URL never reaches an error message.
- The suite passes under any system timezone (verified with `TZ=Asia/Tokyo`) —
  keep it that way; assert on explicit offsets, not on local time.
