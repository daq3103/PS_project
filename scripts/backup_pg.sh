#!/usr/bin/env bash
# Nightly pg_dump sketch — run on VPS via cron, encrypt with GPG before upload.
set -euo pipefail

: "${POSTGRES_USER:?}"
: "${POSTGRES_DB:?}"
: "${BACKUP_DIR:=/var/backups/petshop}"
: "${RETENTION_DAYS:=30}"

STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "${BACKUP_DIR}"

DUMP_FILE="${BACKUP_DIR}/pg_${POSTGRES_DB}_${STAMP}.sql.gz"

pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --format=plain \
  | gzip -9 > "${DUMP_FILE}"

# Optional: gpg --symmetric --cipher-algo AES256 -o "${DUMP_FILE}.gpg" "${DUMP_FILE}" && rm -f "${DUMP_FILE}"

find "${BACKUP_DIR}" -name 'pg_*.sql.gz' -mtime +"${RETENTION_DAYS}" -delete

echo "Backup written: ${DUMP_FILE}"
