# Operations Runbook — Cribl Framework (`crud_cribl-elk-psql`)

> Audience: on-call engineers and operators of the Cribl onboarding framework.
> Scope: the Flask portal (`app.py`), the `cribl_service` / `ece_service` / `etn_onboarding`
> microservices, their Docker deployments, and the CLI tools (`cribl-pusher.py`, `role_rm.py`).
> Companion docs: [CONSTRAINTS.md](CONSTRAINTS.md) (hard limits), [AUDIT.md](AUDIT.md)
> (coupling & credential inventory), [GIT_CLEANUP.md](GIT_CLEANUP.md) (credential rotation).

---

## 1. System map

| Service | What it is | Port (host) | Health endpoint | Depends on |
|---|---|---|---|---|
| `cribl-framework` | Flask portal + automation (`app.py`) | `127.0.0.1:5000` | `GET /cribl/health` (liveness only — see §3) | cribl_service, ece_service, etn_onboarding |
| `cribl_service` | FastAPI wrapper around the Cribl Stream API | `127.0.0.1:8001` | `GET /health` | Cribl leader |
| `ece_service` | FastAPI wrapper around Elasticsearch + Kibana | `127.0.0.1:8002` | `GET /health` | ES nonprod + prod |
| `etn_onboarding` | Flask + gunicorn onboarding state machine | `127.0.0.1:5001` (container 5000) | `GET /health` (liveness), `GET /ready` (checks DB, 503 when down) | etn_postgres |
| `etn_postgres` | Postgres 16 — hosts **two** databases: `etn_onboarding` and `cribl_framework` | `127.0.0.1:5433` | `pg_isready` | — |
| `elasticsearch` | ES 8.17.0 | `127.0.0.1:9200` | `GET /_cluster/health` | — |
| `kibana` | Kibana 8.17.0 | `127.0.0.1:5601` | `GET /api/status` | elasticsearch |
| `apm-server` | OTel/APM ingest | `127.0.0.1:8200` | — | elasticsearch, kibana |
| `cribl-edge` | Cribl Edge (managed-edge mode) | `127.0.0.1:9420` UI; 4317/4318 OTLP in `docker-compose.services.yml` | — | elasticsearch |

**Dual-path design (critical).** `app.py` calls the microservices over HTTP when
`CRIBL_SERVICE_URL` / `ECE_SERVICE_URL` / `ETN_ONBOARDING_URL` are set; when unset it
**shells out** to `cribl-pusher.py` / `role_rm.py` via subprocess. Even in HTTP mode,
catalog, health, entitlements, and offboarding make **direct** Cribl/ES calls that bypass
the microservices. When debugging, always establish which path a failing request took.

**Compose profiles:**

| File | Use | Notes |
|---|---|---|
| `docker-compose.yml` | Full stack, builds from source | All ports bound to 127.0.0.1 |
| `docker-compose.services.yml` | App services only, pre-built `:1.0.0` images | ⚠️ Binds 5000 and 9420 to `0.0.0.0`; **no Postgres** → PSQL persistence disabled |
| `docker-compose.lab.yml` | Local dev lab (Cribl leader on 9000, ES, Kibana, OTel collector) | `docker compose -f docker-compose.lab.yml up -d`, then `python app.py` locally |

---

## 2. Start / stop / smoke test

> Docker Compose procedures below; for Kubernetes/OpenShift deployments via the
> Helm chart, see §20.

```bash
# Start full stack
docker compose up -d

# Watch until healthy (cribl-framework waits for all three microservices to be healthy)
docker compose ps

# Smoke test the running stack (checks infra, health endpoints, login, portal submit, catalog)
bash lab/validate.sh

# Offline self-test of shared Cribl modules (no network, no creds; run from repo root)
python _validate.py

# Stop (keeps volumes)         # Full teardown incl. data
docker compose down            # docker compose down -v
```

