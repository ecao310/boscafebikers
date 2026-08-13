# CLAUDE.md — Boston Café Bikers

Static site + ICS sync for a casual Boston cycling group that rides to cafés.
Tagline: "exploring the city one café at a time".

## File map

| Path | Purpose |
| --- | --- |
| `ralph/PROMPT.md` | The Ralph loop spec (project spec + rules + backlog source of truth). |
| `ralph/ralph.log` | Gitignored loop scratch — per-iteration notes (do not commit). |
| `ralph/PLAN.md` | Working copy of the backlog. Mark tasks `[x]` as they complete. |
| `CLAUDE.md` | This file — decisions, gotchas, conventions for the next iteration. |
| `requirements.txt` | Python deps: `icalendar`, `requests`, `pytest`. |
| `scripts/fetch_rides.py` | Fetches + parses the ICS feed → `site/events.json`; enriches ride images from public Partiful event pages during live syncs. |
| `scripts/promote_events.py` | Copies fetched JSON over the committed one only if `events` differ. |
| `scripts/ride_images.json` | Optional sidecar: ride UID → image URL, merged into each event as `image`; an explicit entry wins over auto-enrichment. |
| `tests/fixtures/sample.ics` | Offline fixture (2 future, 1 past, 1 cancelled). See table below. |
| `tests/fixtures/event-page.html` | Offline fixture: a Partiful event page (`__NEXT_DATA__` with the event's cover image) used to test the enrichment step. |
| `tests/test_fetch_rides.py` | pytest suite for the fetch script (offline only). |
| `site/styles.css` | Shared stylesheet: café palette + base/nav/hero/footer styles, linked by every page. |
| `site/index.html` | Home: rides list/calendar, page-specific inline CSS + shared `styles.css`. Loads the three ride JS files in dependency order (see the `site/index.html` section). |
| `site/js/ride-card.js` | JS module (plain script, part of `window.BCB`): `rideCard()` builder + the `.ics` download / Google Calendar exports + shared constants (`PARTIFUL`, `MONTHS`, `DOW`) and the `el()` DOM helper. Loaded first. |
| `site/js/calendar.js` | JS module (plain script, part of `window.BCB`): FullCalendar renderer + fallback month grid + Eastern wall-clock date math. Loaded second. |
| `site/js/app.js` | JS module (plain script, part of `window.BCB`): bootstrap — `fetch("events.json")`, render, next-ride, modal, "Last updated" stamp, and the deferred `data-bg` background mechanism. Loaded last. |
| `site/images/jess-b-gracies-bikes.jpeg` | Café photo (optimized 1600px wide); the `data-bg` URL on the `#next-ride` section, applied as a background image only after `window.load`. |
| `site/gallery.html` | Ride-photo gallery (empty state → Instagram CTA). |
| `site/shopify.html` | WIP shop page (placeholder only). |
| `site/meta-business.html` | WIP Meta Business page (placeholder only). |
| `site/donate.html` | WIP donate page (placeholder only). |
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
- `site/` is plain static: no bundler, no build step. CSS is split between the
  shared `site/styles.css` (palette + base/nav/hero/footer — the single source
  for the café custom properties) and a small page-specific inline `<style>` on
  each page. Mobile-first, warm café palette, readable at 380px. The **one**
  exception to "no frameworks": the calendar view adopts FullCalendar 6 (MIT)
  from a CDN with `defer` — see the calendar bullet below for the trade-off and
  the graceful fallback.
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
- `ralph/ralph.log` is gitignored loop scratch — do not commit it. Historical
  per-iteration notes live there; keep CLAUDE.md concise. All ralph loop files
  live in `ralph/` (`ralph/PROMPT.md` is the spec and IS committed).

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
- **Calendar refresh/fetch backend (2026-08-13): keep the cron.** There is no
  public, unauthenticated Partiful endpoint that lists an org's events (the
  profile page SSR carries no events and its events-list callable returns 401
  without a Firebase token), so a client-side fetch can't replace the secret
  ICS; a serverless proxy would mean porting the tested Python parsing for
  marginal freshness gain. Public per-event pages *do* expose full data + a
  CORS-enabled per-event ICS (`calendarFile`) — the sync now uses them to
  backfill ride `image` (see the "Ride photos" bullet under
  `scripts/fetch_rides.py`), but they are not a feed replacement. Full
  comparison: ralph.log.
