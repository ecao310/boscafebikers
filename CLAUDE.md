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
| `tests/fixtures/sample.ics` | Offline fixture (2 future, 1 past, 1 cancelled). |
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

## Status

Iteration 1 done: repo scaffolding (`.gitignore`, `PLAN.md`, `CLAUDE.md`,
`requirements.txt`). Nothing else exists yet — next task is the ICS fixture.
