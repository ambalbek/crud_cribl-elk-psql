#!/bin/sh
set -e

# `flask --app wsgi:app` and alembic's `script_location = .` resolve against the
# current directory. The image sets WORKDIR=/app with the code under
# /app/etn_onboarding, so cd into this script's own dir — otherwise `wsgi` is not
# importable, `flask db upgrade` fails, and (under `set -e`) the container exits
# before migrations ever run.
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for Postgres..."
  until python -c "import os, psycopg2; psycopg2.connect(os.environ['DATABASE_URL'])" 2>/dev/null; do
    echo "Postgres not ready, retrying in 2s..."
    sleep 2
  done
  echo "Postgres is ready."

  echo "Ensuring enum types exist..."
  python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
conn.autocommit = True
cur = conn.cursor()
for stmt in [
    \"DO \$\$ BEGIN CREATE TYPE request_status_enum AS ENUM ('intake_pending','intake_validated','engagement','solutioning','storage_pending','storage_confirmed','delivery_destination','delivery_pack','delivery_route','delivery_collection','delivery_routing','delivery_storage','delivery_complete','delivery_failed','validation','reverify','complete','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;\",
    \"DO \$\$ BEGIN CREATE TYPE job_type_enum AS ENUM ('cribl_edge','etn_portal','harness_blob'); EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;\",
    \"DO \$\$ BEGIN CREATE TYPE job_status_enum AS ENUM ('pending','running','success','failed'); EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;\",
]:
    cur.execute(stmt)

# Backfill: an enum created by an older migration may lack newer values. These
# are no-ops if the value already exists. Without them a pre-existing enum that
# predates the storage/delivery states would reject those status commits.
for val in ('storage_pending','storage_confirmed','delivery_destination','delivery_pack','delivery_route','delivery_collection','delivery_routing','delivery_storage','delivery_complete','delivery_failed','validation','reverify','complete','cancelled'):
    cur.execute(\"ALTER TYPE request_status_enum ADD VALUE IF NOT EXISTS %s\" % repr(val))

cur.close()
conn.close()
print('Enum types ready.')
"

  echo "Running database migrations..."
  flask --app wsgi:app db upgrade
else
  echo "DATABASE_URL not set — skipping DB setup"
fi

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 wsgi:app