- `PARTIFUL_ICS_URL` is **set** (as of 2026-07-20); the sync bot commits real
  feed updates every 6h. `site/events.json` currently has 3 future rides
  (2026-08-15, 2026-08-16, 2026-08-23).

## `scripts/fetch_rides.py`

Run it on the fixture (never the live feed) with:

```
.venv/bin/python scripts/fetch_rides.py --ics-file tests/fixtures/sample.ics
```

- CLI: `--ics-file PATH` (bypasses the network), `--out PATH`
  (default `site/events.json`), and `--ride-images PATH` (default
  `scripts/ride_images.json`). With no `--ics-file` it reads
  `PARTIFUL_ICS_URL`, rewriting a leading `webcal://` to `https://`.
  **`--ics-file` runs never enrich** (see the enrichment bullet below) — they
  stay fully offline, so local fixture runs make zero network calls.
- Importable API for tests: `parse_events(data: bytes, now=None, images=None)
  -> list[dict]`, `extract_rsvp_url(description)`,
  `derive_partiful_url(uid) -> str | None`, `load_ride_images(path=None) -> dict`,
  `enrich_rides(rides, fetch_page=None) -> int`, `build_payload(rides, now=None)`,
  `write_events(payload, path)`, `main(argv) -> int`, and `FeedError`.
  Injecting `now` is how the tests pin "future" without depending on the clock.
- **Never echo `requests` exception text** — it embeds the request URL. The
  fetch path reports only `type(exc).__name__` (+ HTTP status when present).
  `scrub()` strips URLs from any other text that gets surfaced.
- Output shape: `{"updated_at", "count", "events": [...]}`; each event has
  `uid, title, start (ISO+offset), end (ISO+offset, may be null), date_display,
  time_display, location (may be null), location_hidden (bool), description
  (RSVP/invite line stripped), rsvp_url (may be null), image (may be null)`.
  `end` comes from the feed's `DTEND` (absent → null); the site's "add to
  calendar" ICS uses it so the invite blocks the whole ride. Display strings
  are precomputed in Python so the page doesn't render in the visitor's tz.
- **`rsvp_url` from the feed text:** Partiful descriptions carry the event page in
  any of three phrasings — `RSVP: <url>`, `RSVP at <url>`, or
  `View this event on Partiful at <url>` — and the URL is line-folded across the
  phrase / URL boundary. `extract_rsvp_url` matches all three (on the unfolded
  `str(event['DESCRIPTION'])`), and `_strip_rsvp` drops the whole invite line from
  the displayed description. If the text has no link at all, `derive_partiful_url`
  falls back to `https://partiful.com/e/<uid>` **only** for a bare UID (no `@` —
  real Partiful exports use the bare event id; descriptive `<name>@partiful.com`
  UIDs are never treated as ids). This is what makes the site's "RSVP on Partiful"
  button link to the actual event instead of the group profile page.
- **Text cleanup:** Partiful appends ` | Partiful` to every exported event title
  and real titles carry stray whitespace runs (e.g.
  `Boston Cafe Bikers        Ice Cream Crawl | Partiful`). `_clean_title`
  strips the suffix (case-insensitive) and collapses internal whitespace, so
  the site shows the organizer's real name. `_clean_description` (which wraps
  `_strip_rsvp`) additionally trims every line and collapses runs of 3+
  newlines into a single paragraph break — Partiful prose is plain paragraphs,
  and the RSVP-line removal can leave a ragged blank gap. Locations are
  otherwise left alone — see the hidden-location note below.
- **Start/end locations (attempted, not available):** Partiful's event model has
  a **single** optional Location field — there is no separate start/end location
  in the app or its ICS export (the ride's meeting point vs. café lives in the
  prose DESCRIPTION instead). So `location` stays the one `LOCATION` value; the
  "start and end locations" backlog task's finding is that there is nothing else
  to extract. What *did* need fixing: when the organizer hides the address until
  RSVP, the export substitutes the placeholder `Location available once RSVP'd`.
  `_clean_location` detects it (`HIDDEN_LOCATION_RE`) and emits `location: null`
  with `location_hidden: true`; the site renders "Location shared after you
  RSVP" instead of the template junk, and the `.ics` download omits `LOCATION`.
