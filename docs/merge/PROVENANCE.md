# docs/merge/PROVENANCE.md — PR #13 base provenance

Records the exact base state PR #13 (network + storage foundation, plan Phases 1 + 2) is built on,
per Checkpoint 0 / absorbed Phase 0 (T-0.1, T-0.2). Created 2026-08-19.

## Base SHAs

| Ref | SHA | Notes |
|---|---|---|
| `main` | `4090bc3e10e8361352a33c0c0cd58f78b60e6e22` | tip is "Merge pull request #10"; does **not** yet contain #11 or #12 |
| PR #11 — `fix/mlflow-uv-lock-public-pypi` | `b85056277e84dd72a2941aeb6e17d276fcb97e71` | 1 commit ahead of `main`; touches only `demos/mlflow/uv.lock` |
| PR #12 — `feat/lifecycle-reset-safety` | `00d70c62e8258402f2c0fea88921beef2c527cb1` | 29 commits ahead of `main`, 0 behind; the lifecycle/data-safety work |
| **integration `feat/merge-cp-integration`** | `1105717cf3260651c23751f49468232410764c4a` | `main` → fast-forward to #12 → merge #11 (clean, `ort`, no conflicts) |
| **`feat/net-bridge-conversion`** | `1105717cf3260651c23751f49468232410764c4a` | branched off integration; Phase 1 work lands here |

## Branch topology (addendum §1)

```
origin/main (4090bc3, at PR #10)
  ├─ fix/mlflow-uv-lock-public-pypi (b850562)      → PR #11 (open)
  └─ feat/lifecycle-reset-safety (00d70c6)          → PR #12 (open)
        └─ feat/merge-cp-integration (1105717)  = main + #12 (ff) + merge(#11)
              └─ feat/net-bridge-conversion (1105717)  ← PR #13 Phase 1 lands here
                    (later: feat/merge-storage-seaweedfs for Phase 2)
```

**Base = `main` + PR #11 + PR #12** (addendum §1). Because #12 is 0 commits behind `main`, `main`
is an ancestor of #12, so `main + #12` fast-forwarded to #12's tip; #11's single `uv.lock` commit
then merged cleanly (different file, no conflict).

## Remote / PR state — verified via `gh` (read-only)

`gh pr list` confirms on `github.com/open-lakehouse/open-lakehouse`:
- **#12** (Phase 1.5 — Lifecycle & data safety) — **OPEN**
- **#11** (fix(mlflow): repoint demo uv.lock) — **OPEN**
- #10 and earlier — merged.
- No PR #13 exists yet (this work).

This is the addendum §1 "still open" case, so the integration branch was cut from a local merge of
`main` + #11 + #12. If #11/#12 gain review fixes after this tip, rebase/merge them into
`feat/merge-cp-integration` **before** the bridge conversion (Checkpoint 2) — do not build on a
stale lifecycle CLI.

## Attribution

CP-derived material ported in later checkpoints (the `terraform/spark-ecs` advertise-address
pattern for T-1.3, `make cache-deps` antecedents, the MinIO→SeaweedFS substitution) must carry
`Co-authored-by` trailers and be noted here as it lands.

---

## Phase 3 — Dashboard (`feat/merge-dashboard`, sibling PR)

Ported the containerized-lakehouse-platform **frontend** (Next.js 15 / React 19 / TS 5.7 /
Tailwind 3.4, `output: standalone`, Vitest 3.0) into `dashboard/`, with its Vitest suite from
CP `tests/frontend/` → `dashboard/tests/`. The verbatim import is one commit (CP-attributed
`Co-authored-by` trailers: Charlotte Blankenberg); the repoint, the T-3.7 fix, and the D6
feature flag are separate commits so the risky diff reads on its own.

Source → destination:

