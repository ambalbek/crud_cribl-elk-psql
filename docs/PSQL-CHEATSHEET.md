# PostgreSQL Cheatsheet — Cribl Framework

## Connect

```bash
# From host (docker compose)
docker compose exec etn_postgres psql -U etn_user -d etn_onboarding

# From host (docker compose dev)
docker compose -f docker-compose_dev.yml exec etn_postgres psql -U etn_user -d etn_onboarding

# Direct connection (if port 5433 is exposed)
psql -h localhost -p 5433 -U etn_user -d etn_onboarding

# Connect to the framework DB (legacy portal records)
docker compose exec etn_postgres psql -U etn_user -d cribl_framework
```

## Databases

```sql
-- List all databases
\l

-- Switch database
\c etn_onboarding
\c cribl_framework
```

## Tables

```sql
-- List all tables
\dt

-- Describe a table (columns, types)
\d onboarding_requests
\d audit_logs
\d delivery_jobs

-- Show table with constraints
\d+ onboarding_requests
```

## View Data

```sql
-- All onboarding requests
SELECT * FROM onboarding_requests;

-- Readable summary (most useful columns)
SELECT
  id,
  apm_id,
  app_name,
  status,
  environment,
  region,
  data_type,
  created_at
FROM onboarding_requests
ORDER BY created_at DESC;

-- Count by status
SELECT status, COUNT(*) FROM onboarding_requests GROUP BY status ORDER BY count DESC;

-- Count by environment
SELECT env, COUNT(*)
FROM onboarding_requests, jsonb_array_elements_text(environment) AS env
GROUP BY env ORDER BY count DESC;

-- Find by APM ID
SELECT * FROM onboarding_requests WHERE apm_id = 'APP001';

-- Find by app name (partial match)
SELECT * FROM onboarding_requests WHERE app_name ILIKE '%payments%';

-- Find by status
SELECT * FROM onboarding_requests WHERE status = 'intake_pending';

-- Find by environment (JSONB array contains)
SELECT * FROM onboarding_requests WHERE environment @> '["dev"]';
SELECT * FROM onboarding_requests WHERE environment @> '["prod"]';

-- Find requests from last 24 hours
SELECT * FROM onboarding_requests WHERE created_at > NOW() - INTERVAL '24 hours';

-- Find requests from last 7 days
SELECT * FROM onboarding_requests WHERE created_at > NOW() - INTERVAL '7 days';
```

## Audit Logs

```sql
-- All audit entries for a request
SELECT
  a.stage,
  a.action,
  a.actor,
  a.outcome,
  a.created_at
FROM audit_logs a
JOIN onboarding_requests r ON a.request_id = r.id
WHERE r.apm_id = 'APP001'
ORDER BY a.created_at;

-- Recent audit activity
SELECT
  r.apm_id,
  a.stage,
  a.action,
  a.actor,
  a.created_at
FROM audit_logs a
JOIN onboarding_requests r ON a.request_id = r.id
ORDER BY a.created_at DESC
LIMIT 20;
```

## Delivery Jobs

```sql
-- Jobs for a request
SELECT
  j.job_type,
  j.status,
  j.started_at,
  j.completed_at
FROM delivery_jobs j
JOIN onboarding_requests r ON j.request_id = r.id
WHERE r.apm_id = 'APP001';

-- Failed jobs
SELECT
  r.apm_id,
  j.job_type,
  j.status,
  j.result,
  j.completed_at
FROM delivery_jobs j
JOIN onboarding_requests r ON j.request_id = r.id
WHERE j.status = 'failed'
ORDER BY j.completed_at DESC;
```

## Update Data

```sql
-- Update request status
UPDATE onboarding_requests SET status = 'complete' WHERE apm_id = 'APP001';

-- Update environment
UPDATE onboarding_requests SET environment = '["dev", "prod"]'::jsonb WHERE apm_id = 'APP001';

-- Cancel a request
UPDATE onboarding_requests SET status = 'cancelled' WHERE apm_id = 'APP001';

-- Bulk update status
UPDATE onboarding_requests SET status = 'cancelled' WHERE status = 'intake_pending' AND created_at < NOW() - INTERVAL '90 days';
```