- **Ride photos:** the ICS feed carries no images, so `image` has two sources.
  (1) **Auto-enrichment** (default, added 2026-08-13): on a **live-feed** sync
  only (`--ics-file` runs stay offline), `enrich_rides()` fetches each ride's
  public Partiful event page `https://partiful.com/e/<id>` (the URL from
  `rsvp_url`, or `derive_partiful_url(uid)`) and extracts the cover image from
  the page's `__NEXT_DATA__` blob (`props.pageProps.event.image`, a URL string
  or `{url, blurHash}`) with a raw Firebase-Storage-URL regex as fallback.
  Fail-soft: a fetch/parse miss leaves `image: null` and never breaks the sync.
  (2) The optional sidecar `scripts/ride_images.json` — a JSON object mapping
  event UID → photo URL. An explicit sidecar entry **wins** over enrichment.
  The organizer edits the sidecar, commits it, and the next sync writes the
  merged `image` into `events.json`; a missing file or an empty object just
  means enrichment is the only source. Malformed sidecar JSON is a `FeedError`
  (fails the sync loudly rather than silently dropping photos). Verified on
  the fixture (`tests/fixtures/event-page.html`) — pytest injects a stub
  `fetch_page` so the tests never hit the network.
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
| `evt-future-charles-loop` | Charles River Loop → Tatte \| Partiful | 2030-06-22 09:30 | CONFIRMED | **kept, 1st** |
| `evt-future-minuteman` | Minuteman Bikeway to Lexington | 2030-07-06 10:00 | CONFIRMED | **kept, 2nd** |

- Future dates are in **2030** on purpose, so the fixture doesn't rot.
- The Charles River title carries the ` | Partiful` suffix real exports append
  (and the Minuteman title does not), so the shared `rides` fixture exercises
  `_clean_title` end-to-end. Minuteman's LOCATION is the real-world
  `Location available once RSVP'd` placeholder (its address is hidden until
  RSVP) while Charles carries a public address — so the shared `rides` fixture
  exercises `_clean_location` both ways.
- RSVP links live at the end of DESCRIPTION as `RSVP: https://partiful.com/e/<id>`,
  after a `\n\n`, and are **line-folded** across the `RSVP:` / URL boundary — the
  parser must work on the unfolded value (`str(event['DESCRIPTION'])`), never on
  raw lines. (Real Partiful exports say `RSVP at <url>` or
  `View this event on Partiful at <url>` instead; `extract_rsvp_url` handles all
  three — see the fetch-script section.)
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
`site/events.json` currently has 3 future rides (2026-08-15, 2026-08-16,
2026-08-23). Historical
per-iteration notes were moved to `ralph/ralph.log` (gitignored scratch) in
iteration 19 to keep this file a concise reference; `git log` records what
each iteration changed.

## `site/index.html`

No build step: `site/styles.css` linked in `<head>` (the shared base — palette,
nav, hero, footer), a small page-specific inline `<style>`, and the ride JS
loaded as three plain scripts at the end of `<body>` — `js/ride-card.js`,
`js/calendar.js`, `js/app.js` — all `defer` (the "JS module split" bullet
below). Each file is an IIFE that attaches its public API to the shared
`window.BCB` namespace, so the three files share state without a module
system or build step. The `defer`'d FullCalendar CDN script sits in `<head>`;
all four are deferred, so FC executes before ride-card/calendar/app in
document order on a real page and the calendar takes the FullCalendar path
directly, falling back to the hand-rolled grid only when the CDN is
unavailable. The node DOM-shim loads the same three files in the same order
(see the "Verifying the JS" note).

- **Shared tab header nav.** All five pages (`index.html`, `gallery.html`,
  `shopify.html`, `meta-business.html`, `donate.html`) carry the same `.nav` —
  an espresso bar with five relative `.tabs` links (Rides / Gallery / Shop /
  Meta Business / Donate). The nav is **static and scrolls with the page**: the
  organizer re-opened the earlier "keep the nav pinned" request as its opposite
  ("make top navigation bar not stay permanently on screen"), so
  `position: sticky; top: 0` were removed from `.nav` in `site/styles.css`
  (2026-08-13); the `.is-active`/`aria-current` + `section { scroll-margin-top:
  64px }` clearance for the sticky nav were removed from `index.html` at the
  same time. The current page's link gets `.is-active` +
  `aria-current="page"`; the others are plain. The nav CSS lives once in
  `site/styles.css` (linked by all five pages); each page keeps only its
  page-specific rules (rides/calendar on `index.html`, gallery grid, the
  `.btn { margin-top: 1rem }` CTA spacing on the sub-pages) in a small inline
  `<style>`. Keep links relative — never root-relative — and keep the
  `.is-active`/`aria-current` on exactly one link per page.