`lab/validate.sh` prints `Results: N passed, N failed, N warnings` and exits 1 on any
failure. Two of its "expected" results matter for on-call: `/cribl/health/elk` returning
**503 is normal** while Logstash is removed, and `cribl_service` `GET /api/v1/worker-groups`
returning 500 is expected in the lab (no Cribl leader configured).

---

## 3. Health checks — what they actually tell you

| Endpoint | Meaning |
|---|---|
| `GET :5000/cribl/health` | **Liveness stub only.** Returns `"ok"` even when Postgres, Cribl, and ES are all down. This is what the container healthcheck probes — a "healthy" container does NOT mean dependencies work. |
| `GET :5000/cribl/health/es` | Real check: proxies ES `/_cluster/health`. 500 = ES unreachable. |
| `GET :5000/cribl/health/elk` | Composite: ES + Logstash + Kibana + OTel indices. 200 only if ALL pass, else 503. **Currently 503 is expected** because no `logstash` service is deployed (see §12). |
| `GET :5001/ready` | etn_onboarding readiness — runs `SELECT 1`; 503 `{"status":"unavailable","error":"database connection failed"}` when Postgres is down. Compose probes `/health`, not `/ready`, so a DB outage does not restart the container. |

**Rule of thumb:** to answer "is the platform actually working," use `/cribl/health/es`,
`:5001/ready`, and a catalog fetch (`GET /cribl/api/catalog`) — not `/cribl/health`.

---

## 4. Logs — where and what to grep

All services log to **stdout only** by default (no log files, no volume):

```bash
docker compose logs -f cribl-framework
docker compose logs -f cribl_service ece_service etn_onboarding
```

Optional file logging for `app.py`: set `LOG_FILE=/path/app.log` → daily-rotated
(`TimedRotatingFileHandler`, midnight, 30-day retention). `LOG_FORMAT=json` switches to
structured logs with `trace_id`/`span_id` injected. `LOG_LEVEL` controls verbosity
(default `INFO`).

Key patterns in `cribl-framework` logs:

| Pattern | Meaning |
|---|---|
| `→ POST /cribl/... [ip] user=...` | Inbound request with authenticated user |
| `← POST /cribl/... 500 1234ms` | Response; anything ≥400 is logged at WARNING |
| `subprocess: ...` / `subprocess exit code: N` | Fallback subprocess path was used (secrets masked as `***`) |
| `subprocess failed — first 500 chars:` | Subprocess stderr/stdout excerpt — the real error is here |
| `catalog — ...` (WARNING) | Catalog degraded silently (see §9) |
| `PSQL insert failed` / `PSQL status update failed` | Postgres side of a dual-write failed (see §10) |
| `Unauthorized admin access attempt by X` | Non-admin hit an admin route |

---

## 5. Troubleshooting: app won't start / crashes at boot

**Symptom: `cribl-framework` container restarts in a loop, or `python app.py` dies immediately.**

1. **`config.json` missing or invalid JSON.** Config is loaded at import
   (`_startup_config = load_config()`); the process dies before Flask binds port 5000.
   Also note `load_config()` re-reads the file on nearly every request with **no caching**
   — a bad edit to `config.json` breaks live traffic instantly, and a fix takes effect
   without restart. Validate with: `python -c "import json; json.load(open('config.json'))"`.
2. **Postgres down at startup.** `db.create_all()` runs at import inside the app context.
   If `DATABASE_URL` is set but Postgres is unreachable, the process crashes before serving.
   Check `docker compose ps etn_postgres` and `pg_isready -h 127.0.0.1 -p 5433 -U etn_user`.
   If `DATABASE_URL` is unset entirely, the app starts fine and logs
   `DATABASE_URL not set — PostgreSQL storage disabled; requests will only go to ES` — that
   is a config decision, not an error.
3. **Bind-mount gotcha:** compose mounts `./config.json` and `./elasticsearch.yml` read-only.
   If a mounted **file** does not exist on the host, Docker creates a **directory** at that
   path — Elasticsearch then fails to start with a config-read error, and the framework
   fails on `config.json` being a directory. Verify with `ls -la config.json elasticsearch.yml`
   (both must be regular files) and delete any accidentally created directories.
