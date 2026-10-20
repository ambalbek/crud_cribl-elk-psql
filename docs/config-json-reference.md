# config.json Reference

All four services read from a single `config.json` mounted at `/app/config.json`.
In OpenShift/ARO, create it as a Kubernetes Secret:

```bash
oc create secret generic cribl-framework-appconfig \
  --from-file=config.json \
  -n <namespace>
```

## Quick Deployment Checklist

1. Copy `config.example.json` to `config.json`
2. Fill in all `CHANGE_ME` values in the `globals` section
3. Add workspace/cluster overrides as needed
4. Create the secret: `oc create secret generic cribl-framework-appconfig --from-file=config.json`
5. Apply deployments: `oc apply -f openshift/`
6. Verify pod logs show correct URLs at startup

---

## Globals Section

The `globals` section defines shared values used by all services. Each section inherits from globals — you only need to specify overrides. If `globals` is absent, the config works the old way (fully explicit).

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `log_level` | string | No | `DEBUG`, `INFO`, `WARNING`, `ERROR`. Default: `INFO` |
| `log_format` | string | No | `text` or `json`. Default: `text` |
| `skip_ssl` | boolean | No | Disable TLS verification globally. Default: `false` |
| `secret_key` | string | **Yes** | Flask session signing key. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `database_url` | string | **Yes** | PostgreSQL connection string → `database.url` + `etn_onboarding.database_url` |
| `elasticsearch_url` | string | **Yes** | ES base URL → `datastream.elk_url` + `ece.es_url` + `entitlement.clusters[].url` |
| `elasticsearch_token` | string | No | ES ApiKey → `datastream.token` + `ece.es_token` + `entitlement.clusters[].token` |
| `elasticsearch_username` | string | Yes* | ES username (*if token empty) |
| `elasticsearch_password` | string | Yes* | ES password (*if token empty) |
| `cribl_url` | string | **Yes** | Cribl Stream leader URL → `base_url`. Workspaces can override with their own `base_url` |
| `cribl_token` | string | No | Cribl bearer token → `credentials.token` |
| `cribl_username` | string | Yes* | Cribl username (*if token empty) → `credentials.username` |
| `cribl_password` | string | Yes* | Cribl password (*if token empty) → `credentials.password` |
| `cribl_service_url` | string | **Yes** | Internal cribl-service pod URL, e.g. `http://cribl-service:8001` |
| `ece_service_url` | string | **Yes** | Internal ece-service pod URL, e.g. `http://ece-service:8002` |
| `etn_onboarding_url` | string | **Yes** | Internal etn-onboarding pod URL, e.g. `http://etn-onboarding:5000` |
| `inter_service_token` | string | **Yes** | Bearer token for inter-service auth → `etn_onboarding.token` + `etn_onboarding.auth_local_users[].token` |

### How globals resolve

```
globals.elasticsearch_url  ──→  datastream.elk_url
                           ──→  ece.es_url
                           ──→  entitlement.clusters[].url

globals.cribl_url          ──→  base_url (root)

globals.database_url       ──→  database.url
                           ──→  etn_onboarding.database_url

globals.secret_key         ──→  secret_key (root)
                           ──→  etn_onboarding.secret_key

globals.skip_ssl           ──→  skip_ssl (root)
                           ──→  datastream.skip_ssl
                           ──→  ece.skip_ssl
                           ──→  entitlement.clusters[].skip_ssl
```

Section-specific values **always override** globals.

---

## Minimal config.json (with globals)

