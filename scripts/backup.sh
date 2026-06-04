#!/usr/bin/env bash
# DB + 写真 をバックアップ。プロジェクト直下から: bash scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && . ./.env && set +a
PGUSER="${POSTGRES_USER:-face_vault}"
PGDB="${POSTGRES_DB:-face_vault}"
TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p backups

# 1) DB ダンプ（gzip）
DB_OUT="backups/db_${TS}.sql.gz"
docker compose exec -T db pg_dump -U "$PGUSER" -p 5449 "$PGDB" | gzip > "$DB_OUT"
echo "[backup] DB  -> $DB_OUT"

# 2) 写真ボリューム（tar.gz）
PHOTO_OUT="backups/photos_${TS}.tar.gz"
VOL="$(docker compose ps -q backend >/dev/null 2>&1; echo face_vault_photodata)"
docker run --rm -v "${VOL}:/data:ro" -v "$(pwd)/backups:/backup" alpine \
  tar czf "/backup/photos_${TS}.tar.gz" -C /data . 2>/dev/null || \
  echo "[backup] 写真ボリューム tar 失敗（ボリューム名を確認: docker volume ls）"
echo "[backup] IMG -> $PHOTO_OUT"
echo "[backup] 完了"