4. **`etn_onboarding` boot failure:** its entrypoint runs `flask db upgrade` **before**
   gunicorn on every start. A failed Alembic migration blocks startup — check
   `docker compose logs etn_onboarding` for the migration traceback.
5. **Port already in use:** something else on 5000/5001/8001/8002/9200/5433 —
   `lsof -iTCP:5000 -sTCP:LISTEN`.

---

## 6. Troubleshooting: login & portal access

| Symptom | Cause | Fix |
|---|---|---|
| Redirected to `/cribl/login` mid-session with no error | Session expired — lifetime is `auth.session_lifetime_minutes` (default 480 min / 8 h), cookie `cribl_session` | Log in again; raise the lifetime in `config.json → auth` if needed |
| 403 page after login when opening `/cribl/app` or admin APIs | Logged in as `user` role, not `admin`. Log shows `Unauthorized admin access attempt by <user>` | Use an account listed in `config.json → auth.local_admins` |
| Login succeeds with a wrong username | **Known behavior:** `POST /cribl/login` with an empty password accepts *any* username as role `user` (log: `User login (no password) OK`) | Working as coded; only admin requires a password. Treat as a finding if this reaches an untrusted network |
| `Local login failed for user=... ` in logs | Password mismatch — compared in plaintext against `config.json → auth.local_admins/local_users` | Correct the password in config (no restart needed) |

---

## 7. Troubleshooting: Cribl API failures

**First, identify the path:** if `CRIBL_SERVICE_URL` is set, most provisioning goes through
`cribl_service:8001`; catalog/offboard/destination calls still go **direct** from `app.py`.

Credential resolution priority everywhere: **CLI flag > env var > `config.json`**.
Token (`CRIBL_TOKEN`) takes priority over username/password when both are present.

| Symptom / error string | Cause | Fix |
|---|---|---|
| `Cribl login failed: 401 ...` / `[ERR] login failed: 401` on every call | Stale static `CRIBL_TOKEN` — Cribl tokens are short-lived and the framework never refreshes them | Rotate the token, or switch to `CRIBL_USERNAME`+`CRIBL_PASSWORD` (login is performed per request, so no refresh problem) |
| `No Cribl credentials: set CRIBL_TOKEN or CRIBL_USERNAME + CRIBL_PASSWORD` (500) | cribl_service has no creds in its env (`cribl_service/.env`) | Set the env vars; microservices do **not** read `config.json` |
| `CRIBL_BASE_URL env var is not set` / `No Cribl URL configured...` | Base URL not resolvable from form value / `CRIBL_SERVICE_URL` / `config.json base_url` | Set it in whichever layer the request used |
| `catalog — Cribl auth failed ws=<ws>: <code>` (WARNING) | One workspace's login failed during catalog build; catalog silently omits it | Fix that workspace's creds/URL in `config.json → workspaces` |
| HTTP **409** `Safety check failed: only N existing routes, minimum is M` or `[SAFETY] total_before=N < min=M` | Route-table safety floor tripped (`min_existing_total_routes` / `CRIBL_MIN_EXISTING_ROUTES`, default 1). Usually means the wrong worker group was targeted or the table really is empty | Verify the worker group; only if intentional, override with `CRIBL_MIN_EXISTING_ROUTES=0` |
| `[SAFETY] total_after (N) < total_before (M)` | The patch would shrink the route table — aborted | Inspect the payload; something is deleting routes it shouldn't |
| `Cannot locate routes array/group in GET response keys={...}` (500/502) | Cribl API returned an unexpected shape — typical after a Cribl upgrade. Note: Cribl `GET /routes` wraps as `{"count":N,"items":[...]}` but `PATCH` expects the **inner** object only | Check Cribl version/release notes; the shape helpers live in `cribl_api.py` |
| HTTP 500 `Internal process exited unexpectedly (code=1)` | The subprocess fallback (`cribl-pusher.py` / `role_rm.py`) called `die()` → `SystemExit`. The real reason is in the log line `subprocess failed — first 500 chars:` | Read the log; commonly missing config keys, workspace not found, or a `[SAFETY]` guard |
| Request hangs, then fails | No retries exist anywhere in `app.py`/`cribl_api.py`/`role_rm.py` — a single transient 5xx fails the operation. Timeouts: Cribl login 60 s, most Cribl calls 30 s, app→microservice 120 s | Retry manually once the transient clears; check Cribl leader load |
| `Workspace '<name>' requires explicit confirmation.` / `Aborted — ALLOW not confirmed.` | The `prod` workspace has `require_allow: true` | Pass `--allow-prod` (CLI) / confirm `ALLOW` interactively |
| CLI run hangs forever with no output | `cribl-pusher.py`/`role_rm.py` are interactive when flags are omitted and will prompt (blocked in non-tty) | Always pass `--yes` plus explicit flags in automation (the web layer always does) |

