# ARO Deployment Guide — Cribl Framework

## Prerequisites

- `oc` CLI logged into your ARO cluster
- Docker (for building images)
- Access to your Nexus registry (`nexus.XXXXXXXX.com:8083`)
- PostgreSQL, Elasticsearch, and Cribl Stream accessible from the ARO namespace

---

## 1. Prepare config.json

Copy the example and fill in your real values:

```bash
cp config.example.json config.json
```

**Minimal config.json with globals:**

```json
{
  "globals": {
    "log_level": "INFO",
    "skip_ssl": false,
    "secret_key": "<generate: python -c 'import secrets; print(secrets.token_hex(32))'>",
    "database_url": "postgresql://USER:PASS@POSTGRES_HOST:5432/etn_onboarding",
    "elasticsearch_url": "https://ES_HOST:9200",
    "elasticsearch_token": "<ES ApiKey or leave empty for user/pass>",
    "elasticsearch_username": "elastic",
    "elasticsearch_password": "<ES password>",
    "cribl_url": "https://CRIBL_STREAM_HOST:9000",
    "cribl_token": "",
    "cribl_username": "<Cribl admin user>",
    "cribl_password": "<Cribl admin password>",
    "cribl_service_url": "http://cribl-service:8001",
    "ece_service_url": "http://ece-service:8002",
    "etn_onboarding_url": "http://etn-onboarding:5000",
    "inter_service_token": "<generate: python -c 'import secrets; print(secrets.token_hex(16))'>"
  },

  "auth": {
    "session_lifetime_minutes": 480,
    "local_admins": [
      {"username": "admin", "password": "<portal admin password>", "display_name": "Admin"}
    ]
  },

  "workspaces": {
    "dev": {
      "worker_groups": ["default", "wg-dev-01"],
      "dest_templates": {"azn": "blob_dest_template_azn_dev.json", "azs": "blob_dest_template_azs_dev.json"},
      "description": "Development"
    },
    "prod": {
      "worker_groups": ["wg-prod-01"],
      "dest_templates": {"azn": "blob_dest_template_azn_prod.json", "azs": "blob_dest_template_azs_prod.json"},
      "description": "Production",
      "require_allow": true
    }
  },

  "route_templates": {"azn": "route_template_azn.json", "azs": "route_template_azs.json"},
  "dest_prefixes": {"azn": "hcsc-blob-storage-northcentralus", "azs": "hcsc-blob-storage-southcentralus"},

  "entitlement": {
    "clusters": [
      {"name": "nonprod"},
      {"name": "prod", "url": "https://PROD_ES_HOST:9200", "token": "<prod ES ApiKey>"}
    ],
    "entitlementFilter": "entitlements"
  },

  "ece": {
    "es_url_prod": "https://PROD_ES_HOST:9200",
    "es_token_prod": "<prod ES ApiKey>"
  },

  "ldap": {
    "server": "ldaps://ldap.corp.example.com:636",
    "bind_dn": "CN=svc-cribl,OU=ServiceAccounts,DC=corp,DC=example,DC=com",
    "bind_pw": "<LDAP bind password>",
    "base_dn": "DC=corp,DC=example,DC=com",
    "use_ssl": true
  }
}
```

**Do NOT commit this file to git.** It contains credentials.

---

## 2. Build and Push Images

```bash
# From project root
docker build -t nexus.XXXXXXXX.com:8083/cribl-framework:latest -f Dockerfile .
docker build -t nexus.XXXXXXXX.com:8083/cribl-service:latest -f cribl_service/Dockerfile .
docker build -t nexus.XXXXXXXX.com:8083/ece-service:latest -f ece_service/Dockerfile .
docker build -t nexus.XXXXXXXX.com:8083/etn-onboarding:latest -f etn_onboarding/Dockerfile .

docker push nexus.XXXXXXXX.com:8083/cribl-framework:latest
docker push nexus.XXXXXXXX.com:8083/cribl-service:latest
docker push nexus.XXXXXXXX.com:8083/ece-service:latest
docker push nexus.XXXXXXXX.com:8083/etn-onboarding:latest
```

---

## 3. Create the Secret

```bash
oc create secret generic cribl-framework-appconfig \
  --from-file=config.json \
  -n <namespace>
```

---

## 4. Deploy

