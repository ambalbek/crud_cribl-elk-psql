#!/bin/sh
set -e

cd /app/etn_onboarding

# ── Bootstrap config.json from base + creds ──────────────────────────────────
if [ -f /app/config.base.json ]; then
  cp /app/config.base.json /app/config.json
  echo "Starting from config.base.json (no creds)"
fi

if [ -n "$AZURE_CLIENT_SECRET" ]; then
  echo "Merging credentials from AZURE_CLIENT_SECRET (Conjur)..."
  printf '%s' "$AZURE_CLIENT_SECRET" | python3 -c "
import json, sys
raw = sys.stdin.read().strip().strip(\"'\")
parsed = json.loads(raw)
if isinstance(parsed, str):
    print(parsed)
else:
    json.dump(parsed, sys.stdout)
" | python3 /app/merge_creds.py
elif [ -f /app/config-secret/config.json ]; then
  echo "Merging credentials from mounted secret..."
  python3 /app/merge_creds.py < /app/config-secret/config.json
fi

# Derive environment suffix from HOSTNAME
if [ -f /app/config.json ] && echo "$HOSTNAME" | grep -q -- '-deployment-'; then
  DEPLOY_ENV=$(echo "$HOSTNAME" | sed 's/.*-deployment-//' | awk -F- '{print $1}')
  echo "Detected DEPLOY_ENV=${DEPLOY_ENV} from HOSTNAME=${HOSTNAME}"
  python3 -c "
import sys, re
env = sys.argv[1]
with open('/app/config.json') as f:
    text = f.read()
for svc in ['cribl-service', 'ece-service', 'etn-onboarding', 'cribl-framework']:
    text = re.sub(r'http://' + svc + r':', 'http://' + svc + '-service-' + env + ':', text)
with open('/app/config.json', 'w') as f:
    f.write(text)
" "$DEPLOY_ENV"
fi

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
  python -c "
import os, glob, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
conn.autocommit = True
cur = conn.cursor()

cur.execute(\"SELECT to_regclass('public.onboarding_requests')\")
tables_exist = cur.fetchone()[0] is not None

cur.execute(\"SELECT to_regclass('public.alembic_version')\")
alembic_exists = cur.fetchone()[0] is not None

has_version = False
current_rev = None
if alembic_exists:
    cur.execute('SELECT version_num FROM alembic_version LIMIT 1')
    row = cur.fetchone()
    if row and row[0]:
        has_version = True
        current_rev = row[0]

# Get all known revision IDs from migration files on disk
known = set()
for f in glob.glob('migrations/versions/*.py'):
    base = os.path.basename(f).replace('.py', '')
    known.add(base)

if has_version and current_rev not in known:
    # DB references a revision that no longer exists (e.g. removed 009)
    # Find the latest known revision by filename sort
    latest = sorted(known)[-1] if known else None
    if latest:
        print(f'alembic_version references unknown revision \"{current_rev}\" — resetting to \"{latest}\"')
        cur.execute('UPDATE alembic_version SET version_num = %s', (latest,))
    else:
        print('No migration files found — clearing alembic_version')
        cur.execute('DELETE FROM alembic_version')
elif tables_exist and not has_version:
    print('Tables exist but alembic is not tracking — stamping at 001_initial')
    cur.close()
    conn.close()
    import subprocess, sys
    subprocess.run([sys.executable, '-m', 'flask', '--app', 'wsgi:app', 'db', 'stamp', '001_initial'], check=True)
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.autocommit = True
    cur = conn.cursor()
else:
    print('DB state OK — proceeding with migrations')

cur.close()
conn.close()
"
  flask --app wsgi:app db upgrade
else
  echo "DATABASE_URL not set — skipping DB setup"
fi

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 wsgi:app
