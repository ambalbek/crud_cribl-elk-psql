#!/bin/sh
set -e

# If APP_CONFIG_JSON is set (e.g. from CyberArk Conjur), write it to config.json
if [ -n "$APP_CONFIG_JSON" ]; then
  echo "Writing config.json from APP_CONFIG_JSON env var..."
  printf '%s\n' "$APP_CONFIG_JSON" > /app/config.json
fi

exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 120 app:app
