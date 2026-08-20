# PR #13 — Network + storage foundation (Phases 1 + 2)

Converts the local stack from host-networking + host-installed storage to
**bridge networking + storage-in-Compose**, upgrades the version-pinned
components that the merge depends on, and adds the SeaweedFS S3 conformance
suite. This is the only tranche of the CP merge that changes existing local
workflows; it is independently defensible via open-lakehouse's own `SECURITY.md`
and lands before the additive feature PRs sit on top.

Base: `main` + PR #11 (demos/mlflow uv.lock hygiene) + PR #12 (lifecycle/reset
safety). See `docs/merge/PROVENANCE.md` for exact SHAs, `docs/merge/DECISIONS.md`
for the D1–D8 pointer.

## What's in it

**Phase 1 — bridge + storage + versions**
- **Bridge networking (D1).** Every service moves off `network_mode: host` onto
  the shared `lakehouse-network`; peers are addressed by service name; host-facing
  services publish ports. Spark ports the `spark-ecs` advertise-address pattern
  (master advertises its own bridge IP, never `0.0.0.0`). `sc://localhost:15002`
  is preserved (I-03).
- **Storage in Compose.** PostgreSQL 16 and SeaweedFS become Compose services
  with named volumes (`docker-compose-storage.yml`); `./lakehouse start storage`
  bootstraps the bucket, warehouse prefixes, and `iceberg_catalog`.
- **UC → official `unitycatalog/unitycatalog:v0.5.0` (D2).** Replaces the
  personal pre-publish staging image (supply-chain hygiene). Non-breaking (I-44);
  unlocks **catalog-managed Delta** (I-45).
- **Delta → 4.3.1 + the UC 0.5.x Spark connector family** (connector 0.4.1 +
  client 0.5.1 + hadoop 0.5.1) — the exact set that makes catalog-managed Delta
  work (I-02/I-45). 4.3.0 alone NPEs through the connector.
- **MLflow → 3.14** (I-09) + healthcheck fix (the image has no `curl`).
- **Jupyter token auth (D5)** + spark-pipelines deps in the image.
- **sdp-medallion** made coherent and runnable end-to-end on catalog-managed
  Delta (self-contained `seed.py` + one-command `run.sh`).

**Phase 2 — SeaweedFS hardening & S3 conformance**
- S3 conformance matrix, presigned host-rewrite (modes B + C — SeaweedFS's Delta
  Sharing edge over MinIO), and a warehouse-layout lint, all wired into
  `./lakehouse test` (`scripts/connectivity/test-s3-*.py`).
- Removed the stale `fs.s3a.multiobjectdelete.enable false` (bulk delete works).
- New `seaweedfs-ops` skill.

## Blast radius

**Breaks / changes behavior**
- The `localhost:9092` / `localhost:8081` **in-container idiom** — in-network
  clients now use service names (`kafka:9092`, `unity-catalog:8080`, …); the host
  still uses `localhost:<published-port>`. Any local scratch work assuming host
  networking needs updating.
- **Host-installed SeaweedFS / PostgreSQL → Compose services + named volumes.**
  Needs the migration note (`docs/merge/MIGRATION.md`, E-06). Host setups often
  kept data in disposable locations (`/tmp/seaweedfs`), so most users start clean.
- **UC image `newfrontdocker/…:v0.4.1` → official `…:v0.5.0` (D2).** The
  `unity-catalog-oss` / `sdp` skills are valid only after the T-1.18 review — do
  **not** claim "UC unchanged." UC 0.5.0's `/tables` API is also stricter (a
  column's `type_json` must be a real descriptor, not `{}`).
- **Jupyter's empty token is removed; token auth required (D5).**
- **`docker compose down -v` can now destroy object data *and* metadata (R-15)** —
  it wipes `postgres-data`, `seaweedfs-data`, `uc-data`. Mitigated by PR #12's
  `./lakehouse reset` (and `stop` without `-v`), after the lifecycle re-ground.

**Explicitly unaffected**
- `sc://localhost:15002` (I-03 / Golden Rule #3).
- AWS / Terraform `awsvpc` — independent of local Compose (E-05).
- The Iceberg **write** story — still upstream-blocked in every UC OSS build;
  I-47 pins it. **No "format neutrality restored" claim.** Reads stay
  engine-neutral via the Iceberg REST endpoint.
- No conflicting unmerged branches beyond #11 / #12.

## Known issues / follow-ups

- **SeaweedFS pinned at 3.80, not 4.x** (deliberate — `docs/merge/` +
  `seaweedfs-ops`). SeaweedFS 4.x enforces `X-Amz-Security-Token` validation and
  rejects UC OSS credential vending's *mandatory* placeholder session token
  (403), breaking the primary UC write path (measured 4.00/4.30/4.40). 4.x fixes
  conditional PUT (`If-None-Match: *`, row **S-04**), so on 3.80 that row is a
  documented **KNOWN-LIMITATION** — it matters only for concurrent multi-writer
  Delta commits, which the local single-writer stack never does. Revisit when UC
  OSS stops requiring a vended token or SeaweedFS adds a static-cred-with-token
  path.
- **`reset` does not wipe Kafka topics / checkpoints** — the honest `--dry-run`
  says so. Follow-up (schedule as an immediate #14 or within #13).
- UC Spark connector `0.5.0` is not published (only `0.4.1`); catalog-managed
  Delta relies on connector 0.4.1 + client/hadoop 0.5.1. Track a 0.5.x connector.

## Verification

See the "before PR #13 leaves draft" gate report in the session log: 183 unit
tests + the S3 conformance (S-01…S-11), version/D2 gates (I-02/08/09/12/44/45/47),
neutrality guards (U-15/17/22/35/36/40, I-42), and the re-grounded lifecycle
regression (E-07 + I-28/29/30) on the Composed topology. `sc://localhost:15002`,
distributed Spark execution, and the sdp-medallion demo all verified on a fresh
teardown + rebuild.