**Config change didn't take effect in Cribl:** Cribl has no filesystem watchers — config
written outside the API is ignored until the **Cribl leader process restarts** (which is
not recommended as routine). Always change config through the API paths this framework uses.

---

## 8. Troubleshooting: Elasticsearch / Kibana

| Symptom / error string | Cause | Fix |
|---|---|---|
| `/cribl/health/es` returns 500; `ES health check failed: ...` | ES unreachable from the app | `curl -u <user> http://127.0.0.1:9200/_cluster/health`; check `elasticsearch` container, disk watermark, heap |
| `strict_dynamic_mapping_exception` on submit | The index template (`elk-index-template.json`) sets `"dynamic": "strict"`, but the portal document contains many fields **not in the template** (`first_name`, `app_team`, `elk_capacity`, ...) | Extend the template with the missing keyword fields, or relax `dynamic`. This is a known template/code mismatch |
| `Request ID 'X' not found` (404) on status update, but the doc clearly exists | Two possible causes: **(a)** writes and reads target different indices — code defaults differ (`logs-cribl-onboarding-requests` in `es_index()`/status updates vs `cribl-onboarding-requests` in catalog). Fix: set `datastream.index` explicitly in `config.json`. **(b)** `_update_by_query` on a data stream requires write blocks off | For (b), run once: `PUT /logs-cribl-onboarding-requests/_settings {"index.blocks.write": false}` (documented in `elk-role.json`) |
| `Cluster [X] — read timed out after Ns` from entitlements | `fetch_role_mappings` uses (10 s connect, 120 s read) against `entitlement.clusters[]`; big role_mapping sets are slow | Check that cluster's load; the call has no retry |
| `ECE_ES_URL env var is not set` / `ECE_ES_URL_PROD is required for provisioning` (500) | ece_service env incomplete — role provisioning pushes to **both** nonprod and prod, so both URLs+creds are required | Fill `ece_service/.env` (`ECE_ES_URL`, `ECE_ES_URL_PROD`, tokens or user/pass, `ECE_KIBANA_URL`) |
| `[ELK] One or more writes failed.` with per-URL `[ERR] <url> → <status>` lines | `role_rm.push_elk` failed on at least one cluster — roles/mappings are named `R-{APP}-{ENV}-{REGION}-{TYPE}` / `RM-...` | Check the listed URL+status; re-run (the push is idempotent per role) |
| ece_service `POST /api/v1/roles/provision` "did nothing" | `dry_run` defaults to **true** on that endpoint | Pass `dry_run=false` explicitly |

---

## 9. Troubleshooting: catalog empty, stale, or missing apps

The catalog (`GET /cribl/api/catalog`) **degrades silently by design** — every build step
catches exceptions, logs at WARNING, and continues:

1. **Catalog is completely empty:** grep logs for `catalog — no apps in onboarding index`
   or `catalog — onboarding fetch failed`. Root cause is usually the onboarding index
   fetch failing (ES down, wrong `datastream.index`, auth).
2. **One workspace's routes missing:** `catalog — Cribl auth failed ws=...` — that
   workspace's creds/URL are broken; the rest of the catalog still renders.
