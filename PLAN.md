# Boston Café Bikers — Plan

Static site for Boston Café Bikers ("exploring the city one café at a time"),
with a ride schedule auto-synced from the organizer's Partiful ICS calendar feed.

## Backlog 3

- [x] Include "Contact Us" section for cities/orgs to reach out
- [x] New blank pages for Shopify integration and meta business integration. leave as separate pages and just put a WIP sign. no functionality.
- [x] Toggle between list and calendar view of future rides
- [x] Move notes from claude.md to ralph.log
- [x] Add gallery page
- [x] Tab header navigation
- [x] Ability to add images to rides
- [x] ICS download for each event
- [x] RSVP on Partiful button should link to actual event, not just the café bikers account page
- [x] Clean up text imported from Partiful
- [x] Attempt to include start and end locations from Partiful
- [x] Button to trigger calendar sync
- [ ] Move ralph-related filed to the ralph directory. adjust instructions to accomodate.
- [ ] Research better options for calendar display. Wrap the text. Research and decide on  a suitable open source calendar display solution.
- [ ] Create a donation section/page. leave it blank/WIP for now. Include navigation to the page, as well as the shopify and meta pages.

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

- [x] The `PARTIFUL_ICS_URL` secret is **not set** on the repo (`gh secret list`
  is empty), so any `sync.yml` run fails at the fetch step. Only a human holding
  the real feed URL can set it — do **not** invent one. The "wire freshness"
  task must therefore verify the sync→deploy chain some other way (e.g. confirm
  the deploy job is reached / correctly skipped), and the README should say the
  secret is a required setup step that is still outstanding.
  — Resolved 2026-08-12: `gh secret list` shows `PARTIFUL_ICS_URL` **is** set
  (since 2026-07-20); the sync bot commits real feed updates every 6h. This
  note is stale.
- [x] Pages is currently on the **legacy** source publishing the repo root, so
  <https://ecao310.github.io/boscafebikers/> serves the README, not the site.
  Converting it is part of the "switch Pages source" task, not a separate fix.
  (Done in iteration 12: `build_type: workflow`, run 29714522817 deployed
  `site/`; the live URL now serves `index.html`.)
- [x] Commit `562f184` (hidden-location placeholder) accidentally reverted the
  `[x]` on "Clean up text imported from Partiful" back to `[ ]`, even though
  that task's code (title suffix/whitespace + description cleanup in
  `4f54030`) was complete and 59 tests were green. Restored the marking and
  verified the cleanup end-to-end on the fixture.
- [ ] README.md's "Deploying" section still says the `PARTIFUL_ICS_URL` secret
  is **not set** ("This secret is not set yet … It is the one remaining manual
  setup step"), but `gh secret list` shows it **is** set (since 2026-07-20) and
  the sync bot commits real feed updates every 6h. The README contradicting
  CLAUDE.md could mislead a future iteration — fix the wording when this task
  is picked up.
