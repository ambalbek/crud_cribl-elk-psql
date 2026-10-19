#!/bin/sh
set -e

cd /app/etn_onboarding

# If DATABASE_URL env var is not set, try to read it from config.json
if [ -z "$DATABASE_URL" ] && [ -f /app/config.json ]; then
  DATABASE_URL=$(python -c "
import json,sys
sys.path.insert(0,'/app')
try:
    from config_resolver import resolve_config
    c = resolve_config(json.load(open('/app/config.json')))
except Exception:
    c = json.load(open('/app/config.json'))
print(c.get('etn_onboarding',{}).get('database_url','') or c.get('globals',{}).get('database_url',''))
" 2>/dev/null || true)
  export DATABASE_URL
fi

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
    \"DO \$\$ BEGIN CREATE TYPE request_status_enum AS ENUM ('intake_pending','intake_validated','engagement','solutioning','storage_pending','storage_confirmed','delivery_destination','delivery_pack','delivery_route','delivery_collection','delivery_routing','delivery_storage','delivery_complete','delivery_failed','validation','reverify','complete','cancelled','offboarded'); EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;\",
    \"DO \$\$ BEGIN CREATE TYPE job_type_enum AS ENUM ('cribl_edge','etn_portal','harness_blob'); EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;\",
    \"DO \$\$ BEGIN CREATE TYPE job_status_enum AS ENUM ('pending','running','success','failed'); EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;\",
]:
    cur.execute(stmt)
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
