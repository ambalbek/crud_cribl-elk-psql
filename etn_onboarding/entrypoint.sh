#!/bin/sh
set -e

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
cur.close()
conn.close()
print('Enum types ready.')
"

echo "Running database migrations..."
flask --app wsgi:app db upgrade

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 wsgi:app
