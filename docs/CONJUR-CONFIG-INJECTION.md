# CyberArk Conjur Config Injection — Implementation Guide

**Date:** 2026-10-20

All four services now support loading config.json from a CyberArk Conjur secret via the `APP_CONFIG_JSON` environment variable, eliminating the need to store config.json in git or mount it as a Kubernetes secret.

## Problem

In production (ARO / OpenShift), `config.json` cannot be checked into git — it contains database credentials, API tokens, session secrets, and inter-service tokens. The previous approach mounted it as a Kubernetes Secret (`cribl-framework-appconfig`), but this requires manual `oc create secret` commands and falls out of sync with the UCD deployment pipeline.

CyberArk Conjur is the approved secrets vault. Secrets are stored as variables and injected into pods as environment variables by the Conjur authenticator sidecar. The challenge: Conjur delivers flat string values, not files — so the entire `config.json` must be stored as a single stringified JSON string and reconstituted at container startup.

## Solution

Each service's entrypoint script checks for an `APP_CONFIG_JSON` environment variable. If set, it writes the value to `/app/config.json` before the application starts. The rest of the startup — config resolution, token wiring, database migrations — works exactly as before.

```sh
#!/bin/sh
set -e

if [ -n "$APP_CONFIG_JSON" ]; then
  printf '%s\n' "$APP_CONFIG_JSON" > /app/config.json
fi

exec gunicorn --bind 0.0.0.0:5000 app:app
```

`printf '%s\n'` is used instead of `echo` because `echo` interprets backslash sequences (`\n`, `\t`) on some shells, which would corrupt JSON values containing backslashes (e.g. in passwords or LDAP DNs).

Backwards compatible: if `APP_CONFIG_JSON` is not set, the service falls back to the mounted `config.json` file (ConfigMap or Kubernetes Secret). No code changes are needed in the application layer — only the entrypoint and Dockerfile were modified.

## Files Changed

| File | Change | Purpose |
|------|--------|---------|
| `entrypoint.sh` (new) | Created | cribl-framework: writes `APP_CONFIG_JSON` to `/app/config.json`, then starts gunicorn |
| `Dockerfile` | Updated | cribl-framework: copies `entrypoint.sh`, sets `ENTRYPOINT` instead of `CMD` |
| `cribl_service/entrypoint.sh` (new) | Created | cribl-service: writes `APP_CONFIG_JSON` to `/app/config.json`, then starts uvicorn on port 8001 |
| `cribl_service/Dockerfile` | Updated | cribl-service: copies entrypoint, sets `ENTRYPOINT` instead of `CMD` |
| `ece_service/entrypoint.sh` (new) | Created | ece-service: writes `APP_CONFIG_JSON` to `/app/config.json`, then starts uvicorn on port 8002 |
| `ece_service/Dockerfile` | Updated | ece-service: copies entrypoint, sets `ENTRYPOINT` instead of `CMD` |
| `etn_onboarding/entrypoint.sh` | Updated | etn-onboarding: added `APP_CONFIG_JSON` block before existing DB migration logic |
| `k8s-local/_config.json` | Updated | Added explicit `token` and `auth_local_users` to `etn_onboarding` section |

## CyberArk Conjur Setup

### 1. Store the config in Conjur

Create a Conjur variable for each environment. The value is the entire `config.json` as a single-line JSON string — no escaped quotes, no newlines:

```
{  "globals": {    "log_level": "INFO",    "inter_service_token": "<real-token>",    "database_url": "postgresql://user:pass@host:5432/db",    ...  },  "auth": { ... },  "etn_onboarding": {    "auth_backend": "local",    "token": "<real-token>",    "auth_local_users": [      {"username": "portal", "token": "<real-token>", "roles": ["platform_admin"]}    ]  }}
```

Conjur variable paths per environment:

| Environment | Conjur Path |
|-------------|-------------|
| Dev | `ConjurSync/AAM_NONPROD01/AAM-XXXXXXXX-CON-T-01-ONS/cribl-elk-psql-dev/app-config-json/value` |
| Nonprod | `ConjurSync/AAM_NONPROD01/AAM-XXXXXXXX-CON-T-01-ONS/cribl-elk-psql-nonprod/app-config-json/value` |
| Prod | `ConjurSync/AAM_PROD01/AAM-XXXXXXXX-CON-T-01-ONS/cribl-elk-psql-prod/app-config-json/value` |

### 2. Add to deployment manifests

Add `APP_CONFIG_JSON` to the CyberArk secrets section in each manifest file (`manifest-dev.yml`, `manifest-nonprod.yml`, `manifest-prod.yml`):

```yaml
cyberark:
  secrets:
    - name: APP_CONFIG_JSON
      value: "ConjurSync/AAM_PROD01/.../cribl-elk-psql-prod/app-config-json/value"
    - name: DATABASE_URL
      value: "ConjurSync/.../database-url/value"
    - name: SECRET_KEY
      value: "ConjurSync/.../secret-key/value"
```

`DATABASE_URL` and `SECRET_KEY` can remain as separate Conjur secrets — they override config.json values via environment variables. `APP_CONFIG_JSON` provides the base config that `config_resolver` processes.

## Token Flow

The inter-service token connects the portal (cribl-framework) to the etn-onboarding service. Three values must match:

| Config Key | Read By | Purpose |
|------------|---------|---------|
| `globals.inter_service_token` | `config_resolver` | Source of truth — auto-wires to both sides if explicit values are absent |
| `etn_onboarding.token` | `app.py` (portal) | Sent as `Authorization: Bearer <token>` in requests to etn-onboarding |
| `etn_onboarding.auth_local_users[].token` | etn_onboarding `LocalVerifier` | Accepted tokens — looked up in an in-memory dict; returns `None` (401) if not found |

**How `config_resolver` wires them** (lines 88–96 of `config_resolver.py`):

1. Sets `etn_onboarding.token` from `globals.inter_service_token` if not explicitly set
2. If `auth_local_users` is not in the `etn_onboarding` section, auto-generates it: `[{"username": "portal", "token": "<inter_service_token>", "roles": ["platform_admin"]}]`

**Root cause of the "invalid or expired token" error:** When `auth_local_users` was empty (missing from config or not injected via env var), `LocalVerifier` loaded with 0 users. Every token lookup returned `None`, producing a 401 — the error message "invalid or expired token" was misleading because the token wasn't expired, it simply wasn't in the empty user registry.

**Best practice:** Always set `etn_onboarding.token` and `etn_onboarding.auth_local_users` explicitly in the config rather than relying on `config_resolver` auto-wiring, especially in production.

## Deployment Steps

### Local (k8s-local)

Local dev uses a mounted `config.json` — no `APP_CONFIG_JSON` needed:

```sh
kubectl delete secret cribl-framework-appconfig -n cribl-elk-psql
kubectl create secret generic cribl-framework-appconfig --from-file=config.json=k8s-local/config.json -n cribl-elk-psql
kubectl rollout restart deployment cribl-framework cribl-service ece-service etn-onboarding -n cribl-elk-psql
```

### ARO / OpenShift (dev, nonprod, prod)

1. Store the full config.json as a single-line JSON string in the CyberArk Conjur variable
2. Add `APP_CONFIG_JSON` to the CyberArk secrets in the deployment manifest
3. Push the updated manifest and Dockerfiles to git
4. Let UCD deploy — the Conjur authenticator sidecar injects `APP_CONFIG_JSON` as an env var
5. The entrypoint writes it to `/app/config.json` at container startup
6. Verify by checking pod logs for `Writing config.json from APP_CONFIG_JSON env var...`

### Verification

After deployment, confirm the token flow works:

```sh
# Check etn-onboarding loaded users
oc logs deployment/etn-onboarding | grep LocalVerifier
# Expected: "LocalVerifier loaded 1 user(s)"

# Test auth from the portal pod
oc exec deployment/cribl-framework -- python -c "
import requests
r = requests.get('http://etn-onboarding:5000/api/intake/',
    headers={'Authorization': 'Bearer <your-token>'}, timeout=5)
print(r.status_code)  # Expected: 200
"
```
