# Boston Café Bikers — Plan

Static site for Boston Café Bikers ("exploring the city one café at a time"),
with a ride schedule auto-synced from the organizer's Partiful ICS calendar feed.

## Backlog 4

- [x] Add footer (Added a consistent footer to all five pages: café tagline `.footer-brand`, a `.footer-nav` mirroring the tab links, and Instagram/Partiful links; styles live once in `site/styles.css` next to the nav. The old per-page footers were inconsistent — `index.html` linked "RSVP to a ride", the sub-pages linked "Home".)
- [x] Remove Sync rides now functionality. Instead, make the Last updated ... a clickable link to the github action (Removed the `.sync-bar` button/status/ghost-link and the `syncNow()` JS from `site/index.html`; the "Last updated … ET." stamp is now `#updated-link`, an anchor to the `sync.yml` workflow on GitHub Actions (`rel=noopener target=_blank`). The `<p id="updated">` is `hidden` until `updated_at` renders, so a failed load leaves no empty focusable link. Verified with the node DOM-shim: happy path (link visible, correct href + "Last updated … ET." text, no sync button), empty-data and fetch-failure paths (line stays hidden); 59 pytest pass; HTML well-formed.)
- [x] Contact Us section includes email and instagram and whatsapp https://chat.whatsapp.com/JtpmhMgE8EmFRGOXrNhT1w (The `#contact` section on `site/index.html` now carries three `.links` cards: `mailto:boscafebikers@gmail.com`, Instagram DM (`@bostoncafebikers`), and the WhatsApp group invite `https://chat.whatsapp.com/JtpmhMgE8EmFRGOXrNhT1w`. The volunteer-DM paragraph now names all three channels. The email was already in use on the donate page. HTML well-formed on all five pages; 59 pytest pass; no JS touched.)

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
- [x] Move ralph-related filed to the ralph directory. adjust instructions to accomodate.
- [x] Research better options for calendar display. Wrap the text. Research and decide on  a suitable open source calendar display solution. (Adopted FullCalendar 6 via CDN; hand-rolled grid kept as fallback. Decision + sizes in CLAUDE.md.)
- [x] Create a donation section/page. leave it blank/WIP for now. Include navigation to the page, as well as the shopify and meta pages.
- [x] The RSVP on Partiful button still links to the profile page instead of the event page. Extract event link from the description in events.json. 
- [x] Clean up the events description. Remove the rsvp link from the description, but keep the button and the link in the button.
- [x] Clean up htmls. Consider creating a unified style sheet. (Created `site/styles.css` holding the shared café palette + base/nav/hero/footer styles; every page now `<link>`s it and keeps only its page-specific rules in a small inline `<style>`. Verified rule-for-rule that no original CSS declaration was lost, HTML stays well-formed, 59 tests pass.)
- [x] Research how https://bostoncyclistsunion.org/events/month/ handles event details and display. Consider incorporating their method. (BCU uses a month grid with a repeated list below + dedicated `/event/{slug}/` detail pages via WordPress/The Events Calendar. Decision: keep FullCalendar month grid; their click-for-details is exactly the "modal on calendar click" task below; incorporated their add-to-calendar exports now as a "Google Calendar" link beside each ride's `.ics` download. Findings + sizes in ralph.log.)
- [x] Remove list of events option. Instead, show the next event in one section near the top, and the existing section becomes calendar only. (New `#next-ride` section right under the hero renders `events[0]` as a featured `.ride.next-ride` card via the shared `rideCard` builder; hero CTA now anchors to `#next-ride`. The `#view-toggle` and list rendering are gone — `#rides` is calendar-only, keeping FullCalendar 6 as primary renderer and the hand-rolled grid as fallback. `setNextRide()` shows a note + Partiful button when the calendar is empty or the fetch fails. Verified: 59 tests pass, HTML well-formed, node shim exercises happy path + empty + 404 + FullCalendar path (incl. destroy-on-re-render).)
- [x] On calendar, clicking on an event should show the event details in a modal or popup. (Added a `#ride-modal` overlay reused by both renderers: FullCalendar `eventClick` (preventDefault + `openRideModal(event.extendedProps.data)`) and the fallback grid's `.ride-chip` — now a `<button>`, not an `<a>`, with a UA-button reset in CSS. Modal content is the *same* `rideCard` builder as the featured next-ride card, so details + RSVP/.ics/Google-Calendar actions can't drift. Closes via `×`, Escape, or backdrop click; restores focus + body scroll. FullCalendar events keep `url` so middle/ctrl-click still opens RSVP in a new tab. Verified with the node DOM-shim: 24 checks across fallback, FullCalendar, empty, 404, and re-render-destroy; 59 pytest pass; HTML well-formed.)

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
- [x] README.md's "Deploying" section still says the `PARTIFUL_ICS_URL` secret
  is **not set** ("This secret is not set yet … It is the one remaining manual
  setup step"), but `gh secret list` shows it **is** set (since 2026-07-20) and
  the sync bot commits real feed updates every 6h. The README contradicting
  CLAUDE.md could mislead a future iteration — fix the wording when this task
  is picked up. (Fixed: the blockquote in "Setting the repo secret" now states
  the secret IS set since 2026-07-20, the cron sync runs automatically, and the
  manual steps apply only to a fresh fork. `gh secret list` confirms
  `PARTIFUL_ICS_URL` present, updated 2026-07-20.)
- [x] The sync bot's last `events.json` commit (`63c17d6`, 2026-08-12 14:10 UTC)
  was generated **before** the text-cleanup / RSVP-link code landed on `master`
  (committed ~18:11 UTC the same day), so the deployed data was stale: the ride
  title kept its ` | Partiful` suffix, the description still carried the
  "View this event on Partiful at …" invite line, and `rsvp_url` was `null`
  (the RSVP button fell back to the group profile). The code was always
  correct — the fixture exercises all three — so this iteration regenerated
  `site/events.json` by re-running the committed cleaning pipeline over the raw
  fields already in the file (no live-feed access). `rsvp_url` now points at
  the actual event page and the invite line is stripped. The next scheduled
  sync reconciles with the live feed either way.
- [x] Post-`RALPH_DONE`, a fresh iteration found an **uncommitted copy edit** in
  `site/index.html` (removed the "We're run by volunteers, so" intro from the
  Contact-copy paragraph and reflowed the `#updated-link` anchor attributes —
  no semantic change to the link). Verified it (html.parser well-formed on all
  five pages, 59 pytest pass, node DOM-shim happy path 12/12 incl. the
  `#updated-link` stamp/href/rel), committed it, and pushed to `master`; the
  push-triggered `pages.yml` deploy was watched and the live URL re-curled to
  confirm the updated copy is served. See ralph.log for the run details.