## Delete Data

```sql
-- Delete a specific request (cascades to audit_logs and delivery_jobs)
DELETE FROM onboarding_requests WHERE apm_id = 'APP001';

-- Delete old cancelled requests
DELETE FROM onboarding_requests WHERE status = 'cancelled' AND created_at < NOW() - INTERVAL '180 days';

-- WARNING: Delete all data (use with caution)
TRUNCATE onboarding_requests CASCADE;
```

## Legacy Framework DB (cribl_framework)

```sql
-- Switch to framework DB
\c cribl_framework

-- View legacy portal records
SELECT * FROM onboarding_requests ORDER BY timestamp DESC;

-- Readable summary
SELECT
  request_id,
  apmid,
  appname,
  status,
  environment,
  region,
  timestamp
FROM onboarding_requests
ORDER BY timestamp DESC;

-- Find by request ID
SELECT * FROM onboarding_requests WHERE request_id = 'REQ-20260926-A1B2C3D4';

-- Update legacy status
UPDATE onboarding_requests SET status = 'done' WHERE request_id = 'REQ-20260926-A1B2C3D4';
```

## JSONB Queries

```sql
-- Environment is a JSONB array, query with these operators:

-- Contains (does array include this value?)
SELECT * FROM onboarding_requests WHERE environment @> '["prod"]';

-- Any of these values
SELECT * FROM onboarding_requests WHERE environment ?| array['dev', 'test'];

-- All of these values
SELECT * FROM onboarding_requests WHERE environment ?& array['dev', 'prod'];

-- Expand array elements
SELECT apm_id, jsonb_array_elements_text(environment) AS env FROM onboarding_requests;

-- Log destinations (also JSONB array)
SELECT * FROM onboarding_requests WHERE log_destinations @> '["elk"]';

-- ELK capacity details (JSONB in form_data)
SELECT apm_id, form_data->'elk_capacity' FROM onboarding_requests WHERE form_data ? 'elk_capacity';

-- Entitlement groups
SELECT apm_id, jsonb_array_elements_text(entitlement_groups) AS grp FROM onboarding_requests;
```

## Migrations

```sql
-- Check migration history
SELECT * FROM alembic_version;

-- Check current version
SELECT version_num FROM alembic_version;
```

## Useful psql Commands

```
\q          -- quit
\l          -- list databases
\dt         -- list tables
\d TABLE    -- describe table
\d+ TABLE   -- describe table with details
\x          -- toggle expanded output (vertical rows)
\x auto     -- auto-expand for wide tables
\timing     -- toggle query timing
\i FILE     -- execute SQL file
\copy       -- export/import CSV
```

## Export Data

```sql
-- Export to CSV
\copy (SELECT * FROM onboarding_requests ORDER BY created_at DESC) TO '/tmp/requests.csv' WITH CSV HEADER;

-- Export specific columns
\copy (SELECT apm_id, app_name, status, environment, created_at FROM onboarding_requests) TO '/tmp/requests_summary.csv' WITH CSV HEADER;

-- From outside the container
docker compose exec etn_postgres psql -U etn_user -d etn_onboarding -c "\copy (SELECT * FROM onboarding_requests) TO STDOUT WITH CSV HEADER" > requests.csv
```

## Backup & Restore

```bash
# Backup
docker compose exec etn_postgres pg_dump -U etn_user etn_onboarding > backup_etn.sql
docker compose exec etn_postgres pg_dump -U etn_user cribl_framework > backup_framework.sql

# Backup (compressed)
docker compose exec etn_postgres pg_dump -U etn_user -Fc etn_onboarding > backup_etn.dump

# Restore
docker compose exec -i etn_postgres psql -U etn_user -d etn_onboarding < backup_etn.sql

# Restore (compressed)
docker compose exec -i etn_postgres pg_restore -U etn_user -d etn_onboarding < backup_etn.dump
```
