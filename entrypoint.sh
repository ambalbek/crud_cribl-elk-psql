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

# Inject Cribl URLs and per-workspace base_url from environment variables.
#
# CRIBL_URLS_LIST — JSON array of Cribl leader URLs for cribl-pusher:
#   CRIBL_URLS_LIST='["https://cribl-dev:9000","https://cribl-test:9000","https://cribl-prod:9000","https://cribl-trec:9000"]'
#
# CRIBL_URLS — JSON object mapping workspace name to its Cribl leader URL:
#   CRIBL_URLS='{"dev":"https://cribl-dev:9000","test":"https://cribl-test:9000"}'
#
# CRIBL_URL_<WORKSPACE> — individual env vars (uppercase, hyphens become underscores):
#   CRIBL_URL_DEV=https://cribl-dev:9000
#
# CRIBL_BASE_URL — override the global base_url for all workspaces.
if [ -f /app/config.json ]; then
  python3 -c "
import json, os

with open('/app/config.json') as f:
    cfg = json.load(f)

changed = False

# Global base_url override
if os.environ.get('CRIBL_BASE_URL'):
    cfg['base_url'] = os.environ['CRIBL_BASE_URL']
    changed = True

# cribl_urls list for cribl-pusher
urls_list = os.environ.get('CRIBL_URLS_LIST', '')
if urls_list:
    cfg['cribl_urls'] = json.loads(urls_list)
    changed = True

# Per-workspace base_url from JSON object
workspaces = cfg.get('workspaces', {})
urls_json = os.environ.get('CRIBL_URLS', '')
if urls_json:
    for ws_name, url in json.loads(urls_json).items():
        if ws_name in workspaces:
            workspaces[ws_name]['base_url'] = url
            changed = True

# Per-workspace base_url from individual env vars
for ws_name in list(workspaces.keys()):
    env_key = 'CRIBL_URL_' + ws_name.upper().replace('-', '_')
    url = os.environ.get(env_key, '')
    if url:
        workspaces[ws_name]['base_url'] = url
        changed = True

if changed:
    with open('/app/config.json', 'w') as f:
        json.dump(cfg, f, indent=2)
    print('Cribl URLs injected into config.json')
"
fi

exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 120 app:app