```json
{
  "globals": {
    "log_level": "INFO",
    "skip_ssl": false,
    "secret_key": "CHANGE_ME",
    "database_url": "postgresql://user:pass@postgres:5432/etn_onboarding",
    "elasticsearch_url": "https://es-host:9200",
    "elasticsearch_username": "elastic",
    "elasticsearch_password": "CHANGE_ME",
    "cribl_url": "https://cribl-stream:9000",
    "cribl_username": "admin",
    "cribl_password": "CHANGE_ME",
    "cribl_service_url": "http://cribl-service:8001",
    "ece_service_url": "http://ece-service:8002",
    "etn_onboarding_url": "http://etn-onboarding:5000",
    "inter_service_token": "CHANGE_ME"
  },
  "auth": {
    "local_admins": [{"username": "admin", "password": "CHANGE_ME", "display_name": "Admin"}]
  },
  "workspaces": {
    "dev": {
      "worker_groups": ["default"],
      "description": "Development"
    }
  },
  "entitlement": {
    "clusters": [{"name": "nonprod"}]
  }
}
```

That's it. Everything else is inherited from globals.

---

## Section Reference (overrides only)

### `auth`

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `session_lifetime_minutes` | integer | No | Session timeout. Default: `480` (8 hours) |
| `local_admins` | array | **Yes** | Admin accounts. Each: `{username, password, display_name}` |
| `local_users` | array | No | Read-only accounts. Each: `{username, password, display_name}` |

### `credentials` (auto-populated from globals)

| Key | Type | Description |
|-----|------|-------------|
| `token` | string | Cribl bearer token (from `globals.cribl_token`) |
| `username` | string | Cribl username (from `globals.cribl_username`) |
| `password` | string | Cribl password (from `globals.cribl_password`) |

### `database` (auto-populated from globals)

| Key | Type | Description |
|-----|------|-------------|
| `url` | string | PostgreSQL URL (from `globals.database_url`) |

### `datastream` (auto-populated from globals)

Only specify overrides:

| Key | Type | Description |
|-----|------|-------------|
| `index` | string | ES index name. Default: `cribl-onboarding-requests` |
| `timeout` | integer | HTTP timeout. Default: `30` |

### `entitlement`

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `clusters` | array | **Yes** | ES clusters. Each needs at least `{name}` — url/creds come from globals |
| `entitlementFilter` | string | No | DN filter. Default: `entitlements` |

**Cluster overrides** (only specify what differs from globals):

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Display name (required) |
| `url` | string | Override ES URL for this cluster |
| `token` | string | Override ES ApiKey |
| `username` | string | Override ES username |
| `password` | string | Override ES password |
| `skip_ssl` | boolean | Override SSL setting |

### `workspaces`

Each workspace key (e.g. `dev`, `prod`):

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `worker_groups` | array | **Yes** | Worker group IDs |
| `description` | string | No | UI label |
| `base_url` | string | No | Override Cribl URL for this workspace (multi-leader) |
| `username` | string | No | Override Cribl username |
| `password` | string | No | Override Cribl password |
| `token` | string | No | Override Cribl token |
| `require_allow` | boolean | No | Require typing ALLOW before writes |
| `dest_templates` | object | No | `{azn: "file.json", azs: "file.json"}` |
| `routes_table` | string | No | Route table name. Default: `default` |
| `skip_ssl` | boolean | No | Override SSL for this workspace |

### `ece` (auto-populated from globals for nonprod)

Only specify overrides:

| Key | Type | Description |
|-----|------|-------------|
| `es_url_prod` | string | Prod ES URL (if different from globals) |
| `es_token_prod` | string | Prod ES ApiKey |
| `es_username_prod` | string | Prod ES username |
| `es_password_prod` | string | Prod ES password |
| `kibana_url` | string | Kibana URL |
| `kibana_token` | string | Kibana ApiKey |
| `timeout` | integer | HTTP timeout. Default: `60` |
| `templates_dir` | string | ELK template output dir. Default: `ops_rm_r_templates_output` |

### `etn_onboarding` (auto-populated from globals)

Only specify overrides:

| Key | Type | Description |
|-----|------|-------------|
| `auth_backend` | string | Auth method. Default: `local` |
| `auth_local_users` | array | Service accounts (auto-generated from `globals.inter_service_token` if omitted) |
| `etn_portal_url` | string | External ETN portal URL |
| `etn_portal_api_key` | string | External ETN portal API key |

