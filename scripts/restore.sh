#!/usr/bin/env bash
# DBリストア。 bash scripts/restore.sh backups/db_YYYYMMDD_HHMMSS.sql.gz
# 写真は: tar xzf backups/photos_*.tar.gz を photodata ボリュームへ展開（下部コメント参照）
set -euo pipefail
cd "$(dirname "$0")/.."

DUMP="${1:-}"
[ -z "$DUMP" ] && { echo "usage: bash scripts/restore.sh <db_dump.sql.gz>"; exit 1; }
[ -f "$DUMP" ] || { echo "not found: $DUMP"; exit 1; }

[ -f .env ] && set -a && . ./.env && set +a
PGUSER="${POSTGRES_USER:-face_vault}"
PGDB="${POSTGRES_DB:-face_vault}"

echo "[restore] $DUMP -> DB $PGDB （既存データに上書き）"
gunzip -c "$DUMP" | docker compose exec -T db psql -U "$PGUSER" -p 5449 -d "$PGDB"
echo "[restore] 完了。backend 再起動推奨: docker compose restart backend"

# 写真リストア例:
#   docker run --rm -v face_vault_photodata:/data -v "$(pwd)/backups:/backup" alpine \
#     sh -c 'cd /data && tar xzf /backup/photos_YYYYMMDD_HHMMSS.tar.gz'
