#!/usr/bin/env bash
set -euo pipefail

# Example PostgreSQL backup script. Keep backup files out of git.

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=eidolon}"
: "${PGUSER:=eidolon}"
: "${BACKUP_DIR:=backups}"

mkdir -p "${BACKUP_DIR}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${BACKUP_DIR}/eidolon-${timestamp}.dump"

pg_dump \
  --host "${PGHOST}" \
  --port "${PGPORT}" \
  --username "${PGUSER}" \
  --dbname "${PGDATABASE}" \
  --format custom \
  --file "${output}"

echo "Wrote ${output}"
