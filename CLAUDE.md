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
| `scripts/ride_images.json` | Optional sidecar: ride UID → image URL, merged into each event as `image`. |
| `tests/fixtures/sample.ics` | Offline fixture (2 future, 1 past, 1 cancelled). See table below. |
| `tests/test_fetch_rides.py` | pytest suite for the fetch script (offline only). |
| `site/index.html` | Home: rides list/calendar, inline CSS/JS, no build step. |
| `site/gallery.html` | Ride-photo gallery (empty state → Instagram CTA). |
| `site/shopify.html` | WIP shop page (placeholder only). |
| `site/meta-business.html` | WIP Meta Business page (placeholder only). |
| `site/events.json` | Generated ride data (committed; the workflow updates it). |
| `.github/workflows/sync.yml` | Cron sync every 6h + manual dispatch. |
| `.github/workflows/pages.yml` | Builds `site/` and deploys it to GitHub Pages. |
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

- **The default branch is `master`** — both locally and on GitHub
  (`gh repo view --json defaultBranchRef` → `master`). There is no `main`
  branch; ignore any tooling that assumes one. Workflows that key on the
  default branch must say `master`.
- The remote is named **`boscafebikers`**, not `origin`
  (`git@github.com:ecao310/boscafebikers.git`). Every `git push`/`git fetch`
  needs the remote spelled out.
- `ralph.log` is gitignored loop scratch — do not commit it. Historical
  per-iteration notes live there; keep CLAUDE.md concise.

## Deployment

**Live: <https://ecao310.github.io/boscafebikers/>** (also `/events.json`).
Everything below is headless — nothing here needs the GitHub web UI.

- **Pages source: GitHub Actions**, not "deploy from a branch". The branch
  source only offers `/` or `/docs`, and the site lives in `site/`. Check with
  `gh api repos/:owner/:repo/pages` (`build_type` must be `"workflow"`); set it
  with `gh api -X PUT repos/:owner/:repo/pages -f build_type=workflow`. The
  leftover `source: {branch: master, path: "/"}` is ignored — don't try to fix it.
- **What deploys:** `.github/workflows/pages.yml` uploads `site/` via
  `actions/upload-pages-artifact` and publishes it with `actions/deploy-pages`.
- **Trigger chain — three ways in:**
  1. `push` on `master` (a human commit) → deploy.
  2. `sync.yml` (cron `0 */6 * * *` / dispatch) fetches the feed, promotes
     `site/events.json` only if the rides changed, and if it committed, its
     `deploy` job calls `pages.yml` via `workflow_call`. Bot commits made with
     `GITHUB_TOKEN` do **not** fire `push`, hence the explicit call.
  3. `workflow_dispatch` on `pages.yml`.
- **Redeploy by hand:** `gh workflow run pages.yml --ref master` then
  `gh run watch <id> --exit-status`. Takes ~15s.
- **Never use root-relative (`/…`) URLs in `site/`** — the site is served from
  the `/boscafebikers/` project subpath, so a leading slash 404s.
- **Sync→deploy gotchas (easy to break, keep them):**
  - `pages.yml`'s checkout must pass `ref: ${{ github.ref }}`. Without it, a
    `workflow_call` from sync.yml checks out the pre-bot-commit SHA and would
    deploy stale rides.
  - The reusable-workflow caller declares the callee's permissions: sync's
    `deploy` job carries `contents: read / pages: write / id-token: write`.
  - The actions (`actions/checkout@v4` et al.) target deprecated Node 20 and
    run on Node 24 on the runners — harmless today; a future pass can bump the
    action majors.
- `PARTIFUL_ICS_URL` is **set** (as of 2026-07-20); the sync bot commits real
  feed updates every 6h. `site/events.json` currently has `events: []` — no
  future rides right now, so the live page shows the empty state.

## `scripts/fetch_rides.py`

Run it on the fixture (never the live feed) with:

```
.venv/bin/python scripts/fetch_rides.py --ics-file tests/fixtures/sample.ics
```

- CLI: `--ics-file PATH` (bypasses the network), `--out PATH`
  (default `site/events.json`), and `--ride-images PATH` (default
  `scripts/ride_images.json`). With no `--ics-file` it reads
  `PARTIFUL_ICS_URL`, rewriting a leading `webcal://` to `https://`.
- Importable API for tests: `parse_events(data: bytes, now=None, images=None)
  -> list[dict]`, `extract_rsvp_url(description)`,
  `load_ride_images(path=None) -> dict`, `build_payload(rides, now=None)`,
  `write_events(payload, path)`, `main(argv) -> int`, and `FeedError`.
  Injecting `now` is how the tests pin "future" without depending on the clock.
- **Never echo `requests` exception text** — it embeds the request URL. The
  fetch path reports only `type(exc).__name__` (+ HTTP status when present).
  `scrub()` strips URLs from any other text that gets surfaced.
