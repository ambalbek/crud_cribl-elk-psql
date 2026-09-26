# Deploying Cribl Framework to Azure ARO via Harness IDP

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Nexus Repository Setup](#2-nexus-repository-setup)
3. [Harness Account & Project Setup](#3-harness-account--project-setup)
4. [Harness Connectors](#4-harness-connectors)
5. [Harness Service Definition](#5-harness-service-definition)
6. [Harness Environment & Infrastructure](#6-harness-environment--infrastructure)
7. [CI Pipeline — Build & Push Images](#7-ci-pipeline--build--push-images)
8. [CD Pipeline — Deploy to ARO](#8-cd-pipeline--deploy-to-aro)
9. [Helm Values Override for ARO](#9-helm-values-override-for-aro)
10. [Triggers](#10-triggers)
11. [Verification & Rollback](#11-verification--rollback)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

| Item | Details |
|------|---------|
| **Azure ARO cluster** | Running OpenShift 4.x cluster with `oc` CLI access |
| **Nexus Repository** | Docker (hosted) repository for container images |
| **Harness account** | Free tier works for initial setup |
| **Git repository** | This repo pushed to GitHub/GitLab/Bitbucket |
| **PostgreSQL** | External PostgreSQL instance accessible from ARO |
| **Cribl Stream** | External Cribl Stream leader accessible from ARO |

### ARO Namespace Setup

```bash
# Login to ARO
oc login --server=https://api.<aro-cluster>.<region>.aroapp.io:6443

# Create namespace
oc new-project cribl-framework-dev

# Create image pull secret for Nexus
oc create secret docker-registry nexus-pull-secret \
  --docker-server=<nexus-host>:<nexus-docker-port> \
  --docker-username=<nexus-user> \
  --docker-password=<nexus-password> \
  -n cribl-framework-dev
```

---

## 2. Nexus Repository Setup

### Create Docker Hosted Repository in Nexus

1. Go to **Nexus Admin > Repositories > Create Repository**
2. Select **docker (hosted)**
3. Configure:
   - **Name**: `cribl-framework`
   - **HTTP port**: `8083` (or your chosen port)
   - **Enable Docker V1 API**: unchecked
   - **Blob store**: default or dedicated

### Image Naming Convention

All four images will be pushed to Nexus:

```
<nexus-host>:<port>/cribl-framework:<tag>
<nexus-host>:<port>/cribl-service:<tag>
<nexus-host>:<port>/ece-service:<tag>
<nexus-host>:<port>/etn-onboarding:<tag>
```

Tags follow: `<branch>-<short-sha>` for dev, `v<semver>` for releases.

### Test Push Locally

```bash
# Login to Nexus Docker registry
docker login <nexus-host>:<port>

# Tag and push one image as a test
docker build -t <nexus-host>:<port>/cribl-framework:test .
docker push <nexus-host>:<port>/cribl-framework:test
```

---

## 3. Harness Account & Project Setup

### Step 1: Create a Harness Project

1. Log in to [app.harness.io](https://app.harness.io)
2. Go to **Home > Projects > + Project**
3. Fill in:
   - **Name**: `cribl-framework`
   - **Organization**: your org (or create one)
   - **Description**: Cribl onboarding framework deployment
4. Enable modules: **CI** (Continuous Integration) and **CD** (Continuous Delivery)

### Step 2: Create a Delegate in ARO

The Harness Delegate runs inside your ARO cluster and executes pipeline steps.

```bash
# In Harness UI: Project Settings > Delegates > + New Delegate
# Select "Kubernetes" and download the YAML

# Apply to ARO
oc apply -f harness-delegate.yaml -n cribl-framework-dev
```

Verify the delegate is connected:
- Harness UI > Project Settings > Delegates — status should be **Connected**

---

## 4. Harness Connectors

Create these connectors under **Project Settings > Connectors**:

### 4.1 Git Connector (Source Code)

| Field | Value |
|-------|-------|
| **Name** | `cribl-git-repo` |
| **Type** | GitHub / GitLab / Bitbucket |
| **URL** | Your repo URL |
| **Auth** | Personal Access Token or SSH key |
| **Delegate** | Select your ARO delegate |

### 4.2 Nexus Docker Registry Connector

| Field | Value |
|-------|-------|
| **Name** | `nexus-docker` |
| **Type** | Docker Registry |
| **Provider** | Other |
| **URL** | `https://<nexus-host>:<port>` |
| **Auth** | Username + Password (Nexus credentials) |
| **Delegate** | Select your ARO delegate |

### 4.3 Kubernetes / OpenShift Connector

| Field | Value |
|-------|-------|
| **Name** | `aro-dev-cluster` |
| **Type** | Kubernetes Cluster |
| **Auth** | Use Delegate running in-cluster (Inherit from Delegate) |
| **Delegate** | Select your ARO delegate |

---

## 5. Harness Service Definition

Create a **Service** under **Deployments > Services > + New Service**:

| Field | Value |
|-------|-------|
| **Name** | `cribl-framework` |
| **Type** | Kubernetes |
| **Manifest Type** | Helm Chart |
| **Helm Version** | v3 |

### Manifest Source

| Field | Value |
|-------|-------|
| **Store** | Git |
| **Connector** | `cribl-git-repo` |
| **Branch** | `main` |
| **Chart Path** | `helm/cribl-framework` |

### Artifacts (4 images)

Add each as a **Primary Artifact** or **Sidecar**:

| Artifact Name | Connector | Image Path | Tag |
|---------------|-----------|------------|-----|
| `cribl-framework` | `nexus-docker` | `cribl-framework` | `<+pipeline.stages.build.spec.execution.steps.build_push.output.outputVariables.IMAGE_TAG>` |
| `cribl-service` | `nexus-docker` | `cribl-service` | (same tag expression) |
| `ece-service` | `nexus-docker` | `ece-service` | (same tag expression) |
| `etn-onboarding` | `nexus-docker` | `etn-onboarding` | (same tag expression) |

---

## 6. Harness Environment & Infrastructure

### Create Environment

Go to **Deployments > Environments > + New Environment**:

| Field | Value |
|-------|-------|
| **Name** | `dev` |
| **Type** | Pre-Production |

### Create Infrastructure Definition

Inside the `dev` environment:

| Field | Value |
|-------|-------|
| **Name** | `aro-dev` |
| **Type** | Kubernetes |
| **Connector** | `aro-dev-cluster` |
| **Namespace** | `cribl-framework-dev` |
| **Release Name** | `cribl` |

---

## 7. CI Pipeline — Build & Push Images

Create a pipeline: **Pipelines > + Create Pipeline > Name: `cribl-ci-cd`**

### Stage 1: Build & Push (CI)

```yaml
pipeline:
  name: cribl-ci-cd
  identifier: cribl_ci_cd
  projectIdentifier: cribl_framework
  orgIdentifier: default
  stages:
    - stage:
        name: Build and Push
        identifier: build_push
        type: CI
        spec:
          cloneCodebase: true
          infrastructure:
            type: KubernetesDirect
            spec:
              connectorRef: aro_dev_cluster
              namespace: cribl-framework-dev
          execution:
            steps:
              # ── Build cribl-framework ──
              - step:
                  name: Build Framework
                  identifier: build_framework
                  type: BuildAndPushDockerRegistry
                  spec:
                    connectorRef: nexus_docker
                    repo: <nexus-host>:<port>/cribl-framework
                    tags:
                      - <+codebase.shortCommitSha>
                      - latest
                    dockerfile: Dockerfile
                    context: .

              # ── Build cribl-service ──
              - step:
                  name: Build Cribl Service
                  identifier: build_cribl_service
                  type: BuildAndPushDockerRegistry
                  spec:
                    connectorRef: nexus_docker
                    repo: <nexus-host>:<port>/cribl-service
                    tags:
                      - <+codebase.shortCommitSha>
                      - latest
                    dockerfile: cribl_service/Dockerfile
                    context: .

              # ── Build ece-service ──
              - step:
                  name: Build ECE Service
                  identifier: build_ece_service
                  type: BuildAndPushDockerRegistry
                  spec:
                    connectorRef: nexus_docker
                    repo: <nexus-host>:<port>/ece-service
                    tags:
                      - <+codebase.shortCommitSha>
                      - latest
                    dockerfile: ece_service/Dockerfile
                    context: .

              # ── Build etn-onboarding ──
              - step:
                  name: Build ETN Onboarding
                  identifier: build_etn_onboarding
                  type: BuildAndPushDockerRegistry
                  spec:
                    connectorRef: nexus_docker
                    repo: <nexus-host>:<port>/etn-onboarding
                    tags:
                      - <+codebase.shortCommitSha>
                      - latest
                    dockerfile: etn_onboarding/Dockerfile
                    context: etn_onboarding
```

> **Note**: The four build steps can run in **parallel** by grouping them under
> a `stepGroup` with `strategy: parallelism`. This cuts build time significantly.

---

## 8. CD Pipeline — Deploy to ARO

Add a second stage to the same pipeline:

### Stage 2: Deploy to Dev (CD)

```yaml
    - stage:
        name: Deploy to Dev
        identifier: deploy_dev
        type: Deployment
        spec:
          deploymentType: Kubernetes
          service:
            serviceRef: cribl_framework
          environment:
            environmentRef: dev
            infrastructureDefinitions:
              - identifier: aro_dev
          execution:
            steps:
              - step:
                  name: Helm Deploy
                  identifier: helm_deploy
                  type: HelmDeploy
                  timeout: 10m
                  spec:
                    skipDryRun: false

            rollbackSteps:
              - step:
                  name: Helm Rollback
                  identifier: helm_rollback
                  type: HelmRollback
```

### Values Override

In the **Service** manifest config, add an override values file path or inline values.
See [Section 9](#9-helm-values-override-for-aro) for the full override file.

---

## 9. Helm Values Override for ARO

Create this file as `helm/cribl-framework/values-aro-dev.yaml`:

```yaml
# ── ARO Dev Environment Values Override ──────────────────────────────────────

global:
  imagePullPolicy: Always
  imagePullSecrets:
    - name: nexus-pull-secret
  logLevel: INFO
  logFormat: json
  otlpEndpoint: ""
  # OpenShift assigns UIDs from the restricted SCC — let it manage these
  podSecurityContext:
    runAsNonRoot: true
    runAsUser: null
    runAsGroup: null
    fsGroup: null
    seccompProfile:
      type: RuntimeDefault

# ── Image Repositories (Nexus) ───────────────────────────────────────────────
# Replace <nexus-host>:<port> with your actual Nexus Docker registry address.

framework:
  enabled: true
  replicaCount: 1
  image:
    repository: <nexus-host>:<port>/cribl-framework
    tag: <+artifact.tag>   # Harness resolves this at deploy time
  secretKey: ""            # Set via Harness Secret: <+secrets.getValue("cribl_secret_key")>
  etnOnboardingToken: ""   # Set via Harness Secret: <+secrets.getValue("cribl_etn_token")>
  route:
    enabled: true
    host: cribl-framework-dev.apps.<aro-cluster>.<region>.aroapp.io
    tlsTermination: edge
  ingress:
    enabled: false
  resources:
    limits:
      cpu: "1"
      memory: 768Mi
    requests:
      cpu: 100m
      memory: 256Mi

criblService:
  enabled: true
  replicaCount: 1       # Start with 1 for dev
  image:
    repository: <nexus-host>:<port>/cribl-service
    tag: <+artifact.tag>
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 128Mi

eceService:
  enabled: true
  replicaCount: 1
  image:
    repository: <nexus-host>:<port>/ece-service
    tag: <+artifact.tag>
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 128Mi

etnOnboarding:
  enabled: true
  replicaCount: 1
  image:
    repository: <nexus-host>:<port>/etn-onboarding
    tag: <+artifact.tag>
  secretKey: ""          # Set via Harness Secret
  migrationJob:
    enabled: true
    backoffLimit: 2
    activeDeadlineSeconds: 300
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 128Mi

# ── External Services ────────────────────────────────────────────────────────
# These point to services OUTSIDE the ARO cluster (or in other namespaces).
# Use Harness Secrets for sensitive values.

external:
  cribl:
    baseUrl: ""          # e.g. https://cribl-stream.internal:9000
    token: ""
    username: ""         # Set via Harness Secret
    password: ""         # Set via Harness Secret
    skipSsl: "false"
    timeout: "30"
    defaultWorkspace: "default"
    defaultRoutesTable: "default"
    minExistingRoutes: "1"

  elasticsearch:
    datastreamUrl: ""    # e.g. https://elasticsearch.internal:9200
    datastreamUsername: ""
    datastreamPassword: ""

  ece:
    esUrl: ""
    esToken: ""
    esUsername: ""
    esPassword: ""
    esUrlProd: ""
    esTokenProd: ""
    esUsernameProd: ""
    esPasswordProd: ""
    kibanaUrl: ""
    kibanaToken: ""
    kibanaUsername: ""
    kibanaPassword: ""
    skipSsl: "false"

  postgres:
    frameworkDatabaseUrl: ""   # e.g. postgresql://user:pass@pg-host:5432/cribl_framework
    etnDatabaseUrl: ""         # e.g. postgresql://user:pass@pg-host:5432/etn_onboarding

networkPolicy:
  enabled: true
```

---

## 10. Triggers

### Auto-deploy to dev on merge to main

Go to **Pipelines > cribl-ci-cd > Triggers > + New Trigger**:

| Field | Value |
|-------|-------|
| **Name** | `on-merge-to-main` |
| **Type** | Webhook |
| **Event** | Push |
| **Connector** | `cribl-git-repo` |
| **Branch** | `main` |
| **Actions** | Closed (merged) for PR, or Push for direct commits |
| **Pipeline** | `cribl-ci-cd` |
| **Stages** | All (Build + Deploy Dev) |

### Manual promotion to higher envs (future)

When you add test/altprod/prod environments later:
- Add approval stages between environments
- Use **Manual Trigger** or **Pipeline Chaining** for promotion
- Each environment gets its own `values-aro-<env>.yaml` override

---

## 11. Verification & Rollback

### Post-Deploy Verification

Add a verification step after Helm Deploy:

```yaml
              - step:
                  name: Health Check
                  identifier: health_check
                  type: ShellScript
                  spec:
                    shell: Bash
                    source:
                      type: Inline
                      spec:
                        script: |
                          # Wait for pods to be ready
                          oc rollout status deployment/cribl-cribl-framework -n cribl-framework-dev --timeout=120s
                          oc rollout status deployment/cribl-cribl-service -n cribl-framework-dev --timeout=120s
                          oc rollout status deployment/cribl-ece-service -n cribl-framework-dev --timeout=120s
                          oc rollout status deployment/cribl-etn-onboarding -n cribl-framework-dev --timeout=120s

                          # Hit health endpoints
                          PORTAL_SVC="http://cribl-cribl-framework.cribl-framework-dev.svc:5000"
                          curl -sf "$PORTAL_SVC/cribl/health" || exit 1
                          echo "All services healthy."
```

### Automatic Rollback

The `rollbackSteps` in the CD stage automatically run `helm rollback` if:
- Helm deploy fails
- Health check step fails
- Timeout is exceeded

### Manual Rollback

```bash
# List releases
helm list -n cribl-framework-dev

# Rollback to previous revision
helm rollback cribl <revision> -n cribl-framework-dev

# Or via Harness UI: Deployments > select execution > Rollback
```

---

## 12. Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `ImagePullBackOff` | Nexus credentials wrong or secret not in namespace | Verify `nexus-pull-secret` exists in the namespace; check Nexus URL/port |
| `CrashLoopBackOff` on etn-onboarding | Database URL not set or unreachable | Check `external.postgres.etnDatabaseUrl` value |
| Migration Job fails | PostgreSQL not reachable from ARO | Ensure network path exists; check firewall rules |
| OpenShift Route 503 | Pods not ready yet | Wait for rollout; check readiness probes |
| `CRIBL_BASE_URL not set` | Missing external.cribl.baseUrl | Set it in values override or Harness Secret |
| Permission denied (SCC) | Pod security context conflicts | Set `runAsUser/runAsGroup/fsGroup` to `null` for OpenShift |

### Debug Commands

```bash
# Check pod status
oc get pods -n cribl-framework-dev

# Check events
oc get events -n cribl-framework-dev --sort-by='.lastTimestamp'

# Check logs
oc logs deployment/cribl-cribl-framework -n cribl-framework-dev
oc logs deployment/cribl-etn-onboarding -n cribl-framework-dev

# Check Helm release
helm status cribl -n cribl-framework-dev
helm get values cribl -n cribl-framework-dev

# Check migration job
oc logs job/cribl-etn-onboarding-migrate -n cribl-framework-dev

# Verify route
oc get route -n cribl-framework-dev
```

### Harness Pipeline Debug

- **Delegate issues**: Check delegate pod logs in ARO
- **Connector failures**: Test connectors in Project Settings > Connectors > Test
- **Variable resolution**: Use Harness expression evaluator in pipeline studio

---

## Quick Start Checklist

- [ ] ARO cluster accessible, `oc` CLI working
- [ ] Nexus Docker repository created and tested with manual push
- [ ] Harness project created with CI + CD modules enabled
- [ ] Harness Delegate deployed to ARO and connected
- [ ] Connectors created: Git, Nexus Docker, Kubernetes
- [ ] Service defined with Helm chart manifest + 4 artifact sources
- [ ] Environment + Infrastructure created for dev
- [ ] `values-aro-dev.yaml` configured with Nexus image repos + external service URLs
- [ ] Secrets stored in Harness: DB passwords, Cribl creds, secret keys
- [ ] Pipeline created with Build + Deploy stages
- [ ] Webhook trigger configured for auto-deploy on merge to main
- [ ] First deployment run successfully
- [ ] Health checks passing
