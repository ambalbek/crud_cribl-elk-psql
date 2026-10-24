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

# Derive environment suffix from deployment name via HOSTNAME
# e.g. HOSTNAME=cribl-framework-dev-7f8b9c6d4-x2k5m → DEPLOY_ENV=dev
if [ -f /app/config.json ]; then
  DEPLOY_ENV=$(echo "$HOSTNAME" | awk -F- '{print $(NF-2)}')
  echo "Detected DEPLOY_ENV=${DEPLOY_ENV} from HOSTNAME=${HOSTNAME}"
  python3 -c "
import sys, re
with open('/app/config.json') as f:
    text = f.read()
for svc in ['cribl-service', 'ece-service', 'etn-onboarding', 'cribl-framework']:
    text = re.sub(r'http://' + svc + r':', 'http://' + svc + '-' + sys.argv[1] + ':', text)
with open('/app/config.json', 'w') as f:
    f.write(text)
" "$DEPLOY_ENV"
fi

exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 120 app:app
