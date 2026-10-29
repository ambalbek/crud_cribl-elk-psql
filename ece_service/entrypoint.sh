#!/bin/sh
set -e

APP_DIR="$(pwd)"

# ── Bootstrap config.json from base + Conjur creds ───────────────────────────
if [ -f "$APP_DIR/config.base.json" ]; then
  cp "$APP_DIR/config.base.json" "$APP_DIR/config.json"
  echo "Starting from config.base.json"
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
" | python3 "$APP_DIR/merge_creds.py" "$APP_DIR/config.json"
elif [ -f "$APP_DIR/config-secret/config.json" ]; then
  echo "Merging credentials from mounted secret..."
  python3 "$APP_DIR/merge_creds.py" "$APP_DIR/config.json" < "$APP_DIR/config-secret/config.json"
fi

# Derive environment suffix from HOSTNAME
if [ -f "$APP_DIR/config.json" ] && echo "$HOSTNAME" | grep -q -- '-deployment-'; then
  DEPLOY_ENV=$(echo "$HOSTNAME" | sed 's/.*-deployment-//' | awk -F- '{print $1}')
  echo "Detected DEPLOY_ENV=${DEPLOY_ENV} from HOSTNAME=${HOSTNAME}"
  python3 -c "
import sys, re
env = sys.argv[1]
with open(sys.argv[2]) as f:
    text = f.read()
for svc in ['cribl-service', 'ece-service', 'etn-onboarding', 'cribl-framework']:
    text = re.sub(r'http://' + svc + r':', 'http://' + svc + '-service-' + env + ':', text)
with open(sys.argv[2], 'w') as f:
    f.write(text)
" "$DEPLOY_ENV" "$APP_DIR/config.json"
fi

exec uvicorn ece_service.main:app --host 0.0.0.0 --port 8002
