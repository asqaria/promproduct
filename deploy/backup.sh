#!/bin/sh
# Ежесуточный бэкап: БД (pg_dump custom) + медиа. Хранение 14 дней.
set -eu

APP_DIR=/opt/promproduct
BACKUP_DIR=/var/backups/promproduct
KEEP_DAYS=14
STAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$BACKUP_DIR/db-$STAMP.dump"
tar -czf "$BACKUP_DIR/media-$STAMP.tar.gz" -C "$APP_DIR" media

find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -delete
echo "Backup $STAMP done"