- **Shared footer.** All five pages end with the same `<footer>`: a
  `.footer-brand` tagline ("…exploring the city one café at a time"), a
  `.footer-nav` mirroring the five tab links (relative, no `.is-active`), and a
  `.footer-social` row (Instagram + Partiful, separated by a `.sep`). The footer
  styles live once in `site/styles.css` next to the nav; each page just repeats
  the shared markup. Keep the three footers on the WIP sub-pages identical to
  the home page's — no per-page footer divergence.
- CSS custom properties on `:root` are the warm café palette (`--espresso`,
  `--roast`, `--crema`, `--latte`, `--foam`, `--oat`, `--ink`, `--muted`).
  Reuse them; don't introduce new hex values.
- Layout is mobile-first: `.wrap` (max-width 680px, 20px gutters) and one
  `@media (min-width: 560px)` block that only bumps vertical padding. Verified
  readable at 380px.
- **Café photo loads last (`data-bg`), backing the `#next-ride` section.** The
  café photo (`site/images/jess-b-gracies-bikes.jpeg`) is *not* a
  `background-image` in the stylesheet — `app.js` reads the `data-bg` attribute
  on `<section id="next-ride">` (the 2nd block, right under the photo-free hero)
  and copies it into `background-image` only after `window.load`
  (`applyBackgrounds()`), so the photo never blocks first paint / LCP. The
  espresso gradient on `#next-ride` in `styles.css` is the no-JS / pre-load
  fallback (the hero keeps the same gradient, permanently photo-free).
  `#next-ride.bg-loaded` adds `background-size: cover` / `background-position:
  center` and a translucent espresso `::before` overlay (the section's `.wrap`
  is lifted above it) for text legibility over the photo. The overlay's opacity
  is the **`--bg-overlay-opacity` custom property** in `styles.css` `:root` —
  the readability "setting" the organizer asked for: raise it to darken the
  photo more (stronger contrast for the "Next ride" heading), lower it to show
  more photo. Ride `<img>` photos stay `loading="lazy"` in `rideCard()`. The
  node shim asserts `background-image` is unset before the load event fires and
  set after.
