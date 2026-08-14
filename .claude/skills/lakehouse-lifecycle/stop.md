# Stop runbook

Goal: bring everything down cleanly, and know exactly what survives.

## Default — quick stop (preserves what is on a mounted volume)

```bash
./lakehouse stop all            # Spark + Kafka
./lakehouse stop unity-catalog
./lakehouse stop airflow
./lakehouse stop mlflow
```

This runs `docker compose down` for each compose file. Containers are removed; **named
volumes are preserved**, so MLflow runs and Airflow DAG history (which live on mounted
volumes) survive a restart.

**Caveat — Unity Catalog does NOT survive today.** The `uc-data` volume is declared but
**not mounted** (see `docker-compose-unity-catalog.yml`), so UC keeps its H2 catalog in the
container's writable layer. Plain `down` removes the container and therefore **loses all UC
catalog metadata** (catalogs, schemas, table registrations). If you need UC state to persist
across a stop, take a backup first (below). (Mounting `uc-data` is planned for a later PR.)

To restart later, follow [start.md](start.md) from Step 3.

## Start fresh — use `./lakehouse reset`, not `down -v`

When the user asks to "reset", "clean up", or "start fresh", use the reset command — it
confirms, supports `--dry-run`, and **actually resets the databases and object store**, which
`down -v` cannot do (host PostgreSQL and SeaweedFS are not reset by removing Compose volumes).

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
