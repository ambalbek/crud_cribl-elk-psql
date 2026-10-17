-- Create additional databases in the same postgres instance.
-- This file is mounted as a docker-entrypoint-initdb.d script.
-- Note: this only runs on first init. If the volume already exists,
-- manually run: CREATE DATABASE cribl_framework;
SELECT 'CREATE DATABASE cribl_framework'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'cribl_framework')\gexec
GRANT ALL PRIVILEGES ON DATABASE cribl_framework TO etn_user;
