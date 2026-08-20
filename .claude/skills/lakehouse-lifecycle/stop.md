# Stop runbook

Goal: bring everything down cleanly, and know exactly what survives.

## Default — quick stop (preserves what is on a mounted volume)

```bash
./lakehouse stop all            # Spark + Kafka
./lakehouse stop unity-catalog
./lakehouse stop airflow
./lakehouse stop mlflow
```

This runs `docker compose down` for each compose file. Containers are removed but
**all persistent state survives a restart**, because it lives in named volumes and
the Composed `postgres` service (PR #13):
- databases (UC / MLflow / Airflow / `iceberg_catalog`) → `postgres-data`;
- object data (every Delta table, MLflow artifacts) → `seaweedfs-data`;
- UC's embedded H2 catalog → `uc-data` (now **mounted**, see
  `docker-compose-unity-catalog.yml` — UC metadata persists across a plain stop);
- MLflow local state → `mlflow-data`; Spark event logs → `spark-data`.

Plain `down` (no `-v`) removes only containers and networks; none of the above is lost.

To restart later, follow [start.md](start.md) from Step 3.

## Start fresh — use `./lakehouse reset`, not `down -v`

When the user asks to "reset", "clean up", or "start fresh", use the reset command — it
confirms, supports `--dry-run`, and resets the databases + object store **surgically**.
**Do NOT use `docker compose down -v`.** Since storage is Composed (PR #13), `-v` now
**wipes `postgres-data`, `seaweedfs-data`, and `uc-data`** — i.e. every database, all
object data, and the UC catalog — in one unconfirmed, unrecoverable step. `reset` is the
safe, granular alternative (and it can preserve MLflow, dry-run, and back up first).

```bash
./lakehouse reset --all --dry-run     # preview every target, destroys nothing
./lakehouse reset --all               # confirm interactively (or --yes)
./lakehouse reset --data              # object store + dangling catalog/tracking rows
./lakehouse reset --metadata          # catalog/tracking databases (UC + airflow + iceberg + mlflow)
./lakehouse reset --metadata --keep-mlflow   # ... but preserve MLflow
```

Back up first if the state matters (see [demo.md](demo.md) for the backup/restore flow):

```bash
./lakehouse backup                    # pg_dump every DB + S3 sync + volumes + UC H2
./lakehouse restore --from <path>     # fail-stop, recoverable
```

After a reset, run `./lakehouse doctor` to confirm no orphaned data or catalog
inconsistencies remain.

## Why raw `docker compose down -v` is the wrong tool here

`-v` removes only **Compose-managed named volumes**. On this stack that means it:

- does **not** touch **host PostgreSQL** (port 5432) — UC/MLflow/Airflow *metadata* rows
  persist, so the next `start` inherits stale catalog state;
- does **not** touch **SeaweedFS** object bytes — SeaweedFS keeps objects in its own
  filer/volume store, not in PostgreSQL and not in a Compose volume on a stock install, so
  every Delta/Iceberg file under `s3://lakehouse/warehouse/` survives;
- **does** delete the MLflow/Airflow volumes it does manage.

Net effect: `down -v` produces a **half-wiped, internally inconsistent** environment —
exactly what `./lakehouse reset` exists to prevent. Never reach for `down -v` to "start
fresh".

## Verifying nothing is left running

```bash
docker ps --filter "name=spark-\|name=kafka\|name=zookeeper\|name=unity-catalog\|name=airflow\|name=mlflow"
```

Should return an empty list.

## Restart vs stop+start

For config changes that need a fresh container:

```bash
./lakehouse restart spark   # equivalent to stop + 2s sleep + start
```

For Java heap or JAR changes, prefer full stop + start (`restart` reuses the same compose
project state).
