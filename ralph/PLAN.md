# Boston Café Bikers — Plan

Static site for Boston Café Bikers ("exploring the city one café at a time"),
with a ride schedule auto-synced from the organizer's Partiful ICS calendar feed.

## Backlog 9
- [x] Verify the dev branch still publishes to a /preview page.
- [x] Bug: on mobile the FullCalendar chips only show the clipped time ("1 O…") — the ride title never appears. Hide the event time on chips (displayEventTime: false or list-item dots below 560px); the time is already on the card and in the modal.
- [x] Bug: 11 archived rides have a Google Maps link as their `location` (organizer pasted the meeting-point link into Partiful's Location field). It renders as a raw URL overflowing the card. Detect a maps URL in `_clean_location` → `location: null` + new `location_url`; render it as a "Meeting point on Google Maps" link in rideCard; carry the field through archive_events merge; add `overflow-wrap: anywhere` to `.where`.
- [ ] Bug: 4 routes were entered café→start (Localito, Scooper Bowl, both Ice Cream Crawl routes), so "from <café>" and the map's Start/End labels are backwards. If `end` matches the Bluebikes pattern and `start` doesn't, swap start/end (and reverse points) when parsing the route.
- [x] Bug: in the ride modal on desktop the map + description fill the 88vh dialog and the RSVP / calendar buttons sit below the scroll edge with no affordance. Cap the map inside the modal (~240px) and/or pin `.ride-actions` at the bottom of the dialog so the primary CTA is always visible.
- [ ] The calendar shows past rides now, so "Upcoming rides" / "Every upcoming ride on one calendar" is wrong. Rename the section to "Ride calendar" and add a one-line legend (dashed = past ride, tap for details).
- [ ] Say when rides happen in "Your first ride". The archive shows 28 of 34 rides were Saturday or Sunday, most at 10 or 11 am, routes 4–5 mi: lead with something like "Most rides are Saturday or Sunday mornings, 10 or 11 am, 3–5 flat-ish miles."
- [ ] "Where we've been": a café list rendered client-side from events-past.json — each café visited, newest first, with the ride date and a link to its Partiful page. Own page (cafes.html, add to nav) or a section on index; no new sync work.
- [ ] Subscribable calendar: have the sync re-export a public `site/rides.ics` (upcoming rides only, no secret URL, hidden locations omitted) and add a "Subscribe in your calendar app" button next to the calendar, alongside the per-ride exports.

## Backlog 8
- [x] Bug: map graphic has no background. find a way to add the tile.
- [x] update start/end locations on cards to be just start location. starts are always bluebikes, so show the detail instead e.g. cleveland circle for the o'some sunday ride.
- [x] Contact Us's Back to the ride page button isn't vertically aligned

## Backlog 7
- [x] find a way to deploy this dev branch without disturbing main. 
- [x] I want past rides to stay on the calendar. Do this by moving old rides from events.json to events-past.json. Or do it some other way if there's a better way.
- [x] remove the background images from all sections below the calendar. Reset colors to be readable like the calendar.
- [x] Move the Contact Us section to its own page. Keep the section too because we'll change it in the next loop. Set up a way to send an email directly from the page. Make it email me at ecao.csindie@gmail.com for now, but make the email changeable.
- [x] Replace the Contact Us section with "Help Cafe Bikers Behind the Scenes". Every ride has a crew with ride leaders and sweepers, people filming and editing. If that's you, we'd love to meet you. Then the 3 buttons already there.
- [x] From partiful, grab the link to the Google Maps route. 
- [x] Extract distance from map and add to ride details
- [x] Use map screenshot as image

## Backlog 6

- [x] I like how it looks on mobile, but the text is harder to read on desktop.
- [x] Reduce size of hero section on index
- [x] remove shop, meta business from top tabs for now. keep on footer.

> **Note convention (2026-08-13):** completed bullets keep their original
> task wording — just flip `[ ]` to `[x]`, with no `(Done: …)` write-up
> appended to the bullet. Per-iteration notes go in `ralph/ralph.log`
> (gitignored). It's still good to add new bullets when there's new work.

## Backlog 5

- [x] Make top navigation bar not stay permanently on screen.
- [x] Combine about us and find us sections.
- [x] Add photos to gallery page
- [x] Add more background images from gallery page
- [x] On mobile, calendar gets stretched vertically to fit names. Avoid huge cell heights. Truncate or something else.
- [x] On mobile, rsvp buttons take up only half the size. Change so it looks better. decide yourself how.
- [x] Revert plan.md bullet points back to their original states. look through git if needed. write instructions to leave notes in ralph.log and keep the bullet points as is. it's still good to write more bullet points if needed.
- [x] Improve readability on index pages. background images make them hard to read.

## Backlog 5

- [x] Make a plan to convert to javascript. Create bullet points in this backlog and do them on the next loop. Features to include: background images that load last. explore new ways for the calendar refresh/fetch backend. mobile-first.
- [x] Extract the inline ride-script out of `site/index.html` into a real JS file layer — `site/js/app.js`, loaded with a plain `<script src="js/app.js" defer>` (relative, never root-absolute) in place of the inline `<script>` block — and update the node DOM-shim verification to load the extracted file instead of regex-pulling the script from the HTML. No behavior change: keep the ES5 code and the `defer`'d FullCalendar CDN script as-is. Verify: node shim happy/empty/404/modal cases still pass, HTML well-formed, pytest stays green.
- [x] Split `site/js/app.js` into per-concern modules and modernize the syntax to ES2017+ (const/let, arrow functions, template literals): `ride-card.js` (rideCard builder + buildIcs/downloadIcs + googleCalUrl), `calendar.js` (FullCalendar renderer + fallback month grid + eastern date math), `app.js` (fetch + render + next-ride + modal + bootstrap). Decide and record plain-script-tags-in-dependency-order vs native ES modules (no build step either way — GitHub Pages serves the files as-is); the node shim must load the new layout. Verify: node shim cases, HTML well-formed, pytest green.
- [x] Deferred background images: add a `data-bg` mechanism where JS sets `background-image` only after `window.load` (or `requestIdleCallback`), so a background image never blocks first paint / LCP, with a no-JS fallback color on the element and ride `<img>` photos kept `loading="lazy"`. Apply it to the first real background image — a hero café photo when the organizer provides one; otherwise verify the mechanism with a placeholder URL so the task isn't blocked on an asset. Verify: node shim asserts `background-image` is set only after the load event and the fallback color renders before it.
- [x] Explore new ways for the calendar refresh/fetch backend and record a decision. Today: a GitHub Actions cron every 6h fetches the secret ICS, commits `site/events.json` only when rides change, and the change redeploys Pages — so freshness is ≤6h plus a deploy per change. Evaluate (a) a client-side fetch of a public Partiful endpoint (profile page / embedded API, CORS permitting — never the secret ICS URL) so the page can be fresher than 6h with no redeploy, (b) a serverless proxy (Cloudflare Worker / Deno Deploy / Vercel function) that holds the secret server-side and emits public JSON the static site fetches, (c) keeping the cron. Write the comparison + chosen path in `ralph/ralph.log` and a one-line decision in CLAUDE.md; implementation, if a winner emerges, is a follow-up bullet.
- [x] Enrich `site/events.json` from Partiful's public per-event pages (follow-up to the fetch-backend decision): during the sync, fetch each event's public page `/e/<id>` (or its `calendarFile` ICS) and merge the richer data it exposes — e.g. `image` (every ride currently has `image: null` even though the event page has one), full location info. The per-event GCS ICS is CORS-enabled for `https://ecao310.github.io` (verified) and the page is unauthenticated, so this needs no new secret — but event IDs still come from the secret feed, so it stays a sync-time enrichment, not a client-side feed. Verify: sync on fixture produces a ride with `image` set; node shim + pytest stay green.
- [x] Mobile-first audit of the JS-rendered UI at 380px: touch targets (calendar chips, modal close, action buttons) ≥44px, the ride-detail modal fits within 88vh and scrolls, ride titles wrap in both calendar renderers (no horizontal scroll, no truncation), tap-vs-hover affordances are correct. Fix whatever the audit finds. Verify: node shim cases still pass, HTML well-formed.
- [x] make it so top navigation bar doesn't scroll with page. just leave it at top.
- [x] move background image to 2nd section. create setting to increase opacity of background to improve readability.
- [x] upcoming ride calendar looks completely broken on web.

## Backlog 4

- [x] Add footer
- [x] Remove Sync rides now functionality. Instead, make the Last updated ... a clickable link to the github action
- [x] Contact Us section includes email and instagram and whatsapp https://chat.whatsapp.com/JtpmhMgE8EmFRGOXrNhT1w

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
- [x] Research better options for calendar display. Wrap the text. Research and decide on  a suitable open source calendar display solution.
- [x] Create a donation section/page. leave it blank/WIP for now. Include navigation to the page, as well as the shopify and meta pages.
- [x] The RSVP on Partiful button still links to the profile page instead of the event page. Extract event link from the description in events.json. 
- [x] Clean up the events description. Remove the rsvp link from the description, but keep the button and the link in the button.
- [x] Clean up htmls. Consider creating a unified style sheet.
- [x] Research how https://bostoncyclistsunion.org/events/month/ handles event details and display. Consider incorporating their method.
- [x] Remove list of events option. Instead, show the next event in one section near the top, and the existing section becomes calendar only.
- [x] On calendar, clicking on an event should show the event details in a modal or popup.

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
- [x] The first live sync of the new past-rides archive revealed the Partiful
  feed carries **34** past events (back to 2025-09-19), not the 6 recoverable
  from git history — and they arrive **unenriched**, because only the upcoming
  list is enriched. 28 archived rides therefore had no image, no route and no
  map. Fixed with `scripts/enrich_archive.py`: a bounded backfill that walks
  the archive newest-first and enriches at most 8 never-checked rides per sync,
  so the whole archive fills in over a few runs and then costs nothing.
  (Backfilled locally: 34/34 archived rides now have an image, 7 have routes
  and maps — the older rides never had a route link on Partiful.)
- [x] Post-`RALPH_DONE`, a fresh iteration found an **uncommitted copy edit** in
  `site/index.html` (removed the "We're run by volunteers, so" intro from the
  Contact-copy paragraph and reflowed the `#updated-link` anchor attributes —
  no semantic change to the link). Verified it (html.parser well-formed on all
  five pages, 59 pytest pass, node DOM-shim happy path 12/12 incl. the
  `#updated-link` stamp/href/rel), committed it, and pushed to `master`; the
  push-triggered `pages.yml` deploy was watched and the live URL re-curled to
  confirm the updated copy is served. See ralph.log for the run details.
