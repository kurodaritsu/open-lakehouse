---
name: unity-catalog-oss
description: Unity Catalog OSS 0.4.x — the only catalog in this stack. Load when configuring the UC server, creating catalogs/schemas/tables via REST, or wiring a non-Spark engine (DuckDB, Trino) against UC. Covers the REST API surface, credential vending, and the no-JDBC-catalog rule.
---

# Unity Catalog OSS

This stack uses **Unity Catalog OSS only**. There is no PostgreSQL JDBC catalog path. If you see `spark.sql.catalog.iceberg.type=jdbc` or `spark.sql.catalog.iceberg.jdbc.user` anywhere, that's a leftover bug from the upstream lakehouse-stack reference — remove it, don't replicate it.

UC OSS runs as a Java server. The compose definition is `docker-compose-unity-catalog.yml`. Backing store is embedded H2 on the `uc-data` volume. REST API is on `localhost:8081`.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `http://localhost:8081/api/2.1/unity-catalog/catalogs` | List/create catalogs |
| `http://localhost:8081/api/2.1/unity-catalog/schemas` | List/create schemas |
| `http://localhost:8081/api/2.1/unity-catalog/tables` | List/create/describe tables |
| `http://localhost:8081/api/2.1/unity-catalog/iceberg/v1/config` | Iceberg REST catalog (Spark uses this) |
| `http://localhost:8081/api/2.1/unity-catalog/iceberg/v1/namespaces` | Iceberg REST namespace ops |

UC 0.4.x speaks the **Iceberg REST Catalog spec** at the `/iceberg/v1/*` path. Any Iceberg client (Spark, PyIceberg, DuckDB via `iceberg` extension) can point at this URL.

## Spark config

Already wired in `config/spark/spark-defaults.conf.example`:

```
spark.sql.catalog.iceberg               org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.iceberg.catalog-impl  org.apache.iceberg.rest.RESTCatalog
spark.sql.catalog.iceberg.uri           http://localhost:8081/api/2.1/unity-catalog/iceberg
spark.sql.catalog.iceberg.warehouse     unity
spark.sql.catalog.iceberg.token         not_used
```

In Spark, `iceberg.bronze.orders` resolves through UC. Behind the scenes Spark calls `GET /iceberg/v1/namespaces/bronze/tables/orders/`.

## Creating things via REST

```bash
# Create the iceberg catalog (one-time)
curl -X POST http://localhost:8081/api/2.1/unity-catalog/catalogs \
  -H "Content-Type: application/json" \
  -d '{"name":"iceberg","comment":"Default Iceberg catalog"}'

# Create a schema
curl -X POST http://localhost:8081/api/2.1/unity-catalog/schemas \
  -H "Content-Type: application/json" \
  -d '{"name":"bronze","catalog_name":"iceberg"}'

# List tables
curl "http://localhost:8081/api/2.1/unity-catalog/tables?catalog_name=iceberg&schema_name=bronze" | jq .
```

Auth: 0.4.x ships with no auth by default for local. Don't add a bearer token until you've wired UC's auth provider — most demos run unauth.

## Backing store

