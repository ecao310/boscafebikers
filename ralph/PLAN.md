# Boston Café Bikers — Plan

Static site for Boston Café Bikers ("exploring the city one café at a time"),
with a ride schedule auto-synced from the organizer's Partiful ICS calendar feed.

## Backlog 5

- [x] Make a plan to convert to javascript. Create bullet points in this backlog and do them on the next loop. Features to include: background images that load last. explore new ways for the calendar refresh/fetch backend. mobile-first. (Planned. The site's JS is one ~445-line ES5 IIFE inlined in `site/index.html` — there is no `.js` file, module system, or build step, and the node DOM-shim verification regex-pulls that script out of the HTML. The conversion plan below: ① extract the IIFE into a real `site/js/` script layer, ② split it per concern and modernize to ES2017+, then the three requested features — ③ background images that load last, ④ a research/decision task on the calendar refresh/fetch backend, ⑤ a mobile-first audit of the JS-rendered UI. Each bullet is one loop-sized, verifiable task; the ordering is deliberate so each builds on the previous.)
- [x] Extract the inline ride-script out of `site/index.html` into a real JS file layer — `site/js/app.js`, loaded with a plain `<script src="js/app.js" defer>` (relative, never root-absolute) in place of the inline `<script>` block — and update the node DOM-shim verification to load the extracted file instead of regex-pulling the script from the HTML. No behavior change: keep the ES5 code and the `defer`'d FullCalendar CDN script as-is. Verify: node shim happy/empty/404/modal cases still pass, HTML well-formed, pytest stays green. (Done: the IIFE is extracted byte-for-byte into `site/js/app.js` (445 lines, round-trip verified against the original inline block), `site/index.html` loads it as `<script src="js/app.js" defer>` at the end of `<body>`, and the node DOM-shim reads the extracted file directly instead of regex-pulling the HTML. Defer ordering: FC's CDN script is `defer` in `<head>`, app.js `defer` at end of body, so FC executes first and the FullCalendar path is taken directly when the CDN loads; the hand-rolled grid fallback + load-hook still cover a blocked CDN. Verified: 50/50 node-shim checks (happy/empty/404/modal incl. chip + FC eventClick open, ×/Escape/backdrop close, stale-FC-instance destroyed on re-render), all 5 HTML pages well-formed, `node --check` OK, 59 pytest pass, local serve `/`, `/js/app.js`, `/events.json` all 200, feed-URL grep clean.)
- [x] Split `site/js/app.js` into per-concern modules and modernize the syntax to ES2017+ (const/let, arrow functions, template literals): `ride-card.js` (rideCard builder + buildIcs/downloadIcs + googleCalUrl), `calendar.js` (FullCalendar renderer + fallback month grid + eastern date math), `app.js` (fetch + render + next-ride + modal + bootstrap). Decide and record plain-script-tags-in-dependency-order vs native ES modules (no build step either way — GitHub Pages serves the files as-is); the node shim must load the new layout. Verify: node shim cases, HTML well-formed, pytest green. (Done: `app.js` is now three ES2017+ IIFEs sharing the `window.BCB` namespace — `ride-card.js` (constants `PARTIFUL`/`MONTHS`/`DOW`, `el()`, `pad2()`, `rideCard`, `buildIcs`/`downloadIcs`/`googleCalUrl`), `calendar.js` (`groupByMonth`/`monthGrid`/`destroyCalendar`/`renderCalendarFull` + Eastern date math, returns `.calendar` boxes instead of touching `#schedule`), `app.js` (DOM refs, `currentData`, `stamp`/`emptyState`/`render`, modal + `BCB.openRideModal`, FC load hook, `fetch` bootstrap). Chose **plain script tags in dependency order** over native ES modules — decision + reasoning recorded in CLAUDE.md and ralph.log. `index.html` loads `js/ride-card.js` → `js/calendar.js` → `js/app.js`, all `defer` after the FullCalendar CDN. The node DOM-shim loads the same three files in order against a shimmed `document`/`fetch`/`window`. No `var` left anywhere. Verified: node shim 50/50 (happy/empty/404/FC path/modal/FC load-hook), all five HTML pages well-formed, `node --check` clean on all three files, local-server smoke test 200 on `/`, `/js/ride-card.js`, `/js/calendar.js`, `/js/app.js`, `/events.json`, 59 pytest pass.)
- [x] Deferred background images: add a `data-bg` mechanism where JS sets `background-image` only after `window.load` (or `requestIdleCallback`), so a background image never blocks first paint / LCP, with a no-JS fallback color on the element and ride `<img>` photos kept `loading="lazy"`. Apply it to the first real background image — a hero café photo when the organizer provides one; otherwise verify the mechanism with a placeholder URL so the task isn't blocked on an asset. Verify: node shim asserts `background-image` is set only after the load event and the fallback color renders before it. (Done: `app.js` gains `applyBackgrounds()` — reads `[data-bg]` attributes and copies the URL into `background-image` only after `window.load` (with a `document.readyState === "complete"` guard), so the photo never blocks first paint/LCP. `<header class="hero">` carries `data-bg="images/jess-b-gracies-bikes.jpeg"`; the espresso gradient in `styles.css` is the no-JS/pre-load fallback, and `.hero.bg-loaded` adds `cover` sizing + a translucent espresso `::before` overlay (hero `.wrap` lifted above it) for text legibility. Ride `<img>` photos stay `loading="lazy"` in `rideCard`. The organizer's candidate hero photo was optimized from 5120×3838 @ 1.9MB to 1600×1199 @ 481KB (sips, quality 70; original backed up to /tmp). Node DOM-shim now mounts a `data-bg` hero and asserts `background-image` is unset before the window `load` event and set right after — 56/56 checks pass; node --check clean on all three JS files; all five HTML pages well-formed; local serve 200 on `/`, `/images/jess-b-gracies-bikes.jpeg`, and the JS/CSS; 59 pytest pass; feed-URL grep clean.)
- [x] Explore new ways for the calendar refresh/fetch backend and record a decision. Today: a GitHub Actions cron every 6h fetches the secret ICS, commits `site/events.json` only when rides change, and the change redeploys Pages — so freshness is ≤6h plus a deploy per change. Evaluate (a) a client-side fetch of a public Partiful endpoint (profile page / embedded API, CORS permitting — never the secret ICS URL) so the page can be fresher than 6h with no redeploy, (b) a serverless proxy (Cloudflare Worker / Deno Deploy / Vercel function) that holds the secret server-side and emits public JSON the static site fetches, (c) keeping the cron. Write the comparison + chosen path in `ralph/ralph.log` and a one-line decision in CLAUDE.md; implementation, if a winner emerges, is a follow-up bullet. (Done: **decision = keep the cron (c).** Researched live: there is NO public unauthenticated Partiful events-list API — the profile page `/u/<id>` SSR-embeds only org metadata, the events list loads via a Firebase HTTPS callable `getMyUpcomingEventsForHomePage` at `api.partiful.com` that returns 401 without a Firebase token, and the site's fallback profile URL is the only public index. Per-event pages `/e/<id>` ARE public and rich — full event in `__NEXT_DATA__` plus a public per-event ICS (`calendarFile`, a GCS URL returning `text/calendar` with `access-control-allow-origin: https://ecao310.github.io`, verified) — but enumerating IDs still needs the secret feed, so (a) can't replace it; (b) a serverless proxy would require porting the tested Python parsing for marginal freshness. Full comparison in ralph.log; one-line decision added to CLAUDE.md's Deployment section. Follow-up bullet added below: enrich `events.json` from the public per-event pages.)
- [x] Enrich `site/events.json` from Partiful's public per-event pages (follow-up to the fetch-backend decision): during the sync, fetch each event's public page `/e/<id>` (or its `calendarFile` ICS) and merge the richer data it exposes — e.g. `image` (every ride currently has `image: null` even though the event page has one), full location info. The per-event GCS ICS is CORS-enabled for `https://ecao310.github.io` (verified) and the page is unauthenticated, so this needs no new secret — but event IDs still come from the secret feed, so it stays a sync-time enrichment, not a client-side feed. Verify: sync on fixture produces a ride with `image` set; node shim + pytest stay green. (Done: `fetch_rides.py` now backfills each ride's `image` from its public Partiful event page during **live-feed** syncs — `enrich_rides()` fetches `https://partiful.com/e/<id>` (the `rsvp_url`, or `derive_partiful_url(uid)`), parses `__NEXT_DATA__.props.pageProps.event.image` (a URL string or `{url, blurHash}`) with a raw Firebase-Storage-URL regex fallback, and merges it in. Fail-soft: a fetch/parse miss leaves `image: null` and never breaks the sync; the `ride_images.json` sidecar wins over enrichment; `--ics-file` runs stay fully offline (only live-feed runs fetch event pages). Scope: `image` only — the feed's single `LOCATION` already carries the public address and the event page's extra location fields (maps URLs) aren't rendered. New fixture `tests/fixtures/event-page.html`; pytest 69 passing (10 new: extraction happy paths + string image + regex fallback + blank page, enrich sidecar-wins/fail-soft/no-page-skip, and main() wiring proving `--ics-file` stays offline while a live run calls `enrich_rides`); node --check clean; HTML well-formed.)
- [x] Mobile-first audit of the JS-rendered UI at 380px: touch targets (calendar chips, modal close, action buttons) ≥44px, the ride-detail modal fits within 88vh and scrolls, ride titles wrap in both calendar renderers (no horizontal scroll, no truncation), tap-vs-hover affordances are correct. Fix whatever the audit finds. Verify: node shim cases still pass, HTML well-formed. (Done: touch targets are now ≥44px tall — `.ride-actions .btn` gets `min-height: 44px` + inline-flex centering, the fallback grid's `.cal-day .ride-chip` gets `min-height: 44px` + flex-center + 8px vertical padding (it was ~15px tall), `.modal-close` is now a 44×44 button (was 32×32), and the FullCalendar renderer's tap targets are bumped the same way: `.fc .fc-daygrid-event` `min-height: 44px` + flex-center, the `+N more` link, and the prev/next toolbar `.fc .fc-button`. The ride-detail modal was restructured so it genuinely fits 88vh and scrolls: `.modal-dialog` is now a flex column (was `overflow-y: auto` on the whole dialog), with `#ride-modal-content` as the scrollport (`min-height: 0; overflow-y: auto`) — so the 44px close button stays pinned at the top instead of scrolling out of view (or overlapping the title, as a 44px absolute button would). Ride titles already wrapped in both renderers (`overflow-wrap: anywhere` on `.ride-chip` and `.fc .fc-event-title`) — confirmed, no horizontal scroll, no truncation. Tap-vs-hover: added `:active` press feedback on `.btn`/`.btn-ghost`/`.ride-chip`/`.modal-close`/`.links a` (via `filter: brightness()` — no new palette hex) and on the nav tabs (stronger rgba bg). Verified: node DOM-shim 56/56, pytest 69 pass, all five HTML pages well-formed, and a CSS-assertion check confirms every touch-target/88vh/wrap rule is present (15/15). JS untouched.)
- [ ] make it so top navigation bar doesn't scroll with page. just leave it at top.
- [ ] move background image to 2nd section. create setting to increase opacity of background to improve readability.
- [ ] upcoming ride calendar looks completely broken on web.

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
