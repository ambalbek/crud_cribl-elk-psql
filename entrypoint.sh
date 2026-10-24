#!/bin/sh
set -e

# If AZURE_CLIENT_SECRET is set (e.g. from CyberArk Conjur), write it to config.json
if [ -n "$AZURE_CLIENT_SECRET" ]; then
  echo "Writing config.json from AZURE_CLIENT_SECRET env var..."
  printf '%s' "$AZURE_CLIENT_SECRET" | python3 -c "
import json, sys
raw = sys.stdin.read().strip().strip(\"'\")
parsed = json.loads(raw)
if isinstance(parsed, str):
    # Double-wrapped: JSON string containing JSON — unwrap once more
    sys.stdout.write(parsed)
else:
    json.dump(parsed, sys.stdout, indent=2)
" > /app/config.json
fi

# Derive environment suffix from HOSTNAME
# e.g. HOSTNAME=cribl-framework-deployment-dev-XXXXXXX → DEPLOY_ENV=dev
# Service naming: <app>-service-<env> (e.g. cribl-service-service-dev)
if [ -f /app/config.json ]; then
  DEPLOY_ENV=$(echo "$HOSTNAME" | awk -F- '{print $(NF-1)}')
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

exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 120 app:app
