You are one iteration of a loop. Each run: pick exactly ONE unchecked task from the
Backlog below (topmost first), complete it fully, verify it, mark it `[x]` in
`ralph/PLAN.md`, commit, push, and exit. Do not attempt more
than one task per run.

## Project spec

Boston Café Bikers ("exploring the city one café at a time") is already built:
a single-page static site in `site/` plus an ICS sync that regenerates
`site/events.json` every 6 hours. See CLAUDE.md for the full file map and
conventions — read it first, every iteration.

**This phase is deployment.** Goal: `site/` is live on GitHub Pages at a URL a
human can open on their phone, it stays fresh as the sync workflow updates
`site/events.json`, and the README describes what actually happens.

Repo facts you need:

- Remote is named `boscafebikers` (NOT `origin`):
  `git@github.com:ecao310/boscafebikers.git`. Local branch is `master`.
- `gh` CLI is installed and authenticated as `ecao310`.
- The site is in the `site/` subdirectory, not the repo root.

Two hard constraints that rule out the obvious approach:

1. GitHub Pages "Deploy from a branch" only offers **`/` (root)** or **`/docs`**
   as the folder. There is no `/site` option — the README currently claims there
   is, and it is wrong. So deployment must use the **GitHub Actions** Pages
   source (`actions/upload-pages-artifact` with `path: site` →
   `actions/deploy-pages`), which can publish any subdirectory.
2. Commits pushed by the sync workflow's `GITHUB_TOKEN` **do not trigger**
   `push`-triggered workflows. A Pages deploy workflow that only listens on
   `push` will therefore never redeploy after a ride-schedule update. Solve it
   deliberately (e.g. make the deploy workflow `workflow_call`-able and have
   `sync.yml` call it after a successful promote, or trigger on `workflow_run`)
   and write the reasoning into CLAUDE.md.

## Rules

- One task per iteration. Small, complete, verified.
- Verify before committing. Prefer real evidence over assumption: `gh run watch`
  / `gh run view --log-failed` for workflow runs, `curl -sS -o /dev/null -w '%{http_code}'`
  against the live URL for deploys. Never mark a task `[x]` on the strength of
  "the YAML looks right".
- Nothing in this phase may hit the live ICS feed. Tests and local runs use
  `tests/fixtures/sample.ics`. `pytest tests/ -q` must stay green (24 tests) —
  run it before any commit that touches Python or workflows.
- Never commit secrets. The real ICS URL only ever lives in the
  `PARTIFUL_ICS_URL` GitHub secret / env var, never in a file, a log, or a CLI
  argument.
- If you find a bug from a previous iteration, fixing it IS your task this
  iteration: fix it, note it under "Discovered work" in `ralph/PLAN.md`, exit.
- If a task is blocked, mark it `[blocked: reason]` in `ralph/PLAN.md` and pick the next
  task instead. Anything needing a human click in the GitHub web UI is blocked —
  but check first whether `gh api` can do it headlessly (it usually can, e.g.
  `gh api -X POST repos/:owner/:repo/pages`).
- Keep CLAUDE.md updated with anything the next iteration needs to know
  (decisions, gotchas, file map). You have no memory between runs — these files
  are your memory. Avoid adding unnecessary notes to CLAUDE.md.
- When every Backlog task is `[x]`, verify the whole system end-to-end once
  (trigger sync → promote → deploy → live URL serves the updated page), then
  print exactly `RALPH_DONE` and exit.
- Add notes to `ralph/ralph.log` (gitignored scratch — never commit it).
- Keep `ralph/PLAN.md` bullets at their original task wording. When completing a
  task, just flip `[ ]` to `[x]` — do NOT append `(Done: …)` write-ups to the
  bullet. Write the per-iteration write-up in `ralph/ralph.log` instead. Adding
  new backlog bullets when there is new work is still fine.