3. **`ilm_tier` shows `none` everywhere:** the ILM fan-out (`ThreadPoolExecutor`, 10
   workers, 5 s per request, 45 s total) timed out against ES — silent degradation.
4. **A fix isn't showing up:** the catalog has a **60-second in-process cache**. Wait 60 s,
   or trigger a successful offboard / `/cribl/run` (both bust the cache), or restart.

---

## 10. Troubleshooting: portal submits & status updates (dual-write)

When `DATABASE_URL` is set, submits are **dual-written**: Postgres first, then ES. The
failure semantics are asymmetric — know them before reconciling:

| Observation | What happened | Repair |
|---|---|---|
| 500 `Failed to store request in database: ...` | Postgres insert failed → **nothing was written anywhere** (rollback ran, ES never attempted) | Fix Postgres, resubmit |
| 500 `Failed to store request: ...` | ES index failed **after Postgres committed** → orphaned `pending` row in Postgres, no ES doc | Fix ES, then either resubmit (new request_id) and delete the orphan, or manually index the doc |
| Status update returns 200 but Postgres row still `pending`; log `PSQL status update — request_id=X not found` or `PSQL status update failed` | Status updates treat ES as source of truth — Postgres failure is logged but **not returned** | Reconcile the row by hand: `UPDATE onboarding_requests SET status='done' WHERE request_id='X';` (DB `cribl_framework` on `etn_postgres`, host port 5433) |
| 502 `Onboarding service unavailable: ...` | The intake POST to `etn_onboarding` (15 s timeout) failed | Check `:5001/ready`, `docker compose logs etn_onboarding` |
| 502 `Onboarding service returned invalid response` | etn_onboarding replied without `id`/`apm_id` — often an auth mismatch surfacing oddly | Verify `ETN_ONBOARDING_TOKEN` matches the token in etn's `AUTH_LOCAL_USERS` |
| 400 with a field message (`"apmId is required."`, `"Region must be azn or azs."`, `"App Name must be a single word..."` etc.) | Client-side validation failure — not an outage | Fix the form input |

Postgres access for reconciliation:

```bash
docker compose exec etn_postgres psql -U etn_user -d cribl_framework \
  -c "SELECT request_id, apmid, status, timestamp FROM onboarding_requests ORDER BY timestamp DESC LIMIT 20;"
```

---

## 11. Troubleshooting: offboarding (`DELETE /cribl/api/catalog/<apm_id>`)

This is the **highest-risk operation** in the system. Operational rules:

1. **Always dry-run first:** `DELETE /cribl/api/catalog/<apm_id>?dry_run=true` and review
   the `actions[]` array.
2. **The HTTP status is always 200 — success is per-action.** Inspect the response body:
   each element of `actions[]` may carry an `"error"` key (`cribl_auth`,
   `cribl_routes_fetch`, `cribl_routes`, `elk_role_mappings_fetch`, `elk_role_mapping`,
   `elk_role`, `es_status_update`). A "successful" offboard can have silently failed halves.
3. **Substring matching hazard:** routes are matched by `apmid` **substring** in route
   id/name across ALL workspaces and worker groups. A short apm_id (e.g. `app1`) will
   match `app10`, `app11`, ... Verify the dry-run output lists only the intended routes.
4. Partial failure recovery: re-run the offboard (route deletion is idempotent), or clean
   up the leftover pieces manually — ES roles/mappings via
   `DELETE /_security/role_mapping/<name>` / `DELETE /_security/role/<name>`, status via
   the admin update-status endpoint.

---

## 12. Troubleshooting: `/cribl/health/elk` 503 & Logstash

**A 503 from `/cribl/health/elk` is currently EXPECTED, not an incident.** The composite
check probes `ELK_LOGSTASH_URL` (default `http://logstash:9600`), but no compose file
deploys a `logstash` service — `lab/validate.sh` explicitly asserts the 503 with the
comment "Logstash removed, health reports degraded."