### `ldap`

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `server` | string | **Yes** | LDAP URL, e.g. `ldaps://ldap.corp.example.com:636` |
| `bind_dn` | string | **Yes** | Bind DN |
| `bind_pw` | string | **Yes** | Bind password |
| `base_dn` | string | **Yes** | Base DN for user search |
| `use_ssl` | boolean | No | Default: `true` |

### Other root keys

| Key | Type | Description |
|-----|------|-------------|
| `route_templates` | object | `{azn: "file.json", azs: "file.json"}` |
| `dest_prefixes` | object | `{azn: "prefix-azn", azs: "prefix-azs"}` |
| `snapshot_dir` | string | Pre-patch route snapshots dir. Default: `cribl_snapshots` |
| `min_existing_total_routes` | integer | Safety check. Default: `1` |
| `diff_lines` | integer | Context lines in diffs |
| `iiq_url` | string | IIQ portal URL (displayed in UI only) |
| `dynatrace_url` | string | Dynatrace URL (displayed in UI only) |

---

## Service-to-Config Mapping

| Service | Reads |
|---------|-------|
| **cribl-framework** | Root keys, `auth`, `credentials`, `database`, `datastream`, `entitlement`, `workspaces`, `ldap`, `etn_onboarding.token` |
| **cribl-service** | Root `base_url` + `credentials` + `skip_ssl` + `snapshot_dir` + `min_existing_total_routes` + `log_level` |
| **ece-service** | `ece` section + root `log_level` |
| **etn-onboarding** | `etn_onboarding` section |

---

## Multi-Cluster Setup

### Multiple Cribl leaders (e.g. Azure North + South)

```json
{
  "globals": {
    "cribl_url": "https://cribl-azn.com:9000",
    "cribl_username": "admin",
    "cribl_password": "CHANGE_ME"
  },
  "workspaces": {
    "dev_azn": {
      "base_url": "https://cribl-azn.com:9000",
      "worker_groups": ["wg-dev-01"],
      "description": "Dev - Azure North"
    },
    "dev_azs": {
      "base_url": "https://cribl-azs.com:9000",
      "worker_groups": ["wg-dev-01"],
      "description": "Dev - Azure South"
    }
  }
}
```

### Multiple ES clusters (nonprod + prod with different creds)

```json
{
  "globals": {
    "elasticsearch_url": "https://es-nonprod:9200",
    "elasticsearch_username": "elastic",
    "elasticsearch_password": "NONPROD_PASS"
  },
  "entitlement": {
    "clusters": [
      {"name": "nonprod"},
      {
        "name": "prod",
        "url": "https://es-prod:9200",
        "password": "PROD_PASS"
      }
    ]
  },
  "ece": {
    "es_url_prod": "https://es-prod:9200",
    "es_token_prod": "PROD_API_KEY"
  }
}
```

---

## Backward Compatibility

If `globals` is absent, config.json works exactly as before — all values must be specified explicitly in each section. The `globals` feature is opt-in.

---

## Troubleshooting

### 401 Unauthorized on catalog/destinations
- Check pod logs: `oc logs deployment/cribl-service --tail=30`
- Startup logs show `CRIBL_BASE_URL` and `CRIBL_USERNAME`
- Test from pod: `oc exec deployment/cribl-service -- curl -sk -X POST -H "Content-Type: application/json" -d '{"username":"USER","password":"PASS"}' https://CRIBL_URL:9000/api/v1/auth/login`

### Empty catalog/entitlements
- Check `CRIBL_SERVICE_URL` in cribl-framework startup logs
- Verify the database has data: `oc exec deployment/postgres -- psql -U user -d dbname -c "SELECT count(*) FROM onboarding_requests;"`

### Updating the secret
```bash
oc create secret generic cribl-framework-appconfig \
  --from-file=config.json \
  --dry-run=client -o yaml | oc apply -f -
oc rollout restart deployment/cribl-framework deployment/cribl-service deployment/ece-service deployment/etn-onboarding
```
