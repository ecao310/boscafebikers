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
- `ralph.log` is gitignored loop scratch — do not commit it.

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
- **Still outstanding (needs a human):** the `PARTIFUL_ICS_URL` secret is unset,
  so every scheduled sync fails at fetch and no deploy is chained. The site
  serves the committed fixture-derived `events.json` until then.

Details per iteration: "Deployment: pre-flight findings", "Deployment: live",
"Deployment: live verification", "Freshness chain: sync → deploy" below.

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
HTTP, not `file://`, for `fetch("events.json")` to work).
Iteration 9: end-to-end check — **phase 1 complete, nothing broken.**
Iteration 10: phase-2 pre-flight (see "Deployment: pre-flight findings").
Iteration 11: `.github/workflows/pages.yml`.
Iteration 12: Pages source switched to Actions, pushed, first deploy green —
**the site is live** (see "Deployment: live").
Iteration 13: live-deploy verification (see "Deployment: live verification").
Iteration 14: freshness chain — `sync.yml` calls `pages.yml` via `workflow_call`
(see "Freshness chain").
Iteration 15: README rewritten for the real deploy — the impossible
"folder `/site`" instructions are gone, replaced by the Actions source (+ the
`gh api -X PUT … build_type=workflow` headless form), the live URL, the manual
`gh workflow run pages.yml` redeploy, why the sync→deploy chain uses
`workflow_call`, the no-root-relative-paths rule, and `site/CNAME` for a future
custom domain. Also added a callout that `PARTIFUL_ICS_URL` is still unset, and
listed `pages.yml` in the repo-layout table.
Iteration 16: final CLAUDE.md pass — added the consolidated "## Deployment"
section above (Pages source, all three trigger paths, manual redeploy, the
subpath rule, the outstanding secret) and ran the phase-2 end-to-end check.
**Phase 2 complete.** Evidence: `pytest tests/ -q` 24 passed; working tree
clean; fetch-on-fixture → `promote_events.py` → "Rides unchanged" and
`git diff --quiet -- site/events.json` clean (so the chain correctly skips the
deploy on a no-op sync); `gh workflow run pages.yml` run 29715268132 green in
14s; live `/` and `/events.json` both 200 and the served `events` byte-equal to
the committed `site/events.json`. (The runners now warn that `actions/checkout@v4`
et al. target the deprecated Node 20 and are forced onto Node 24 — harmless
today, but a future iteration should bump the action majors.)

### Deployment: pre-flight findings (iteration 10)

State of the repo/GitHub side as of the start of phase 2:

- Default branch `master` (local + GitHub), remote `boscafebikers`, repo is
  **public** at <https://github.com/ecao310/boscafebikers>. Local `master` was
  2 commits ahead; pushed, now in sync. Working tree clean.
- `git grep` over all tracked files for `webcal://`, `partiful.com`,
  `calendar/ical`, `*.ics`: **no real feed URL anywhere.** Every hit is the
  public profile URL, a fixture RSVP link, or prose about the `webcal://`
  scheme. Re-run that grep before any phase-2 commit.
- A stray `pages-deploy/` git worktree (same commit as `master`, no changes)
  was left behind by an earlier run; removed with `git worktree remove` +
  `git branch -D`. If `git status` shows an untracked dir that turns out to be
  a worktree, that's what it is — check `git worktree list` first.
- **Pages already exists but is misconfigured**: `gh api repos/:owner/:repo/pages`
  returns `build_type: "legacy"`, `source: {branch: master, path: "/"}`, i.e.
  it's publishing the *repo root* (README), not `site/`. Live URL is already
  allocated: <https://ecao310.github.io/boscafebikers/>. Switching to the
  Actions source is a `PUT` to that endpoint with `build_type: "workflow"` —
  the site does **not** need creating, only converting.
- **`PARTIFUL_ICS_URL` is not set** — `gh secret list` is empty. See
  "Discovered work" in PLAN.md; the freshness task must account for a sync run
  that fails at fetch.

## `.github/workflows/pages.yml` (iteration 11)

`checkout` → `actions/configure-pages@v5` → `actions/upload-pages-artifact@v3`
(`path: site`) → `actions/deploy-pages@v4`, with `permissions: contents: read /
pages: write / id-token: write`, `concurrency: pages` (`cancel-in-progress:
false`), and the `github-pages` environment carrying the deploy URL.

- Triggers so far: `push` on **`master`** (the default branch — there is no
  `main`) and `workflow_dispatch`. The sync→deploy chain is *not* wired yet;
  that's the "wire freshness" backlog task, and it must not rely on `push`
  because `GITHUB_TOKEN` commits don't fire `push` triggers.
- Why Actions and not "deploy from a branch": that source only offers `/` or
  `/docs`, and the site lives in `site/`.
- Pushed in iteration 12, after the Pages source was flipped to Actions (see
  "Deployment: live" below).
- Validated with `ruby -ryaml -rjson -e '…'` (parses; the `on:` key shows up as
  `true` in the Ruby dump — YAML 1.1 boolean coercion, harmless).

### Deployment: live (iteration 12)

**The site is live at <https://ecao310.github.io/boscafebikers/>**, served from
`site/` by `pages.yml` (Actions source).

- Flipping the source is headless:
  `gh api -X PUT repos/:owner/:repo/pages -f build_type=workflow`. Confirm with
  `gh api repos/:owner/:repo/pages` → `build_type: "workflow"`, `status: "built"`.
  (`source: {branch: master, path: "/"}` is left over from the legacy config and
  is ignored once `build_type` is `workflow` — don't try to "fix" it to `/site`;
  that value is not accepted.)