| CP source | open-lakehouse | Reworking |
|---|---|---|
| `frontend/` | `dashboard/` | verbatim import, then repoint |
| `frontend/src/app/api/minio/[...path]` | `dashboard/src/app/api/storage/[...path]` | renamed; `MINIO_URL`→`S3_ENDPOINT` (`seaweedfs:8333`) |
| (new) | `dashboard/src/app/api/health/storage` | HEAD-bucket probe (SeaweedFS has no `/minio/health/live`) |
| (new) | `dashboard/src/lib/features.ts`, `src/app/api/features`, `src/components/code-exec-guard.tsx` | D6 feature-flag plumbing |
| `tests/frontend/**` | `dashboard/tests/**` | verbatim; vitest `include` repointed to `./tests/**` |

Reworkings of note:
- **Repoint (T-3.2/3.3/3.4):** MinIO→SeaweedFS (`seaweedfs:8333`), `mlflow-server:5000`,
  `unity-catalog:8080`; bucket `lakehouse-data`→`${S3_BUCKET:-lakehouse}`; client "open UI"
  links → host ports (UC 8081, MLflow 5000, Spark UI 8082, Jupyter 8889, Sharing 8443);
  MinIO-console links dropped (SeaweedFS has no console).
- **T-3.7 (security):** `POST /api/pipelines` containment gained a trailing-separator
  boundary (`isInsidePipelinesDir`), closing the sibling-dir escape a bare
  `startsWith(base)` admitted. CP's own test that asserted `../../../etc/passwd` was allowed
  is inverted (F-08).
- **D6 / T-3.8:** the code-execution / write routes and the Pipelines + Notebooks pages ship
  **disabled** behind `DASHBOARD_ALLOW_CODE_EXECUTION` (default false), a documented demo
  toggle with loud warnings when enabled.
- **Neutrality (D8):** separate `docker-compose-dashboard.yml`, opt-in CLI arm, never started
  by `start all`. The sharing page's "external access" section was genericized (no
  cloudflared / tunnel specifics; `make share*` → `./lakehouse share *`).

## Phase 4 — Delta Sharing (`feat/merge-sharing`)

**Branch base:** `feat/merge-sharing` is cut from the PR #13 trunk
`feat/net-bridge-conversion` @ `f72ff2f` (per `docs/merge/PR-fan-strategy.md`).

Ported from the containerized-lakehouse platform `docker/delta-sharing/` (the OpenSharing
reference server + `url-rewriter-proxy.py` + configs) and `tests/docker/test_url_rewriter.py`,
rewritten for the open-lakehouse stack. The verbatim import commit carries `Co-authored-by`
trailers to the CP authors; the SeaweedFS adaptation is Isaac's.

| CP source | Ported to | Key reworking |
|---|---|---|
| `docker/delta-sharing/*` | `docker/delta-sharing/*` | Verbatim import (normalized to repo style: black/ruff), then repointed. |
| MinIO endpoint `minio:9000` | `seaweedfs:8333` | `server.yaml` hadoopConf + `core-site.xml` (fs.s3a/fs.s3/fs.s3n). |
| CP env/placeholders `MINIO_ENDPOINT`, `MINIO_PUBLIC_SCHEME`, `__MINIO_*__` | `S3_PUBLIC_ENDPOINT`, `S3_PUBLIC_SCHEME`, `__S3_*__` | Matches the `seaweedfs-ops` skill; no MinIO exists here. |
| CP shared tables (notebook-produced retail-gold + streaming/crypto_rates on `lakehouse-data`) | `sales_by_region`, `daily_revenue` on `s3a://lakehouse/warehouse/sharing/` | Replaced with a **self-contained seed** (`scripts/sharing/seed_shared_tables.py`) writing path-based Delta at fixed prefixes — verifiable in isolation, no notebook dependency. |
| CP public-endpoint-first sharing (`scripts/start-sharing.sh`) | **local-first** (`S3_PUBLIC_ENDPOINT=localhost:8333`) | The `./lakehouse share` CLI serves locally out of the box; a public HTTPS endpoint is an override, and how it's exposed is out of scope for this repo. |
| CP `docker-compose.yml` delta-sharing service | `docker-compose-sharing.yml` | Bridge network; loopback-bound 8443 (D6); no cross-file `depends_on`. |