- Output shape: `{"updated_at", "count", "events": [...]}`; each event has
  `uid, title, start (ISO+offset), date_display, time_display, location,
  description (RSVP line stripped), rsvp_url (may be null), image (may be
  null)`. Display strings are precomputed in Python so the page doesn't render
  in the visitor's tz.
- **Ride photos:** the ICS feed carries no images, so `image` comes from the
  optional sidecar `scripts/ride_images.json` — a JSON object mapping event UID
  → photo URL (e.g. `"<partiful-id>@partiful.com": "https://…/a.jpg"`). The
  organizer edits that file, commits it, and the next sync writes the merged
  `image` into `events.json`; a missing file or an empty object means every
  ride has `image: null`. UIDs come from the feed (`uid` field in
  `events.json`). Malformed sidecar JSON is a `FeedError` (fails the sync
  loudly rather than silently dropping photos).
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
keyed on `requirements.txt`, and a `concurrency: sync-rides` group so two runs
can't race a push. `sync` job carries `permissions: contents: write` (job-level);
the `deploy` job (see Deployment) carries the Pages permissions.

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

## `.github/workflows/pages.yml`

`checkout` (with `ref: ${{ github.ref }}`) → `actions/configure-pages@v5` →
`actions/upload-pages-artifact@v3` (`path: site`) → `actions/deploy-pages@v4`,
with `permissions: contents: read / pages: write / id-token: write`,
`concurrency: pages` (`cancel-in-progress: false`), and the `github-pages`
environment carrying the deploy URL. Triggers: `push` on **`master`** (the
default branch — there is no `main`), `workflow_dispatch`, and `workflow_call`
(from sync.yml). Why Actions and not "deploy from a branch": that source only
offers `/` or `/docs`, and the site lives in `site/`.

## Status

Phase 1 (build) and phase 2 (deploy) are complete — the site is live and the
sync→deploy freshness chain works. Phase 3 (Backlog 3) is in progress.
`PARTIFUL_ICS_URL` is set and the sync bot commits real updates every 6h;
`site/events.json` currently has `events: []` (no future rides), so the live
page shows the empty state. Historical per-iteration notes were moved to
`ralph.log` (gitignored scratch) in iteration 19 to keep this file a concise
reference; `git log` records what each iteration changed.

## `site/index.html`

Single file, no build step: inline `<style>` in `<head>`, one IIFE `<script>`
just before `</body>`.

- **Shared tab header nav.** All four pages (`index.html`, `gallery.html`,
  `shopify.html`, `meta-business.html`) carry the same `.nav` — a sticky
  espresso bar with four relative `.tabs` links (Rides / Gallery / Shop / Meta
  Business). The current page's link gets `.is-active` + `aria-current="page"`;
  the others are plain. The CSS is duplicated inline in each page (no shared
  stylesheet, no build step). Keep links relative — never root-relative — and
  keep the `.is-active`/`aria-current` on exactly one link per page.
  `section { scroll-margin-top: 64px }` on the home page keeps the sticky nav
  from covering in-page anchor targets (`#rides`).
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
  `rsvp_url` also falls back to the profile URL. When a ride has `image`, the
  card starts with a photo banner (`.ride-img-link` wrapping `<img
  class="ride-img" loading="lazy">`, `alt` = ride title) linked to the same
  RSVP target; it's omitted entirely when `image` is null/absent.
- **List/calendar toggle** (`#view-toggle`, static markup but `hidden` until
  the script has rides): two `.view-btn` buttons (`data-view="list|calendar"`,
  `.is-active` + `aria-pressed` mark the chosen view) switch `#schedule`
  between the card list (default) and month-grid calendars. The calendar
  renders one `.calendar` block per month that has rides — `groupByMonth()`
  groups by the Y-M-D prefix of `start`, and because `events.json` is sorted,
  both month order and within-month event order come out chronological for
  free. Each `.cal-grid` is 7 weekday columns (`.cal-dow` headers); a day cell
  has a `.num` plus one `.ride-chip` `<a>` per ride (href = `rsvp_url`, falling
  back to the profile URL). Cells outside the month get the `.empty` class.
  `.cal-day.has-ride` tints days that have rides.
- **Calendar weekday math is the exception to the no-`Date` rule.** The
  calendar must not call `new Date(start)` in the visitor's local tz — a
  near-midnight ride would land on the wrong weekday for non-Eastern visitors.
  The `start` ISO string already carries the Eastern offset, so its Y-M-D
  prefix *is* the Eastern wall-clock date; the code builds
  `new Date(Date.UTC(y, m-1, d))` and reads `getUTCDay()` / `getUTCDate()`.
  That returns the same weekday in any timezone. Display times still come from
  the precomputed `date_display`/`time_display`.
- **`[hidden]` needs `display: none !important`** in the CSS: `.view-toggle`
  sets `display: flex`, which would override the UA's `hidden` rule and show
  the (empty) toggle before JS hides it. The global `[hidden]` rule exists for
  this reason.
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
  were checked.
- Sections/ids: `#rides`, `#first-ride`, `#about`, `#links`, `#contact`. The
  hero CTA anchors to `#rides`.
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
