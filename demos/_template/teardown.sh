#!/usr/bin/env bash
# Teardown script for <demo-name>.
# Removes every artifact this demo created. Safe to re-run (idempotent).

set -euo pipefail

DEMO_NAME="<demo-name>"
echo "-> teardown: ${DEMO_NAME}"

# --- S3 / object-store prefix cleanup ---------------------------------------------
# Every demo writes its data under a dedicated prefix. Delete it so a re-run starts
# clean. Override S3_BUCKET / DEMO_S3_PREFIX / S3_ENDPOINT from the environment; the
# defaults match the local stack. Deletes are idempotent (`|| true`): an already-empty
# or absent prefix is not an error.
S3_BUCKET="${S3_BUCKET:-lakehouse}"
S3_ENDPOINT="${S3_ENDPOINT:-http://localhost:8333}"
DEMO_S3_PREFIX="${DEMO_S3_PREFIX:-warehouse/<demo-name>/}"

if command -v aws >/dev/null 2>&1; then
  AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY:-lakehouse_s3}" \
  AWS_SECRET_ACCESS_KEY="${S3_SECRET_KEY:-lakehouse_s3_secret}" \
    aws --endpoint-url "${S3_ENDPOINT}" s3 rm \
      "s3://${S3_BUCKET}/${DEMO_S3_PREFIX}" --recursive >/dev/null 2>&1 || true
  echo "  cleared s3://${S3_BUCKET}/${DEMO_S3_PREFIX}"
else
  echo "  (aws CLI not found; skipping S3 prefix cleanup for s3://${S3_BUCKET}/${DEMO_S3_PREFIX})"
fi

# --- Catalog / streaming / tracking (uncomment what this demo created) ------------
# Drop UC / Iceberg tables (idempotent)
# docker exec spark-master-41 /opt/spark/bin/spark-sql -e "DROP TABLE IF EXISTS iceberg.<schema>.<table>;"

# Delete Kafka topics (idempotent)
# docker exec kafka kafka-topics --delete --if-exists --topic <topic> --bootstrap-server localhost:9092

# Clear MLflow runs by experiment (commented; requires MLflow CLI)
# mlflow experiments delete --experiment-id <id>

# Stop demo-specific services (commented; uncomment if this demo started them)
# ./lakehouse stop mlflow

echo "ok teardown: ${DEMO_NAME} complete"