- **Gotcha:** right after the flip, the legacy `pages-build-deployment`
  workflow can still have a run queued, and it holds the `github-pages`
  environment, so the new "Deploy site to Pages" run sits `queued` for many
  minutes. Cancel the stale legacy run (`gh run cancel <id>`) and the Actions
  deploy starts within seconds (job itself takes ~15s).
- Verified live: `curl -o /dev/null -w '%{http_code}'` on `/` and
  `/events.json` = 200/200; the page `<title>` is the real one and
  `events.json` decodes to the 2 fixture rides (Charles River Loop → Tatte,
  Minuteman Bikeway to Lexington).
- Redeploy by hand: `gh workflow run pages.yml --ref master` (then
  `gh run watch <id>`).

### Deployment: live verification (iteration 13)

Checked against the real URL, not the local files:

- `curl` on `/` and `/events.json` → **200 / 200**. The served `events.json`
  parses and is byte-for-byte equal to the committed `site/events.json`
  (same `events`, same `updated_at`); the served `index.html` is identical to
  `site/index.html`.
- **No project-subpath breakage.** Nothing in the page uses a root-relative
  (`/…`) URL: the only refs are `href="#rides"`, two absolute
  `https://partiful.com/…` / instagram links, a `data:` favicon, and the
  relative `fetch("events.json", {cache:"no-cache"})`. Keep it that way — the
  site is served from `/boscafebikers/`, so any leading-slash path would 404.
- Rendering re-verified against the **live** page with the node shim trick from
  iteration 9 (`/tmp/render_check.mjs`: fetch the live HTML, regex out the last
  `<script>`, `eval` it against a fake `document` whose `innerHTML` setter
  throws, and a `fetch` rebased on the live base URL). Both ride cards rendered
  with `.when`/`.where`/description/RSVP hrefs, plus the "Last updated … ET."
  stamp.

### Freshness chain: sync → deploy (iteration 14)

`sync.yml` **calls** `pages.yml` instead of relying on `push`:

- `pages.yml` gained a `workflow_call:` trigger. `sync.yml`'s `sync` job now
  exports `outputs.changed` (set to `true`/`false` by the commit step via
  `$GITHUB_OUTPUT`), and a second job
  `deploy: {needs: sync, if: needs.sync.outputs.changed == 'true', uses:
  ./.github/workflows/pages.yml}` redeploys only when a commit was actually
  pushed.
- **Why not `push`:** commits pushed with `GITHUB_TOKEN` don't fire `push`
  triggers, so the sync bot's commit would never redeploy the site. `workflow_run`
  would also work but fires on *every* sync, changed or not.
- **Permissions moved to job level.** `sync.yml` no longer has a top-level
  `permissions:` block: `sync` gets `contents: write`, `deploy` gets
  `contents: read / pages: write / id-token: write`. A reusable-workflow caller
  must declare the callee's permissions on the calling job.
- **Gotcha:** `pages.yml`'s checkout now passes `ref: ${{ github.ref }}`.
  Without it, checkout uses `github.sha` — which, in a workflow_call from
  sync.yml, is the commit from *before* the bot pushed the new
  `site/events.json`, so the deploy would publish stale rides. Keep that `with:`.
- Verified: a temporary `chain-test.yml` (workflow_dispatch → `uses:
  ./.github/workflows/pages.yml`, same shape as sync's deploy job) ran green —
  run 29715148012, all steps ✓ — proving `pages.yml` is callable and deploys;
  it was then deleted. Dispatching `sync.yml` (run 29715178013) failed at
  "Fetch rides" because `PARTIFUL_ICS_URL` is unset, and `deploy` correctly
  reported `skipped`. Live URL re-checked after: `/` and `/events.json` 200/200,
  served `events` byte-equal to the committed file.
- Still outstanding (not fixable here): the `PARTIFUL_ICS_URL` secret. Until a
  human sets it, every scheduled sync fails at fetch and no deploy is chained.

### End-to-end verification (how it was done, iteration 9)

Fresh-clone simulation in `/tmp`, everything offline:

1. `git clone` the repo → fresh `python3 -m venv .venv` + `pip install -r
   requirements.txt` → `pytest tests/ -q` = 24 passed.
2. Deleted `site/events.json`, regenerated it with `scripts/fetch_rides.py
   --ics-file tests/fixtures/sample.ics` → exit 0, exactly the 2 future 2030
   rides, sorted.
3. Served with `python -m http.server -d site 8765`; `/` and `/events.json`
   both 200.
4. Rendering was checked against the **served** page (not the file on disk):
   a small node script fetches `/`, regex-extracts the inline `<script>`,
   `eval`s it against a shim `document` (whose `innerHTML` setter *throws*, so
   the no-`innerHTML` rule is enforced) and a `fetch` rebased on the server
   URL, then dumps the DOM. Both ride cards, `.when`/`.where`/description/RSVP
   hrefs and the "Last updated … ET." stamp all rendered. Re-ran with an empty
   `events` array and with `events.json` deleted (real 404) → both fell back to
   a note plus the Partiful-profile button.
5. Workflow guard: fetch to a temp file → `promote_events.py` → "Rides
   unchanged", `git diff --quiet` clean (no bot commit). Repeated with an
   edited title → "Rides changed", diff dirty (would commit). Both correct.
6. `git grep` for feed-URL patterns in tracked files: only prose/code mentions
   of the `webcal://` scheme, no real URL. HTML re-validated with
   `html.parser` (no unclosed/mismatched tags).

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
