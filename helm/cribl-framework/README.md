# cribl-framework Helm chart

Deploys the **application services only**:

| Component | Image (default) | Port | Default replicas | Toggle |
|---|---|---|---|---|
| Portal (`app.py`) | `cribl-framework:1.0.0` | 5000 | 1 | `framework.enabled` |
| Cribl API wrapper | `cribl-service:1.0.0` | 8001 | 2 | `criblService.enabled` |
| ES/Kibana wrapper | `ece-service:1.0.0` | 8002 | 2 | `eceService.enabled` |
| Onboarding state machine | `etn-onboarding:1.0.0` | 5000 | 2 | `etnOnboarding.enabled` |

**Deliberately NOT deployed** (external infrastructure, wired in via the
`external` values section): Cribl Stream / Edge, Elasticsearch, Kibana,
APM Server, and PostgreSQL.

## Production features

- **Non-root everywhere** — the images have no `USER` directive, so the chart
  enforces `runAsNonRoot` + UID 1000, seccomp `RuntimeDefault`, dropped
  capabilities, and no privilege escalation (`global.podSecurityContext` /
  `global.containerSecurityContext`). On OpenShift's restricted SCC, null out
  `runAsUser`/`runAsGroup`/`fsGroup` and let the platform assign the UID.
- **Zero-downtime rollouts** — RollingUpdate with `maxUnavailable: 0`
  (Recreate only when an RWO snapshots PVC is enabled), checksum annotations
  restart pods on config/secret changes, startup probes cover slow boots.
- **DB migrations as a hook Job** — `etnOnboarding.migrationJob` runs
  `flask db upgrade` once per install/upgrade and strips the migration from the
  pod entrypoint, so `etn_onboarding` scales past 1 replica safely.
- **PodDisruptionBudgets** — created automatically for any component with
  more than one replica (`maxUnavailable: 1`).
- **NetworkPolicies** (`networkPolicy.enabled`) — backends only accept traffic
  from this release's pods; portal ingress can be narrowed with
  `networkPolicy.portalFrom`.
- **Dedicated ServiceAccount** with `automountServiceAccountToken: false`
  (nothing here talks to the Kubernetes API).
- **Values validation** — `values.schema.json` rejects malformed values at
  `helm install/upgrade/lint` time.
- **`helm test`** — a hook pod curls every enabled component's health endpoint.
- **Supply-chain knobs** — per-image `digest` pinning (wins over `tag`),
  per-image `pullPolicy`, `global.imagePullSecrets`.
- **Ops passthroughs** — per-component `nodeSelector`, `tolerations`,
  `affinity`, `topologySpreadConstraints`, `podAnnotations`, `podLabels`,
  `extraEnv`; `helm.sh/resource-policy: keep` on snapshot PVCs so rollback
  data survives release deletion.

## Prerequisites

1. Build and push the four images to your registry (same images
   `docker-compose.services.yml` uses; microservice builds need the **repo
   root** as context):

   ```bash
   docker build -t <registry>/cribl-framework:1.0.0 .
   docker build -t <registry>/cribl-service:1.0.0 -f cribl_service/Dockerfile .
   docker build -t <registry>/ece-service:1.0.0 -f ece_service/Dockerfile .
   docker build -t <registry>/etn-onboarding:1.0.0 ./etn_onboarding
   ```

2. Reachable external endpoints: Cribl leader, Elasticsearch (datastream +
   nonprod/prod for role provisioning), Kibana, and PostgreSQL with the
   `cribl_framework` and `etn_onboarding` databases created (see
   `etn_onboarding/init-extra-dbs.sql` for the docker-compose equivalent —
   `etn_onboarding` migrations create their own tables via the migration Job).

## Install

```bash
helm install cribl helm/cribl-framework -n cribl --create-namespace \
  -f my-values.yaml
helm test cribl -n cribl
```

Minimal production `my-values.yaml`:

```yaml
external:
  cribl:
    baseUrl: https://cribl-leader.example.com:9000
    username: svc-cribl
    password: "..."
  elasticsearch:
    datastreamUrl: https://es.example.com:9200
    datastreamUsername: cribl_portal
    datastreamPassword: "..."
    elkEsUrl: https://es.example.com:9200
    elkKibanaUrl: https://kibana.example.com:5601
  ece:
    esUrl: https://es-nonprod.example.com:9200
    esToken: "..."
    esUrlProd: https://es-prod.example.com:9200
    esTokenProd: "..."
    kibanaUrl: https://kibana.example.com:5601
  postgres:
    frameworkDatabaseUrl: postgresql://user:pass@pg.example.com:5432/cribl_framework
    etnDatabaseUrl: postgresql://user:pass@pg.example.com:5432/etn_onboarding

framework:
  image:
    repository: registry.example.com/cribl-framework
  secretKey: "<random>"
  etnOnboardingToken: "<random>"   # kept in sync with etn_onboarding automatically
  config:
    existingSecret: cribl-app-config   # kubectl create secret generic ... --from-file=config.json
  route:
    host: cribl.apps.example.com

criblService:
  image: { repository: registry.example.com/cribl-service }
eceService:
  image: { repository: registry.example.com/ece-service }
etnOnboarding:
  image: { repository: registry.example.com/etn-onboarding }

networkPolicy:
  enabled: true
```

Prefer keeping credentials out of values files entirely: pre-create one Secret
per component (same env-var keys the chart-managed Secrets carry) and set
`<component>.existingSecret`.

## config.json for the portal

`app.py` requires `/app/config.json` at startup. Provide it either:

- pre-created: `kubectl create secret generic cribl-app-config
  --from-file=config.json` and set `framework.config.existingSecret` (preferred
  for production), or
- inline via `framework.config.content` (chart stores it in a Secret).

The shipped default only lets the pod boot — with empty `auth.local_admins`
no one can perform admin actions, and empty `workspaces`/`datastream` disable
provisioning and the catalog. Keep `datastream.index` set explicitly
(`docs/RUNBOOK.md` §8).

## Exposure

Only the portal is exposed. OpenShift: `framework.route` (enabled by default).
Vanilla Kubernetes: disable the route and enable `framework.ingress`. The three
backend services are ClusterIP-only.

## Operational notes

- `/cribl/health` (the probe target) is liveness-only — it does not verify
  Cribl/ES/Postgres. Real checks: `/cribl/health/es`, etn `/ready`
  (`docs/RUNBOOK.md` §3 and §20).
- The portal runs the Flask dev server — keep `framework.replicaCount: 1`;
  scale the FastAPI/gunicorn backends instead.
- Route-rollback snapshots: enable `criblService.persistence` (HTTP path) —
  and `framework.persistence` if the subprocess fallback is ever used. RWO
  volumes force the Recreate strategy; keep those components at 1 replica.
- Disabling `criblService`/`eceService` removes the corresponding
  `*_SERVICE_URL` from the portal env, which switches `app.py` to its
  subprocess fallback — then Cribl/ES credentials must be present in
  `config.json` instead.
- Upgrades: `helm upgrade` runs the etn migration Job first (pre-upgrade
  hook); a failed migration aborts the upgrade before any pod is replaced.
  Roll back with `helm rollback` (schema rollbacks may additionally need
  `flask db downgrade` by hand — Alembic migrations are not auto-reversed).
