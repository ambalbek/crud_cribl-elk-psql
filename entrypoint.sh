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
    sys.stdout.write(parsed)
else:
    json.dump(parsed, sys.stdout, indent=2)
" > /app/config.json
fi

# Derive environment suffix from HOSTNAME
# e.g. HOSTNAME=cribl-framework-deployment-dev-XXXXXXX → DEPLOY_ENV=dev
# Service naming: <app>-service-<env> (e.g. cribl-service-service-dev)
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

# Inject Cribl master node URLs into workspace base_url fields.
# Reads from env vars set by Conjur:
#   CRIBL_URL_DEV, CRIBL_URL_TEST, CRIBL_URL_ALTPROD, CRIBL_URL_PROD
# Each is a comma-separated list of master node URLs.
# Skips any that are not set.
if [ -f /app/config.json ]; then
  python3 -c "
import json, os

url_map = {
    'dev':     os.environ.get('CRIBL_URL_DEV', ''),
    'test':    os.environ.get('CRIBL_URL_TEST', ''),
    'altprod': os.environ.get('CRIBL_URL_ALTPROD', ''),
    'prod':    os.environ.get('CRIBL_URL_PROD', ''),
}

with open('/app/config.json') as f:
    cfg = json.load(f)

workspaces = cfg.get('workspaces', {})
injected = 0
for ws_name, raw in url_map.items():
    if not raw or ws_name not in workspaces:
        continue
    urls = [u.strip().rstrip('/') for u in raw.split(',') if u.strip()]
    # single URL → string, multiple → list
    workspaces[ws_name]['base_url'] = urls[0] if len(urls) == 1 else urls
    injected += 1

with open('/app/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
print(f'Cribl master URLs injected: {injected} workspace(s)')
"
fi

exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 120 app:app
