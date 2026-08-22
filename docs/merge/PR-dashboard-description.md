# Dashboard (Phase 3) — read-only web viewer

Ports the containerized-lakehouse-platform **frontend** into `dashboard/` as an
opt-in, read-only web viewer over Unity Catalog, MLflow, the SeaweedFS object
store, service health, and (when running) Delta Sharing.

**Base:** cut from the #13 trunk `feat/net-bridge-conversion` @ `952b5d6` (a fan
sibling — see `docs/merge/PR-fan-strategy.md`; not based on #14/#15).

## What this is

A Next.js 15 / React 19 app (TS 5.7, Tailwind 3.4, `output: standalone`,
Vitest 3.0). It is a **viewer**, not a control plane — it reads UC / MLflow / S3
and never writes to the warehouse in its default posture (D8 scope honesty). It
is **opt-in**: `./lakehouse start all` does not start it.

```bash
./lakehouse start dashboard      # first run builds the image; serves 127.0.0.1:3000
./lakehouse stop dashboard
```

## Commit shape (mechanical → substantive)

1. **Import CP frontend verbatim** (`Co-authored-by` Charlotte Blankenberg) — bulk, no behavior change.
2. **Repoint to SeaweedFS + bridge service names** — endpoints, bucket, env, client links, vitest paths.
3. **Compose + opt-in CLI arm + status/ports/help + overlay** — how it plugs into the platform.
4. **Close the `/api/pipelines` path-traversal (T-3.7)** + invert CP's F-08 test.
5. **Feature-flag off the code-execution / write routes + pages (D6 / T-3.8)** — the demo toggle.
6. **Skill, PROVENANCE, PR description, Python config tests.**

Read the risky diffs (4, 5) without wading through the ~11k-line bulk import.

## Security posture

- **Read-only by default.** The Pipelines + Notebooks pages and the four
  code-execution / write routes (`POST /api/jupyter-exec`, `POST /api/pipelines/run`,
  `POST /api/pipelines`, `DELETE /api/pipelines/history`) are **disabled** behind
  `DASHBOARD_ALLOW_CODE_EXECUTION` (default `false`). Disabled routes return `403`;
  the nav hides the pages. Enable only on a trusted, non-exposed network — it is a
  deliberate, warning-laden demo toggle (loud CLI warning + persistent in-UI banner).
- **Path traversal (T-3.7):** `POST /api/pipelines` containment now uses a
  trailing-separator boundary, rejecting sibling-dir escapes like
  `/app/pipelines-evil`. Enforced whether or not the flag is on. F-08 inverts CP's
  original "traversal allowed" assertion.
- **Least-privilege exposure:** binds `127.0.0.1:3000` only.
- **No internal specifics:** the sharing page's external-access section is
  tool-agnostic (no cloudflared / tunnel names; `./lakehouse share *`).

## Blast radius

Almost entirely new files (`dashboard/`, `docker-compose-dashboard.yml`,
`.claude/skills/dashboard/`, `tests/test_dashboard_config.py`, the test overlay).
Shared touch-points are additive only: the `lakehouse` CLI (opt-in `dashboard`
arms + `status --json`), `scripts/lib/overlay.sh` (`OVERLAY_BASE_SERVICES`), and a
Phase-3 section appended to `docs/merge/PROVENANCE.md`. No behavior change to any
existing service (Option-A §4 "purely additive").

## Verification

- `tests/test_dashboard_config.py` (5 tests, `pytest -m dashboard`): port
  contract, env-var contract (U-25), code-execution-off-by-default (U-26 / D6),
  neutrality (U-38 / D8), core-compose isolation. Green.
- Vitest (`dashboard/tests/**`) including F-08 (traversal → 400) and F-10
  (flag gating).
- `bash -n` + `shellcheck` clean on the CLI; base and run-scoped overlay both
  render via `docker compose config`.
- Full E2E (docker build via npm proxy + `./lakehouse start dashboard` on the live
  stack + browser walk-through + flag both ways) — see the PR checklist.

This pull request and its description were written by Isaac.
