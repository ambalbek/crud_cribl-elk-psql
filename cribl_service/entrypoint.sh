#!/bin/sh
set -e

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

exec uvicorn cribl_service.main:app --host 0.0.0.0 --port 8001
