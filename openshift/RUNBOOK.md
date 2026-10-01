# OpenShift Deployment Runbook — cribl-elk-psql

## Directory Structure

```
openshift/
├── configmap.yml                    # LOG_LEVEL, LOG_FORMAT (non-secret config)
├── secret-cribl-elk-psql.yml        # DB URLs, tokens, keys
├── services.yml                     # ClusterIP for all 4 services
├── routes.yml                       # External TLS routes (cribl-framework + etn-onboarding)
├── cribl-framework-deployment.yml   # Main orchestration API (port 5000)
├── cribl-service-deployment.yml     # Cribl Stream proxy (port 8001)
├── ece-service-deployment.yml       # Elasticsearch proxy (port 8002)
└── etn-onboarding-deployment.yml    # Onboarding state machine (port 5000)
```

## Design Decisions

- **Routes** only for `cribl-framework` and `etn-onboarding` — the two user-facing APIs. `cribl-service` and `ece-service` are internal only (ClusterIP, no route).
- **TLS edge termination** on routes — OpenShift handles SSL, pods run HTTP.
- **Health probes** match each service's existing healthcheck paths from docker-compose.
- **Service discovery** works the same as docker-compose — `http://cribl-service:8001`, `http://ece-service:8002`, etc.

## Services Overview

| Service | Port | Health Endpoint | Exposed via Route |
|---|---|---|---|
| cribl-framework | 5000 | `/cribl/health` | Yes |
| cribl-service | 8001 | `/health` | No (internal) |
| ece-service | 8002 | `/health` | No (internal) |
| etn-onboarding | 5000 | `/health` | Yes |

## Prerequisites

1. **Namespace** — create the OpenShift namespace before deploying:
   ```bash
   oc new-project appXXXXXXXX-cribl-elk-psql
   ```

2. **Image Pull Secret** — if pulling from a private Nexus Docker registry:
   ```bash
   oc create secret docker-registry nexus-pull-secret \
     --docker-server=nexus.XXXXXXXX.com:8083 \
     --docker-username=<user> \
     --docker-password=<password> \
     -n appXXXXXXXX-cribl-elk-psql

   oc secrets link default nexus-pull-secret --for=pull
   ```

3. **Secrets** — fill real values in `secret-cribl-elk-psql.yml` before applying. Never commit real credentials to git.

## Replace Before Deploying

| Placeholder | Replace With |
|---|---|
| `appXXXXXXXX-cribl-elk-psql` | Your actual OpenShift namespace |
| `nexus.XXXXXXXX.com:8083` | Your actual Nexus Docker registry URL |
| `CHANGEME` (in secret) | Actual credentials and connection strings |

## Deploy Commands

Run these in order:

```bash
# 1. Config and secrets (must exist before deployments reference them)
oc apply -f openshift/configmap.yml
oc apply -f openshift/secret-cribl-elk-psql.yml   # after filling real values

# 2. Networking (services + routes)
oc apply -f openshift/services.yml
oc apply -f openshift/routes.yml

# 3. Deployments (order matters — internal services first, then dependents)
oc apply -f openshift/cribl-service-deployment.yml
oc apply -f openshift/ece-service-deployment.yml
oc apply -f openshift/etn-onboarding-deployment.yml
oc apply -f openshift/cribl-framework-deployment.yml
```

## Verify Deployment

```bash
# Check all pods are running
oc get pods -n appXXXXXXXX-cribl-elk-psql

# Check services
oc get svc -n appXXXXXXXX-cribl-elk-psql

# Check routes (external URLs)
oc get routes -n appXXXXXXXX-cribl-elk-psql

# Test health endpoints from inside the cluster
oc exec deploy/cribl-framework -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/cribl/health').read())"
oc exec deploy/cribl-service -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8001/health').read())"
oc exec deploy/ece-service -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8002/health').read())"
oc exec deploy/etn-onboarding -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/health').read())"
```

## Troubleshooting

```bash
# Pod not starting — check events
oc describe pod <pod-name> -n appXXXXXXXX-cribl-elk-psql

# Application logs
oc logs deploy/cribl-framework -n appXXXXXXXX-cribl-elk-psql
oc logs deploy/cribl-service -n appXXXXXXXX-cribl-elk-psql
oc logs deploy/ece-service -n appXXXXXXXX-cribl-elk-psql
oc logs deploy/etn-onboarding -n appXXXXXXXX-cribl-elk-psql

# Secret not found — verify it exists
oc get secret cribl-elk-psql-secrets -n appXXXXXXXX-cribl-elk-psql

# ConfigMap not found — verify it exists
oc get configmap cribl-elk-psql-config -n appXXXXXXXX-cribl-elk-psql

# ImagePullBackOff — check registry credentials
oc get events --field-selector reason=Failed -n appXXXXXXXX-cribl-elk-psql
```

## Rollback

```bash
# Roll back a deployment to the previous revision
oc rollout undo deploy/cribl-framework -n appXXXXXXXX-cribl-elk-psql

# Check rollout history
oc rollout history deploy/cribl-framework -n appXXXXXXXX-cribl-elk-psql
```