UC OSS stores its catalog metadata in an embedded H2 file, `/home/unitycatalog/etc/db/h2db.mv.db` inside the container (the image's stock `hibernate.properties`; no PostgreSQL involved). Since the 0.6.0 bump it sits on the `uc-data` named volume, so container recreation keeps catalogs/schemas/table registrations. Before that it was ephemeral: every image swap wiped the catalog and tables had to be re-registered with `CREATE TABLE ... USING delta LOCATION 's3://...'`.

`./lakehouse backup` / `restore` copy the H2 file (`uc_h2_backup`). Hibernate `hbm2ddl.auto=update` handles schema changes at startup; you don't manage them.

## Credential vending

UC OSS can vend S3 credentials to clients so Spark doesn't need hardcoded `S3_ACCESS_KEY`/`S3_SECRET_KEY`. Configure in `server.properties`:

```
s3.region=us-east-1
s3.endpoint=http://seaweedfs:8333
s3.access-key=<your-seaweedfs-key>
s3.secret-key=<your-seaweedfs-secret>
s3.path-style-access=true
```

Clients then ask UC for temporary creds when reading a table — no creds in client config. For demo purposes the current spark-defaults.conf still ships static S3 keys; cleaning this up is a follow-on.

## Other engines

```python
# DuckDB
import duckdb
con = duckdb.connect()
con.sql("INSTALL iceberg; LOAD iceberg;")
con.sql("ATTACH 'http://localhost:8081/api/2.1/unity-catalog/iceberg' AS uc (TYPE iceberg);")
con.sql("SELECT * FROM uc.bronze.orders LIMIT 10;")
```

Trino, Dremio: same pattern — register UC's `/iceberg/v1/` URL as an Iceberg REST catalog.

## Limitations of UC OSS 0.4.x (don't promise users these)

- Auth providers (OAuth, SAML) are partial.
- Lineage events (system tables) are minimal compared to managed Databricks UC.
- Cross-catalog references work; cross-deployment federation does not.

## Write-side reality (verified 2026-05-19, v0.4.0 and v0.4.1)

UC OSS's write story is partial and format-specific. What was actually tested:

- **Iceberg is read-only.** UC's Iceberg REST adapter (`/iceberg/v1/...`)
  advertises only `GET`/`HEAD` endpoints — no `POST` for namespace or table
  creation. Spark `CREATE TABLE` against the `iceberg` catalog fails with
  `UnsupportedOperationException: Server does not support endpoint`. UC's
  native `/tables` API rejects `ICEBERG` as a `data_source_format` entirely
  (accepts `DELTA`, `PARQUET`, `CSV`, `JSON`). **Treat the `iceberg` catalog
  as read-only** — fine for cross-engine reads of tables created elsewhere,
  not for writes.
- **Delta writes work** via the UC Spark connector (`io.unitycatalog.spark.UCSingleCatalog`),
  with sharp edges:
  - The connector asserts `location != null` and `provider != null` in
    `createTable`. The standard Spark SQL path populates `location`
    automatically; SDP and other non-analyzer paths don't — you must pass
    `location` + `provider` explicitly (in `table_properties` for SDP). See
    [[sdp]] → `unity-catalog.md`.
  - Credential vending (`generateTemporaryPathCredentials`) only accepts
    `s3` / `gs` / `abfs` URI schemes — **`s3a://` is rejected.** Write
    locations as `s3://`; Hadoop resolves via the `spark.hadoop.fs.s3.impl`
    → `S3AFileSystem` mapping.
  - No truncate support — re-creating an existing table errors. Drop first.
- **Bucket config gotcha:** UC's `ServerProperties.getS3Configurations()` loop
  breaks (silently skipping the bucket) if *either* the IAM-role group OR the
  static-creds group has any null field. For SeaweedFS / static-cred mode set
  a non-null `s3.sessionToken.0` (any placeholder) or the bucket won't load
  and credential vending fails with "S3 bucket configuration not found."

## Storage convention (since 2026-09-20)

Same three-tier model as Databricks managed storage (schema > catalog > server default):

- **Catalog-level `storage_root` is the tier we use**: `s3://lakehouse/managed/<catalog>`. Managed
  tables and managed volumes then land at
  `s3://lakehouse/managed/<catalog>/__unitystorage/catalogs/<catalog_id>/{tables,volumes}/<id>`.
  `unity` and `example` are set up this way.
- **Server default** `storage-root.tables=s3://lakehouse/managed` (`server.properties`) is the
  safety net for catalogs created without a `storage_root` (UC UI has no field for it): managed
  tables go to `s3://lakehouse/managed/__unitystorage/tables/<table_id>`; managed volumes fail
  there (`FAILED_PRECONDITION`, no `storage-root.volumes` exists). So: create catalogs over REST
  with `storage_root`, not from the UI.
- Schemas: create them anywhere (UI, Spark `CREATE SCHEMA`, REST); they inherit the catalog root.
  A schema-level `storage_root` is possible over REST but not part of the convention.
- **External tables**: `s3://lakehouse/external/<catalog>/<schema>/<table>`, passed as `LOCATION` /
  `.option("path", ...)`. Never register a table at a parent prefix; UC rejects anything nested
  under an existing table path afterwards.
- `storage_root` is set at create time only (`UpdateCatalog`/`UpdateSchema` don't carry it), and
  the Spark connector ignores `CREATE SCHEMA ... LOCATION`.
- Managed tables use the catalogManaged protocol (reader v3 / writer v7, column mapping, DVs, row
  tracking). Other engines must go through the UC Delta API to find the path and need to support
  those features. `DROP TABLE` on a managed table removes only the catalog entry; UC OSS's S3
  delete is a no-op, so the files under `managed/` stay until removed by hand.
- History: `unity.common.us_states_metadata` and `example.mnist.images` were moved under
  `external/`; both catalogs were recreated to attach the `storage_root`. All ids changed.

Create a catalog the convention way:

```bash
curl -X POST http://localhost:8081/api/2.1/unity-catalog/catalogs -H 'Content-Type: application/json' \
  -d '{"name":"<catalog>","storage_root":"s3://lakehouse/managed/<catalog>"}'
```

## 0.6.0 notes (bumped 2026-09-20 from 0.4.1; connector 0.3.0 -> 0.6.0, Delta 4.2.0 -> 4.4.0)

- Connector artifact is per Spark version since 0.5.0: `unitycatalog-spark_4.1_2.13`. Runtime deps
  `unitycatalog-client`, `unitycatalog-hadoop`, `jackson-databind-nullable`. Delta 4.3+ brings
  `delta-kernel-api/defaults/unitycatalog` + `jackson-datatype-jdk8`. All in `download-jars.sh`.
- UC `columns` are populated only with `spark.databricks.delta.catalog.update.enabled=true`
  (set in `spark-defaults.conf`). Delta's `cleanupTableDefinition` otherwise hands the catalog an
  empty schema, which is why the UC UI showed "No data" for every table before. `CREATE TABLE ...
  USING delta LOCATION` without a column list also registers `columns: []`; spell the columns out.
- Credential vending vs SeaweedFS: connector 0.5+ signs s3a requests with the vended session token
  (`AwsSessionCredentials`); SeaweedFS answers `InvalidAccessKeyId` to any request carrying
  `X-Amz-Security-Token`. `spark.sql.catalog.unity.credScopedFs.enabled=false` and
  `spark.sql.catalog.unity.renewCredential.enabled=false` keep s3a on
  `SimpleAWSCredentialsProvider` with the static keys. Untested consequence: managed tables via the
  Delta API may need the scoped FS.
- `df.write.mode("overwrite").saveAsTable("unity.x.y")` is now `REPLACE TABLE`, which the connector
  rejects for external tables ("only catalog-managed Delta tables can be replaced"). Pattern that
  works: create once with `.option("path", "s3://...")`, then `df.write.mode("overwrite")
  .insertInto(table)`. CTAS into a non-empty location also fails
  (`DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`), so a DROP + recreate needs the prefix wiped first.
- UC Delta API (`/api/2.1/unity-catalog/delta/v1/...`) for catalog-managed Delta tables;
  `server.managed-table.enabled` defaults to true. Managed tables need a `storage_root` on the schema
  (`CreateSchema.storage_root`; catalog `storage_root` is not patchable). External tables with an
  explicit `s3://` location are unchanged.
- `s3.endpoint.0` in `server.properties` is ignored by the server (never was read). The server only
  vends static creds; Spark resolves the endpoint from `fs.s3a.endpoint`. Consequence: the server-side
  Iceberg REST read path (`S3FileIO`) has no SeaweedFS endpoint override and likely never worked here.
- Iceberg REST is still read-only.
- Terraform `spark-ecs` Dockerfile ARGs still pin the old versions; not updated.

## When something's wrong

`./lakehouse logs unity-catalog | tail -100` shows the Java server's stdout. Most failures are:

1. SeaweedFS not up yet → credential-vended table operations fail with S3 errors, catalog ops still succeed.
2. Broken H2 after a UC version bump → `podman volume rm open-lakehouse_uc-data` (loses registrations; Delta data in SeaweedFS survives) and re-register tables with `CREATE TABLE ... LOCATION`.