Escalate only if the 503 body shows Elasticsearch, Kibana, or the OTel indices failing —
not Logstash alone. If Logstash is ever re-added, also restore the Cribl Edge outputs
that point at `logstash:5044/5045/5046`.

---

## 13. Troubleshooting: tracing / OTel

| Symptom | Cause | Fix |
|---|---|---|
| No traces anywhere, no errors either | If neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_TRACES_EXPORTER=console` is set, spans are created but **silently never exported** | Set `OTEL_EXPORTER_OTLP_ENDPOINT` (compose default: `http://apm-server:8200`; services profile: `http://cribl-edge:4318`) |
| Log line `opentelemetry-exporter-otlp-proto-http not installed; traces disabled` | Missing optional dependency | `pip install opentelemetry-exporter-otlp-proto-http` |
| Traces exported but not visible in ES | Path is OTel → APM Server / Cribl Edge → Elasticsearch; check the middle hop (`docker compose logs apm-server` or the Edge UI on :9420) | Verify `otel-*` indices: `GET /_cat/indices/otel-*` |
| JSON logs missing `trace_id` | `python-json-logger` not installed — falls back silently to plain formatting | Install it, set `LOG_FORMAT=json` |
| No metrics in ES | By design: the OTel collector config exports metrics to `debug` only; traces/logs go to ES | Expected; change `otel-collector-config.yml` if metrics persistence is needed |

---

## 14. Troubleshooting: Azure Blob delivery

The framework never talks to Azure directly — it writes `connectionString` values into
Cribl `azure_blob` destinations (`blob_dest_template_*.json`). Delivery problems are
therefore diagnosed **in Cribl**, not in this app.

| Symptom | Cause | Fix |
|---|---|---|
| Events blocked / backpressure alarms on a destination | `maxOpenFiles: 100` per destination with partitioning `apmid/logType/Y/M/D` (~5 paths/app/day). A destination shared by many apps exhausts open files; `onBackpressure: block` then stalls events | **Do not consolidate destinations** — one destination per app is the design (see [CONSTRAINTS.md](CONSTRAINTS.md)) |
| Cribl destination errors about a missing container | All templates set `createContainer: false`; containers are created **manually by the storage team** | Request the container; never flip `createContainer` |
| Auth failures on the blob destination | Bad/rotated connection string; note `blob_dest_template_azn_dev.json` ships with `AccountKey=REPLACE_ME` placeholder | Update the connection string in the template and re-push the destination |
| LGLHLD data mixed with regular retention | LGLHLD (legal hold) requires its **own container** — Azure immutability is container-scoped | Keep the dedicated `blob_dest_template_lglhld.json` destination |

---

## 15. Troubleshooting: LDAP lookup (`/cribl/portal/api/ldap-lookup`)

| Response | Meaning | Fix |
|---|---|---|
| 503 `LDAP is not configured` | `ldap.server` or `ldap.base_dn` empty in config | Fill `config.json → ldap` |
| 503 `LDAP connection failed` | Network/bind failure (connect timeout 5 s) | Check `LDAP_SERVER` reachability, bind DN/password |
| 500 on first use only | `ldap3` is imported lazily inside the handler — missing package surfaces as 500 only when the endpoint is hit | `pip install ldap3` / rebuild image |
| 200 `{"found": false}` | Lookup worked; lan_id has no entry | Not an error |

---

## 16. Rollback: Cribl route changes

Every route-table PATCH through `cribl_service` writes a snapshot **before** modifying:

- Location: `{snapshot_dir}/{table}/routes_snapshot_YYYYMMDDTHHMMSSZ.json`
  (default dir `cribl_snapshots/`, bind-mounted into the `cribl-framework` container).
- Snapshots are **skipped on dry-run**.
- ⚠️ The directory is gitignored and may be missing on a fresh checkout — if it doesn't
  exist on the host, create it before the first real push or snapshots have nowhere to land.

To roll back: take the latest snapshot for the affected table and PATCH it back via
`PATCH /api/v1/m/{worker_group}/routes/{table}` (send the **inner** routes object, not the
`{"count":N,"items":[...]}` wrapper).