- **Rendering script** (`site/js/app.js` — loads last; `ride-card.js` /
  `calendar.js` supply the helpers via `window.BCB`): `fetch("events.json")` →
  - The **next-ride section** (`#next-ride`, the first section in `<main>`,
    right under the hero — whose CTA anchors to `#next-ride`) shows the nearest
    upcoming ride as a featured card. `setNextRide()` renders `events[0]`
    (events.json is sorted by start and the sync filters to future rides) into
    `#next-ride-card` via the shared `rideCard(ev, "next-ride")` builder; when
    there's nothing upcoming it shows a note plus a "See all rides on Partiful"
    button.
  - The **schedule section** (`#rides`) is **calendar-only** — the list view
    and its `#view-toggle` were removed in favor of the next-ride card.
    `<div id="schedule">` gets the month calendar (FullCalendar 6 primary,
    hand-rolled grid fallback — see the calendar bullet), and
    `<p class="note" id="updated">` holds the "Last updated … ET." stamp as a
    clickable link (`#updated-link`) to the `sync.yml` workflow on GitHub
    Actions — the "Sync rides now" button is gone (every page load already
    fetches the current `events.json`, and a maintainer re-syncs from that
    workflow page). The line stays `hidden` until `updated_at` renders, so a
    failed load leaves no empty focusable link. Zero events, a non-OK
    response, or bad JSON all fall back to a note plus a "See all rides on
    Partiful" button pointing at the profile URL.
  - The shared `rideCard(ev, extraClass)` builder renders one `.ride` card
    (`.ride.next-ride` when passed the extra class): `.when` =
    `date_display · time_display`, `.where` = location or the friendly
    "Location shared after you RSVP" note when `location_hidden`, a `<p>`
    description, and `<a class="btn">RSVP on Partiful` (a missing `rsvp_url`
    falls back to the profile URL). When a ride has `image`, the card starts
    with a photo banner (`.ride-img-link` wrapping `<img class="ride-img"
    loading="lazy">`, `alt` = ride title) linked to the same RSVP target; it's
    omitted entirely when `image` is null/absent. Each card ends with a
    `.ride-actions` row: the RSVP button plus a `btn btn-ghost` "Add to
    calendar" button that downloads a per-event `.ics` generated in the browser
    (`buildIcs`/`downloadIcs`). ICS `DTSTART`/`DTEND` reuse the same
    Eastern-wall-clock trick as the calendar — the `start`/`end` ISO prefixes
    become `DTSTART;TZID=America/New_York:…` with no `new Date(start)`. Long
    lines are folded per RFC 5545 (`foldIcsLine`), text is escaped
    (`icsEscape`), and the RSVP URL is appended to the description + emitted as
    a `URL:` property. A second `btn btn-ghost` "Google Calendar" `<a>` (opened
    in a new tab) mirrors the BCU add-to-calendar export: `googleCalUrl(ev)`
    builds a `calendar.google.com/calendar/render?action=TEMPLATE` URL from the
    same precomputed Eastern wall-clock fields (`icsDateTime`, no `new
    Date(start)`), `ctz=America/New_York`, and `end` null → the block defaults
    to +1h via `icsDateTimePlusHour` (Date.UTC arithmetic so a near-midnight
    ride rolls into the next day). Like `buildIcs`, the details field appends
    `RSVP: <url>` when `rsvp_url` is present. This came out of the BCU research
    task — see the decision note under "Research" in ralph.log.
  - The **ride-detail modal** (`#ride-modal`, a `.modal` overlay with
    `.modal-backdrop` + `.modal-dialog`) is the BCU detail-page pattern adapted
    for the single page: clicking a calendar event (FullCalendar `eventClick`
    or a fallback-grid `.ride-chip`) opens it instead of navigating straight to
    the RSVP page. Content is built by the *same* `rideCard(ev, "modal-ride")`
    builder as the featured next-ride card, so the details and the
    add-to-calendar exports can't drift; `.modal .ride` drops the card chrome
    so the dialog is the single container. `openRideModal(ev)` stores
    `document.activeElement`, sets the dialog's `aria-label` to the ride title,
    hides body scroll (`document.body.style.overflow = "hidden"`), and focuses
    the close button. `closeRideModal()` restores focus to the opener. Closing:
    the `×` button, Escape (a `keydown` listener), or clicking the backdrop
    (any click in the overlay whose target isn't inside `.modal-dialog`). The
    modal sits at `z-index: 100` (above the nav) and relies on the
    `[hidden]` rule to beat its `display: flex`. The dialog is a **flex column**
    with `#ride-modal-content` as its scrollport (`min-height: 0;
    overflow-y: auto`), so it fits within `max-height: 88vh` and the 44px
    `.modal-close` button stays pinned at the top while a long description
    scrolls (don't revert to `overflow-y: auto` on the whole dialog — the close
    button would scroll out of view).
- **Calendar view** (the schedule section's only renderer — the list view was
  removed). The **primary renderer is FullCalendar 6** (`dayGridMonth`): when
  `window.FullCalendar` is defined, `renderCalendarFull()` builds a
  `FullCalendar.Calendar` in `#ride-calendar` with `timeZone:
  "America/New_York"`, `initialDate` = first ride's Eastern date, `height:
  "auto"`, `dayMaxEvents: 3`, `eventDisplay: "block"`, header nav
  (prev/next + month title), and one event per ride (`title`, `start`, `end`,
  `url` = `rsvp_url` falling back to the profile URL, `extendedProps.data` =
  the full event). `eventClick` intercepts the left-click and opens the ride
  detail modal (see the rendering-script bullet) instead of navigating to the
  RSVP page; the event keeps its `url` so middle-click / ctrl-click still opens
  the RSVP target in a new tab (native anchor behavior). `render()` calls
  `destroyCalendar()` first so a stale instance can't leak when syncing or
  re-rendering. **`renderCalendarFull` takes the mount element
  (`renderCalendarFull(events, schedule)`) and appends the `.calendar` box into
  it BEFORE calling `FullCalendar.render()`** — FullCalendar measures its
  container via `getBoundingClientRect()` during `componentDidMount`, and if the
  holder is detached at render time it measures 0 wide, collapsing the day-grid
  columns to ~0px and crushing every event to ~14px (the "calendar looks
  completely broken" bug). Don't revert to "build the box, return it, then
  append" — the render must happen after the box is in the document.
  **Fallback:** if the CDN script hasn't loaded (slow network /
  blocked), `typeof FullCalendar` is undefined and the hand-rolled month grid
  takes over — one `.calendar` block per month that has rides, built by
  `groupByMonth()` / `monthGrid()` (7 `.cal-dow` weekday columns, a `.num` per
  day cell, one `.ride-chip` `<button>` per ride that opens the same modal;
  `.cal-day.has-ride` tints days). The chip is a `<button>` — clicking it is an
  action (show details), not a navigation — so CSS resets the UA button look
  (`font: inherit`, `border: 0`, `text-align: left`, `cursor: pointer`, plus
  `width: 100%`) on top of the shared chip styling. Ride titles **wrap** in
  both renderers (`overflow-wrap: anywhere`) rather than ellipsis-truncating,
  so a long title stays fully visible at 380px. Every tappable calendar element
  (`.ride-chip`, `.fc .fc-daygrid-event`, the FC `+N more` link, the prev/next
  `.fc .fc-button`) carries `min-height: 44px` — the 2026-08-13 mobile audit's
  touch-target rule; keep it when restyling. The FullCalendar CDN script has
  `defer`; a tiny hook listens for its `load` event and re-renders if it lands
  after an earlier fallback render.
- **Calendar display decision (2026-08-12, revised):** the calendar view adopts
  **FullCalendar 6.1.15** (MIT, actively maintained, industry standard) via
  CDN — a single `defer`'d script tag; its CSS is embedded in the JS and
  auto-injected. Re-evaluated in Aug 2026 because the previous "keep hand-rolled"
  resolution was reverted by the organizer: FullCalendar is the only candidate
  that is (a) genuinely maintained, (b) MIT for the month-grid view this site
  uses, (c) usable with zero build step via the `index.global.min.js` global
  build, and (d) themeable to the café palette through the `--fc-*` custom
  properties overridden (with `!important`, since the library injects its
  `<style>` later) in `<head>`. Rejected alternatives: TOAST UI Calendar
  (dormant since 2023, needs a build), vanilla-js-calendar / vanilla-calendar
  (date *pickers*, not event-display calendars), SimpleCalendarJS (78KB,
  npm-oriented, unproven). The hand-rolled grid is kept as the zero-dependency
  fallback so a CDN outage still leaves a working calendar. Research notes:
  `ralph/ralph.log`. Sizes: `index.global.min.js` ≈ 282KB raw / ~90KB gzip.
- **Calendar weekday math is the exception to the no-`Date` rule.** The
  calendar must not call `new Date(start)` in the visitor's local tz — a
  near-midnight ride would land on the wrong weekday for non-Eastern visitors.
  The `start` ISO string already carries the Eastern offset, so its Y-M-D
  prefix *is* the Eastern wall-clock date; the code builds
  `new Date(Date.UTC(y, m-1, d))` and reads `getUTCDay()` / `getUTCDate()`.
  That returns the same weekday in any timezone. Display times still come from
  the precomputed `date_display`/`time_display`.
- **`[hidden]` needs `display: none !important`** in the CSS. It was added so
  the `.view-toggle` (which set `display: flex`) couldn't override the UA's
  `hidden` rule and show an empty toggle before JS hid it; the toggle is gone,
  but the rule is kept as a global safety net for any future `[hidden]`.
- `events.json` display strings (`date_display`, `time_display`) are
  precomputed; the JS must **not** re-format dates with `Date`, or visitors
  outside Eastern see wrong times. `updated_at` is likewise formatted by
  **regex-slicing the ISO string** (it already carries the Eastern offset) —
  keep it that way.
- The DOM is built with `createElement`/`textContent`, never `innerHTML`, so
  feed text can't inject markup. Keep that.
- **JS module split (2026-08-13):** the ride JS is three plain scripts in
  dependency order — `js/ride-card.js` → `js/calendar.js` → `js/app.js` — each
  an IIFE attaching its public API to the shared `window.BCB` namespace, all
  loaded `defer` after the FullCalendar CDN script. Chosen over native ES
  modules (`<script type="module">`): both need zero build step and Pages
  serves either as-is, but plain scripts keep the node DOM-shim's
  `vm.runInContext` verification trivial (run the three files in order against
  a shimmed `document`/`fetch`/`window`), and the cross-file references
  (`calendar.js` calls `BCB.openRideModal`, `app.js` calls
  `BCB.renderCalendarFull`) resolve at call time, after every file has loaded.
  `window.BCB` is the one shared global — never leak anything else onto
  `window`. Dependency-order contract: `ride-card.js` owns the constants
  (`PARTIFUL`, `MONTHS`, `DOW`), `el()`, `pad2()`, the `rideCard` builder, and
  `buildIcs`/`downloadIcs`/`googleCalUrl`; `calendar.js` owns the calendar
  renderers and Eastern date math — `renderCalendarFull(events, mountEl)`
  appends its `.calendar` box into `mountEl` (app.js passes `#schedule`) BEFORE
  calling `FullCalendar.render()` (the holder must be in the document at render
  time, or FC measures 0-wide columns — see the Calendar-view bullet); the
  fallback `monthGrid()` returns a `.calendar` box `app.js` appends itself;
  `app.js` owns DOM refs, `currentData`, the modal, and the bootstrap.
- Verifying the JS: no browser here, but `node` (v25+) is installed. The node
  DOM-shim `readFileSync`s `site/js/ride-card.js`, `calendar.js`, `app.js` (in
  that order) and evals each against a shimmed `document`/`fetch`/`window`
  (no regex-pulling out of the HTML) — `window` points at the vm global so the
  `window.BCB` namespace survives across files — that's how the happy path,
  empty, missing-rsvp, 404, the ride-detail modal (open via chip /
  FullCalendar `eventClick`, close via backdrop / Escape / `×`,
  stale-instance-destroyed-on-re-render), and the deferred `data-bg`
  background-image (unset before the window `load` event, set after — the
  shim fires `context.handlers.load()` to prove it) cases are checked.
- Sections/ids: `#next-ride`, `#rides`, `#first-ride`, `#about`, `#contact`;
  the ride-detail overlay is `#ride-modal` (not a `<section>`). The hero CTA
  anchors to `#next-ride`. (`#about` absorbed the former `#links` "Find us"
  section on 2026-08-13 — the Instagram/Partiful links now live under the
  About us heading; there is no `#links` section anymore.)
- **Contact section** (`#contact`, home page only): three `.links` cards —
  email `mailto:boscafebikers@gmail.com`, Instagram DM
  (`https://instagram.com/bostoncafebikers`), and the WhatsApp group invite
  (`https://chat.whatsapp.com/JtpmhMgE8EmFRGOXrNhT1w`). Same email is on the
  donate page's WIP note. The sub-pages (gallery/shop/meta/donate) have no
  contact section — only the shared footer.
- Verified well-formed by feeding it through `html.parser` (no unclosed or
  mismatched tags).

## `tests/test_fetch_rides.py`

Run with `.venv/bin/python -m pytest tests/ -q` (69 passing). Notes:

- There is no `conftest.py` / packaging; the test file puts `scripts/` on
  `sys.path` itself and does `import fetch_rides`.
- Pinned clock is `NOW = 2025-01-01 12:00 America/New_York`, passed as
  `parse_events(..., now=NOW)`. Never call the parser without `now` in a test.
- Coverage: past + cancelled filtering, sort order, folded-RSVP extraction,
  RSVP line stripped from description, `-04:00` offsets, precomputed display
  strings, non-ASCII round-trip, `now` boundary (`>=` keeps an event starting
  exactly now), empty result, malformed feed → `FeedError`, `main()` exit codes
  (0 happy path, 1 for broken feed / missing file / unset env var), `end`
  extraction (fixture DTEND → ISO, missing DTEND → null), hidden-location
  placeholder → `location: null` + `location_hidden: true`, two leak tests
  asserting the feed URL never reaches an error message, and the event-page
  enrichment (fixture `event-page.html` → image extracted; sidecar wins;
  fetch failure is soft; `--ics-file` runs never enrich, live-feed runs do).
- The suite passes under any system timezone (verified with `TZ=Asia/Tokyo`) —
  keep it that way; assert on explicit offsets, not on local time.