The upstream **T-4.8** presigned-URL signer bug (`delta-io/delta-sharing#753`, fix PR `#965`
stalled) — the reason the re-signing proxy exists — is documented in the `delta-sharing` skill.

**Not in this PR (deferred follow-up):** folding the CP Delta Sharing *notebooks* (T-5.4) into
`demos/delta-sharing/` — that lands after both this PR and the Demos PR merge.

## Phase 5 — Demos (`feat/merge-demos-docs`)

**Branch base:** `feat/merge-demos-docs` is cut from the PR #13 trunk
`feat/net-bridge-conversion` @ `4e25c6b` (per the fan strategy in `docs/merge/PR-fan-strategy.md`).

Ported from the containerized-lakehouse platform notebooks
(`~/workspace/containerized lakehouse platform/notebooks/`) and rewritten for the open-lakehouse
stack: Spark Connect transport (`sc://localhost:15002`), SeaweedFS S3, the `lakehouse` bucket, and
the pre-wired UC / Delta catalogs. Each demo follows the `demos/_template/` contract
(script + README + `teardown.sh`) and runs top-to-bottom on the local Connect stack; its teardown
clears its own artifacts to zero residue. The four Delta-backed demos are self-cleaning on re-run
(they clear their S3 prefix and write Delta with `overwrite` at the start, via the shared
`demos/_lib/` helpers). `mlflow-tracking` does not write a Delta table — it re-runs by restoring a
soft-deleted experiment and registering a new model version, and its artifacts are removed by its
teardown (not cleared at start).

| Source notebook | Ported to | Key reworking vs the CP notebook |
|---|---|---|
| `01_Quick_Start` | `demos/quick-start/` | Connect; dropped the raw-parquet storage probe (S3A rename committer fails on SeaweedFS) — the governed Delta write proves storage instead. |
| `02_Delta_Lake_Deep_Dive` | `demos/delta-deep-dive/` | Connect; Delta DML via SQL (no DeltaTable client); path-based `delta.\`s3a://…\``. |
| `03_Unity_Catalog` | `demos/unity-catalog/` | Connect; external Delta registered by writing Delta with `overwrite` then `CREATE TABLE … USING delta LOCATION 's3://…'` (not CTAS; not `INSERT`; `s3://` not `s3a://`) — deterministic re-runs even over a lingering SeaweedFS dir; catalog list via UC REST (SHOW CATALOGS is lazy over Connect). |
| `04_Analytics` | `demos/analytics/` | Connect; self-seeds a governed `unity.analytics_demo.sales`; matplotlib charts saved to PNG (headless `Agg`) instead of inline; matplotlib import guarded. |
| `05_MLflow_Tracking` | `demos/mlflow-tracking/` | Data sourced/prepped in Spark Connect, trained with **scikit-learn** (not Spark ML): `mlflow.spark.log_model` saves via the S3A rename committer, which SeaweedFS rejects; `mlflow.sklearn.log_model` uploads via boto3 and works. Tracking + Model Registry + `champion` alias preserved. NOT a fold into `demos/mlflow/` (that is a separate conversational-analytics demo). |

Ported demo code carries `Co-authored-by` trailers to the CP authors on commit.

**Deferred (not in this PR):** `demos/unity-catalog-multi-engine/` (T-5.6) stays a placeholder —
UC OSS 0.5.0's Iceberg REST endpoint cannot serve any table this stack can write (measured; see the
session notes / memory), so a real multi-engine-via-REST demo is a separate follow-up. The
`06/09/10` Delta Sharing notebooks (T-5.4) fold in after the Sharing PR lands.