---

## 17. Credential rotation

Follow the checklist in [GIT_CLEANUP.md](GIT_CLEANUP.md). Summary of what rotates and where
it lives:

| Credential | Consumed by |
|---|---|
| `CRIBL_TOKEN` (or username/password) | app.py, cribl_service, CLI tools |
| `ECE_ES_TOKEN` / `ECE_ES_PASSWORD` (nonprod + `_PROD`) | ece_service, role_rm.py |
| `ECE_KIBANA_TOKEN` / `ECE_KIBANA_PASSWORD` | ece_service |
| `ES_DATASTREAM_*` / `config.json → datastream` | app.py portal writes & catalog |
| Azure Storage connection strings | `blob_dest_template_*.json` → pushed into Cribl destinations (rotate in Azure, update templates, re-push destinations) |
| `ETN_ONBOARDING_TOKEN` | app.py → etn_onboarding (must match etn's `AUTH_LOCAL_USERS`) |
| Portal local users/admins | `config.json → auth` (plaintext; no restart needed) |

Known hygiene issues to keep in mind during rotation (from AUDIT.md): `config.json` is
tracked in git despite `.gitignore`; `docker-compose.yml` and `kibana.yml` contain
hardcoded ES/Kibana secrets; `cookies.txt` is not gitignored. Rotating a value in the
environment does not remove the old one from git history — see GIT_CLEANUP.md.

---

## 18. Reference: timeout matrix

| Call | Timeout |
|---|---|
| ES datastream writes / catalog search | 30 s (`datastream.timeout`) |
| app.py → microservices (`_svc_*`) | 120 s (hardcoded) |
| ES role_mapping fetch (entitlements) | 10 s connect / 120 s read |
| app.py → etn_onboarding intake | 15 s |
| `/cribl/health/elk` sub-checks, ILM per-request | 5 s each (ILM pool: 10 workers, 45 s total) |
| Cribl login (`cribl_api`) | 60 s |
| Cribl catalog/offboard/route calls | 30 s |
| cribl_service sync client / ece_service ES+Kibana | 60 s |
| cribl_service async client | `CRIBL_TIMEOUT` (default 30 s) |
| LDAP | 5 s connect / 10 s receive |

**Retries exist only in** `cribl_service/routers/provision.py` (3 attempts, backoff 1/3/5 s,
4xx not retried) and the `untracked_apmids` audit tool (urllib3 Retry on 429/5xx).
Everything else fails on the first error — a transient Cribl/ES 5xx during provisioning
means re-running the operation (route upserts and pack installs are idempotent:
`"status":"skipped"` / `"already_installed"`).

---

## 19. Reference: known sharp edges (summary)

- `/cribl/health` is a stub — never use it to conclude the platform is healthy (§3).
- `/cribl/health/elk` 503 is currently expected (Logstash removed) (§12).
- Catalog degrades silently and caches for 60 s (§9).
- Offboard always returns 200; check `actions[]`; substring apm_id matching can over-match (§11).
- Dual-write (Postgres+ES) has asymmetric failure semantics (§10).
- Index-name defaults differ between write and read paths — pin `datastream.index` (§8).
- ES template is `dynamic: strict` and does not include all portal fields (§8).
- `config.json` is re-read per request — malformed edits break live traffic instantly (§5).
- `docker-compose.services.yml` exposes 5000/9420 on all interfaces and disables Postgres.
- app.py runs on the Flask dev server even in containers; long calls (120 s service
  timeouts, 45 s ILM pool) can tie it up.
- TLS verification is disabled unconditionally in the entitlement/offboard ES paths.
- CI covers `etn_onboarding/` only — `app.py`, `cribl_service`, `ece_service` have no
  automated tests; `python _validate.py` is the only pre-deploy check for shared modules.
- Planned-but-not-real (from ENGINEERING_VIEW.md): `dt_service:8003`, `harness_service:8004`,
  `/healthz`, `/readyz`, `/metrics`, `STORE_BACKEND` flag — do not look for these in prod.

---

## 20. Kubernetes deployment (Helm chart)

The chart at `helm/cribl-framework/` deploys the four app services only —
Cribl Stream, ELK, and PostgreSQL are external endpoints set in values
(`external.*`). Full details in `helm/cribl-framework/README.md`.

### Deploy / upgrade / rollback

```bash
helm upgrade --install cribl helm/cribl-framework -n cribl --create-namespace -f my-values.yaml
helm test cribl -n cribl        # hook pod curls every enabled health endpoint
helm history cribl -n cribl
helm rollback cribl <REV> -n cribl
```

- **Upgrades run etn migrations first**: a `pre-upgrade` Job executes
  `flask db upgrade` before any pod is replaced. If the Job fails, the upgrade
  aborts with the old pods still running — read the Job logs:
  `kubectl -n cribl logs job/cribl-etn-onboarding-migrate`.
- **`helm rollback` does not reverse database migrations.** If a bad release
  included a schema change, additionally run `flask --app wsgi:app db downgrade`
  by hand (exec into an etn pod) before or after the rollback.
- Config/secret changes roll pods automatically (checksum annotations) —
  `helm upgrade` with only a values change is enough; no manual restarts.

### In-cluster health semantics

| Probe | Endpoint | Meaning |
|---|---|---|
| framework liveness/readiness | `/cribl/health` | Liveness stub (§3) — a Ready portal pod does NOT mean Cribl/ES/Postgres work |
| etn readiness | `/ready` | Real DB check — etn pods going NotReady = Postgres problem |
| backends | `/health` | Process-up only |

So: a fully "green" rollout with broken dependencies is possible. After deploy,
run `helm test` plus the real checks (`/cribl/health/es`, a catalog fetch).

### Kubernetes-specific troubleshooting

| Symptom | Cause / fix |
|---|---|
| Portal pod crash-loops at startup | Same causes as §5: bad `config.json` (check the mounted Secret: `kubectl get secret <release>-cribl-framework-appconfig -o jsonpath='{.data.config\.json}' \| base64 -d \| python3 -m json.tool`), or `DATABASE_URL` set but Postgres unreachable (`db.create_all()` at import) |
| Migration Job fails on first install | `external.postgres.etnDatabaseUrl` empty or DB unreachable; the `etn_onboarding` database must exist (migrations create tables, not the database) |
| etn pods NotReady, `/ready` 503 | External Postgres outage — compose hid this (its healthcheck probed `/health`), Kubernetes surfaces it correctly |
| Backend unreachable after enabling NetworkPolicy | Only this release's pods may call backends; the portal's ingress may need `networkPolicy.portalFrom` to include the router namespace (e.g. `openshift-ingress`) |
| Pod stuck `Pending` with an RWO snapshots PVC | Recreate strategy + RWO volume: old pod must terminate first; multi-replica with persistence is unsupported — keep 1 replica |
| `CreateContainerConfigError` about runAsNonRoot | Platform SCC/PSP conflict — on OpenShift restricted SCC, null out `global.podSecurityContext.runAsUser/runAsGroup/fsGroup` |
| Provisioning 500s only in cluster, works in compose | Check which path is active: `kubectl exec <portal pod> -- env \| grep SERVICE_URL` — if `criblService`/`eceService` are disabled the portal silently switches to subprocess fallback and needs creds in `config.json` |

### Logs & snapshots in cluster

```bash
kubectl -n cribl logs deploy/cribl-cribl-framework -f          # portal
kubectl -n cribl logs deploy/cribl-cribl-service -f            # Cribl wrapper
kubectl -n cribl logs job/cribl-etn-onboarding-migrate         # last migration
```

Route-rollback snapshots (§16) live in the `cribl-service` pods at
`/app/cribl_snapshots` — enable `criblService.persistence` or they are lost on
every pod restart. The PVCs carry `helm.sh/resource-policy: keep`, so they
survive `helm uninstall`.
