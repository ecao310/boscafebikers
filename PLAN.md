# Boston Café Bikers — Plan

Static site for Boston Café Bikers ("exploring the city one café at a time"),
with a ride schedule auto-synced from the organizer's Partiful ICS calendar feed.

## Backlog — phase 2: deploy to GitHub Pages

- [x] Pre-flight: confirm local `master` is pushed to the `boscafebikers` remote
  and is the repo's default branch; `git grep` tracked files for the real ICS
  feed URL; working tree clean. Record the default branch name in CLAUDE.md.
- [x] Add `.github/workflows/pages.yml`: `actions/upload-pages-artifact`
  (`path: site`) + `actions/deploy-pages`, `permissions: pages: write /
  id-token: write / contents: read`, `concurrency: pages`, triggers `push` (default
  branch) + `workflow_dispatch`. Validate the YAML with `ruby -ryaml`.
- [x] Switch the repo's Pages source to GitHub Actions via `gh api` (create the
  Pages site if absent), push, and watch the first deploy with `gh run watch`.
  Record the live URL in CLAUDE.md.
- [x] Verify the live deploy: `curl` the site URL and its `events.json` (both
  200, JSON valid, `events` match the committed file), no absolute-path breakage
  under the `/<repo>/` project subpath.
- [x] Wire freshness: a ride-schedule update must redeploy the site even though
  `GITHUB_TOKEN` pushes don't fire `push` triggers. Verify via a `sync.yml`
  `workflow_dispatch` run.
- [x] Fix the README's GitHub Pages section — the "folder `/site`" instructions
  are impossible. Document the Actions deploy, the live URL, and `site/CNAME`
  for a future custom domain.
- [x] Final CLAUDE.md pass (file map + "Deployment" section + manual redeploy),
  then full end-to-end verification and `RALPH_DONE`.

## Backlog — phase 1: build (complete)

- [x] Init repo: git init, .gitignore, PLAN.md (copy of this Backlog),
  CLAUDE.md with file map and conventions, requirements.txt (icalendar, requests)
- [x] Create tests/fixtures/sample.ics with 4 realistic Partiful-style events:
  2 future, 1 past, 1 cancelled; include RSVP URLs in descriptions
- [x] Write scripts/fetch_rides.py per spec; run it on the fixture and confirm
  site/events.json contains exactly the 2 future events, sorted by date
- [x] Add tests/test_fetch_rides.py (pytest): past-event filtering, cancelled
  filtering, RSVP link extraction, timezone correctness, malformed-feed exit code
- [x] Write site/index.html hero + about + first-ride + links sections with
  placeholder schedule area
- [x] Add schedule rendering JS: load events.json, render ride cards
  (date, time, start location, RSVP button), last-updated stamp, empty-state
  fallback to the Partiful profile
- [x] Create .github/workflows/sync.yml per spec (cron `0 */6 * * *`,
  workflow_dispatch, commit-if-changed guard)
- [x] Add README.md: what this is, how to get the ICS URL from Partiful
  (Settings → Calendar Sync → Apple Calendar, swap `webcal://` for `https://`),
  how to set the repo secret, how to deploy on GitHub Pages
- [x] End-to-end check: fresh clone simulation — script on fixture, open site,
  confirm rides render; fix anything broken

## Discovered work

(append new tasks here as `- [ ]` items; treat them as part of the Backlog)

- [ ] The `PARTIFUL_ICS_URL` secret is **not set** on the repo (`gh secret list`
  is empty), so any `sync.yml` run fails at the fetch step. Only a human holding
  the real feed URL can set it — do **not** invent one. The "wire freshness"
  task must therefore verify the sync→deploy chain some other way (e.g. confirm
  the deploy job is reached / correctly skipped), and the README should say the
  secret is a required setup step that is still outstanding.
- [x] Pages is currently on the **legacy** source publishing the repo root, so
  <https://ecao310.github.io/boscafebikers/> serves the README, not the site.
  Converting it is part of the "switch Pages source" task, not a separate fix.
  (Done in iteration 12: `build_type: workflow`, run 29714522817 deployed
  `site/`; the live URL now serves `index.html`.)