```bash
oc apply -f openshift/services.yml
oc apply -f openshift/cribl-framework-deployment.yml
oc apply -f openshift/cribl-service-deployment.yml
oc apply -f openshift/ece-service-deployment.yml
oc apply -f openshift/etn-onboarding-deployment.yml
oc apply -f openshift/routes.yml
```

---

## 5. Verify

```bash
# All pods should be Running with 1/1 READY
oc get pods -l app=cribl-elk-psql

# Check startup logs for each service
oc logs deployment/cribl-framework --tail=20
oc logs deployment/cribl-service --tail=20
oc logs deployment/ece-service --tail=20
oc logs deployment/etn-onboarding --tail=20
```

**cribl-framework startup logs should show:**
```
============================================================
cribl-framework startup config:
  CRIBL_SERVICE_URL:   http://cribl-service:8001
  ECE_SERVICE_URL:     http://ece-service:8002
  ETN_ONBOARDING_URL:  http://etn-onboarding:5000
  ETN_ONBOARDING_TOKEN: set
  config.json base_url: https://your-cribl-host:9000
  config.json credentials.username: admin
  config.json database.url: set
  config.json datastream.elk_url: https://your-es-host:9200
============================================================
PostgreSQL connected — your-postgres-host:5432/etn_onboarding
```

**cribl-service startup logs should show:**
```
============================================================
cribl-service startup config:
  CRIBL_BASE_URL:  https://your-cribl-host:9000
  CRIBL_TOKEN:     (empty)
  CRIBL_USERNAME:  admin
  CRIBL_PASSWORD:  ***
  CRIBL_SKIP_SSL:  False
============================================================
```

---

## 6. Update the Secret (after config changes)

```bash
oc create secret generic cribl-framework-appconfig \
  --from-file=config.json \
  --dry-run=client -o yaml | oc apply -f -

oc rollout restart deployment/cribl-framework \
  deployment/cribl-service \
  deployment/ece-service \
  deployment/etn-onboarding
```

---

## Architecture

```
                    ┌─────────────────────┐
                    │   config.json        │
                    │   (K8s Secret)       │
                    └──────┬──────────────┘
                           │ mounted at /app/config.json
            ┌──────────────┼──────────────┬─────────────────┐
            ▼              ▼              ▼                 ▼
    ┌───────────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐
    │cribl-framework│ │cribl-svc │ │ece-svc   │ │etn-onboarding  │
    │  :5000        │ │  :8001   │ │  :8002   │ │  :5000         │
    └───────┬───────┘ └────┬─────┘ └────┬─────┘ └───────┬────────┘
            │              │            │               │
            │  HTTP calls  │            │               │
            ├─────────────►│            │               │
            ├──────────────┼───────────►│               │
            ├──────────────┼────────────┼──────────────►│
            │              │            │               │
            │              ▼            ▼               ▼
            │         Cribl Stream  Elasticsearch    PostgreSQL
            │           :9000        :9200            :5432
            │              ▲            ▲
            └──────────────┘            │
              (catalog direct)          │
                                        │
```

- **cribl-framework** — Portal UI, catalog, entitlements, pusher. Calls other 3 services over HTTP.
- **cribl-service** — Proxy to Cribl Stream API. Routes, destinations, packs, provisioning.
- **ece-service** — Proxy to Elasticsearch/Kibana. Roles, role-mappings, ILM.
- **etn-onboarding** — Onboarding state machine. Request lifecycle management.
- All 4 read config.json from the same Secret.

---

## Troubleshooting Runbook

### Pod not starting / CrashLoopBackOff

```bash
# Check logs
oc logs deployment/<service-name> --tail=50

# Check if secret is mounted
oc exec deployment/<service-name> -- cat /app/config.json | head -5

# Check if image is latest
oc describe deployment/<service-name> | grep Image
```

**Common causes:**
- Secret `cribl-framework-appconfig` doesn't exist → `oc get secret cribl-framework-appconfig`
- config.json has invalid JSON → `python -m json.tool < config.json`
- Image not pushed → rebuild and push

---

### 401 Unauthorized (Cribl auth failure)

**Symptoms:** Catalog empty, destinations empty, pusher fails.

**Diagnose:**
```bash
# Check what credentials are being used
oc logs deployment/cribl-service --tail=20 | grep "CRIBL_BASE_URL\|CRIBL_USERNAME"

# Test Cribl auth from inside the pod
oc exec deployment/cribl-service -- curl -sk -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USER","password":"YOUR_PASS"}' \
  https://YOUR_CRIBL_URL:9000/api/v1/auth/login
```

