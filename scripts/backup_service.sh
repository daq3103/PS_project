#!/bin/sh
# Optional backup sidecar. Writes only beneath /backup; never deletes existing backups.
set -eu
root=/backup
interval=${BACKUP_INTERVAL_SECONDS:-86400}
maximum=${BACKUP_MAX_TOTAL_MB:-5000}
media_limit=${BACKUP_MAX_MEDIA_MB:-500}
for value in "$interval" "$maximum" "$media_limit"; do
  case "$value" in ''|*[!0-9]*) echo 'Invalid backup resource limit'; exit 2;; esac
done
[ "$interval" -ge 3600 ] || exit 2
mkdir -p "$root"
backup_once() {
  available_kb=$(df -Pk "$root" | tail -1 | awk '{print $4}')
  used_kb=$(du -sk "$root" | awk '{print $1}')
  media_kb=$(du -sk /media | awk '{print $1}')
  db_bytes=$(psql -Atqc 'SELECT pg_database_size(current_database())')
  estimate_kb=$((db_bytes / 1024 + media_kb + 10240))
  [ "$media_kb" -le $((media_limit * 1024)) ] || { echo 'Backup skipped: media limit reached'; return 1; }
  [ $((used_kb + estimate_kb)) -le $((maximum * 1024)) ] || { echo 'Backup skipped: retention capacity reached; archive old backups after verification'; return 1; }
  [ "$available_kb" -gt $((estimate_kb + 1024 * 1024)) ] || { echo 'Backup skipped: reserve at least 1 GB free disk'; return 1; }
  token=$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')
  name="pethome-$(date -u +%Y%m%dT%H%M%SZ)-$token"
  path="$root/$name.partial"
  mkdir "$path"
  pg_dump --format=custom --file="$path/database.dump" || return 1
  tar -czf "$path/rescue-images.tar.gz" -C /media . || return 1
  (cd "$path" && sha256sum database.dump rescue-images.tar.gz > SHA256SUMS && sha256sum -c SHA256SUMS) || return 1
  printf '{"created_at":"%s","status":"complete","name":"%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name" > "$path/manifest.json"
  mv "$path" "$root/$name"
  cp "$root/$name/manifest.json" "$root/last-success.json.tmp"
  mv "$root/last-success.json.tmp" "$root/last-success.json"
  echo "Backup completed and checksummed: $name"
}
while :; do
  backup_once || echo 'Backup failed; previous copies retained. Check disk, destination and database access.'
  sleep "$interval"
done
