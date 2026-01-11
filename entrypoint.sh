#!/bin/sh
set -e

echo "Waiting for database and creating tables..."
until python /app/create_tables.py; do
  echo "create_tables.py failed, retrying in 2s..."
  sleep 2
done

echo "Starting app"
exec uvicorn main:app --host 0.0.0.0 --port 8002