**Fix:** Update `globals.cribl_username` / `globals.cribl_password` in config.json and recreate the secret.

---

### 429 Rate Limited (Cribl login)

**Symptoms:** `catalog — Cribl auth failed ws=...: 429`

**Cause:** Too many login attempts (Cribl rate-limits `/api/v1/auth/login`).

**Fix:** Wait 5 minutes for the rate limit to expire, or use a `globals.cribl_token` (bearer token) instead of username/password. Tokens skip the login endpoint entirely.

---

### Status stuck at intake_pending

**Symptoms:** Request submitted, pusher ran successfully, but status doesn't change.

**Diagnose:**
```bash
# Check if PSQL update happened
oc logs deployment/cribl-framework --tail=30 | grep "PSQL status"

# Check the database directly
oc exec deployment/postgres -- psql -U <user> -d etn_onboarding \
  -c "SELECT apm_id, status FROM onboarding_requests;"
```

**Common causes:**
- cribl-framework and etn-onboarding pointing to different databases
  - Both `globals.database_url` and `etn_onboarding.database_url` must point to the **same** database
- Status enum mismatch — the DB uses `request_status_enum` (valid values: `intake_pending`, `delivery_complete`, `complete`, `cancelled`, etc.)

---

### Entitlements page empty

**Symptoms:** Page loads but shows no role mappings.

**Diagnose:**
```bash
# Check logs
oc logs deployment/cribl-framework --tail=20 | grep -i "entitle\|cluster\|role_mapping"

# Test ES directly
oc exec deployment/cribl-framework -- curl -sk -u elastic:PASS \
  https://ES_HOST:9200/_security/role_mapping
```

**Common causes:**
- ES has no custom role mappings (fresh cluster)
- `entitlementFilter` doesn't match any DN in the mappings — role mappings must contain the filter string (default: `entitlements`) in their rules
- ES credentials wrong — check `globals.elasticsearch_username` / `globals.elasticsearch_password`

---

### Destinations page empty

**Symptoms:** Page loads, dropdown shows no destinations.

**Diagnose:**
```bash
# Test cribl-service directly
oc exec deployment/cribl-service -- curl -s http://localhost:8001/cribl/stream/destinations?worker_group=default
```

**Fix:** If cribl-service returns data but UI is empty, check that response format is `{items: [...]}`. If cribl-service returns nothing, check Cribl Stream credentials.

---

### Database connection errors

**Symptoms:** `DATABASE_URL not set` or `could not connect to server`

**Diagnose:**
```bash
# Check what URL is being used
oc logs deployment/cribl-framework --tail=20 | grep "PostgreSQL"
oc logs deployment/etn-onboarding --tail=20 | grep "Postgres"

# Test from pod
oc exec deployment/cribl-framework -- python -c \
  "import psycopg2; psycopg2.connect('postgresql://USER:PASS@HOST:5432/DB'); print('OK')"
```

**Fix:** Update `globals.database_url` in config.json.

---

### How to check the resolved config

Verify what the pods actually see after globals resolution:

```bash
oc exec deployment/cribl-framework -- python -c "
import json
from config_resolver import resolve_config
c = resolve_config(json.load(open('config.json')))
print('base_url:', c.get('base_url'))
print('cribl_service_url:', c.get('cribl_service_url'))
print('database.url:', c.get('database',{}).get('url','')[:40])
print('datastream.elk_url:', c.get('datastream',{}).get('elk_url'))
print('ece.es_url:', c.get('ece',{}).get('es_url'))
print('etn.database_url:', c.get('etn_onboarding',{}).get('database_url','')[:40])
print('etn.token:', bool(c.get('etn_onboarding',{}).get('token')))
print('clusters:', len(c.get('entitlement',{}).get('clusters',[])))
"
```

---

### How to rollback

```bash
# See deployment history
oc rollout history deployment/cribl-framework

# Rollback to previous version
oc rollout undo deployment/cribl-framework
oc rollout undo deployment/cribl-service
oc rollout undo deployment/ece-service
oc rollout undo deployment/etn-onboarding
```

---

## Contact

For issues not covered here, check:
- Pod logs: `oc logs deployment/<name> --tail=50`
- Startup diagnostics: look for the `====` banner in cribl-framework and cribl-service logs
- Config resolution: use the `oc exec` command above to dump resolved config
- Cribl Stream UI: verify routes/destinations exist directly in the Cribl web UI
