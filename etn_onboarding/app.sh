#!/bin/sh
# ARO / HCSC startup script — referenced by deployments/manifest-*.yml as
# `appscript: app.sh`. The HCSC buildpack runs THIS instead of the image
# ENTRYPOINT (etn_onboarding/entrypoint.sh), so everything the entrypoint does
# for ARO must happen here too:
#   1. wait for Postgres
#   2. ensure the enum types exist + backfill any missing values (idempotent)
#   3. run Alembic migrations (flask db upgrade)
#   4. start gunicorn
#
# Why this file matters: without it the buildpack had no start script, the image
# ENTRYPOINT was bypassed, migrations never ran, and request_status_enum was
# missing the newer delivery states. Any transition to e.g. delivery_complete
# then failed on commit and the request status never persisted to Postgres.
set -e

# Resolve into the package dir so `wsgi:app` imports and `migrations/` (alembic
# script_location = .) both resolve exactly as they do under the image ENTRYPOINT
# and docker-compose.
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for Postgres..."
  i=0
  until python -c "import os, psycopg2; psycopg2.connect(os.environ['DATABASE_URL'])" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 60 ]; then
      echo "Postgres still not reachable after ~120s — aborting." >&2
      exit 1
    fi
    echo "Postgres not ready, retrying in 2s..."
    sleep 2
  done
  echo "Postgres is ready."

  # ── Ensure enum types exist (autocommit — CREATE TYPE / ALTER TYPE ADD VALUE
  #    must not run inside the migration transaction on all PG versions) ────────
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

# Backfill: an enum created by an older migration may lack newer values.
# ADD VALUE IF NOT EXISTS is a no-op when the value already exists.
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
exec gunicorn --bind "0.0.0.0:${PORT:-5000}" wsgi:app
