#!/usr/bin/env bash
# init-storage.sh — idempotent bootstrap for the Composed storage layer (T-1.8).
#
# Creates (idempotently, safe to re-run):
#   - the S3 bucket ${S3_BUCKET} in SeaweedFS
#   - the warehouse prefixes bronze / silver / gold / _checkpoints / pipeline-history
#   - the iceberg_catalog PostgreSQL database (mlflow / airflow self-provision via
#     their own entrypoints, so they are intentionally NOT created here)
#
# Targets the effective endpoints from the environment (.env is sourced if present),
# defaulting to the published host ports for the default (non-overlay) path.
#
# Requires: aws CLI (S3), psql (PostgreSQL) on PATH.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Load .env for credentials/endpoints if present (does not override the environment).
if [ -f "${ROOT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${ROOT_DIR}/.env"
  set +a
fi

S3_ENDPOINT="${S3_ENDPOINT:-http://localhost:8333}"
S3_BUCKET="${S3_BUCKET:-lakehouse}"
S3_ACCESS_KEY="${S3_ACCESS_KEY:-admin}"
S3_SECRET_KEY="${S3_SECRET_KEY:-admin_password}"

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

# Warehouse prefixes to materialize (as zero-byte folder markers).
WAREHOUSE_PREFIXES=(bronze silver gold _checkpoints pipeline-history)

# Databases init-storage owns (others self-provision).
MANAGED_DATABASES=(iceberg_catalog)

log()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }

# --- S3 -------------------------------------------------------------------
init_s3() {
  echo "SeaweedFS S3 (${S3_ENDPOINT}, bucket ${S3_BUCKET}):"
  export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY}"
  export AWS_SECRET_ACCESS_KEY="${S3_SECRET_KEY}"
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

  local aws=(aws --endpoint-url "${S3_ENDPOINT}")

  # Bucket (idempotent): head-bucket succeeds if it already exists.
  if "${aws[@]}" s3api head-bucket --bucket "${S3_BUCKET}" >/dev/null 2>&1; then
    log "bucket ${S3_BUCKET} already exists"
  else
    "${aws[@]}" s3api create-bucket --bucket "${S3_BUCKET}" >/dev/null
    ok "created bucket ${S3_BUCKET}"
  fi

  # Warehouse prefixes as folder markers (put-object is idempotent).
  local p key
  for p in "${WAREHOUSE_PREFIXES[@]}"; do
    key="warehouse/${p}/"
    "${aws[@]}" s3api put-object --bucket "${S3_BUCKET}" --key "${key}" >/dev/null
    ok "prefix s3://${S3_BUCKET}/${key}"
  done
}

# --- PostgreSQL -----------------------------------------------------------
init_databases() {
  echo "PostgreSQL (${POSTGRES_HOST}:${POSTGRES_PORT}):"
  export PGPASSWORD="${POSTGRES_PASSWORD}"
  local psql=(psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -tAc)

  local db exists
  for db in "${MANAGED_DATABASES[@]}"; do
    exists="$("${psql[@]}" "SELECT 1 FROM pg_database WHERE datname = '${db}'" 2>/dev/null || true)"
    if [ "${exists}" = "1" ]; then
      log "database ${db} already exists"
    else
      "${psql[@]}" "CREATE DATABASE ${db}" >/dev/null
      ok "created database ${db}"
    fi
  done
}

main() {
  init_s3
  init_databases
  echo "storage bootstrap complete."
}

main "$@"
