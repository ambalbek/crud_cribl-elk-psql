"""
config_resolver.py — Resolves globals in config.json.

If config.json has a "globals" section, shared values are expanded into
each service section as defaults. Section-specific values always win.

If "globals" is absent, the config is returned unchanged (backward compatible).
"""
import copy


def resolve_config(raw: dict) -> dict:
    """Expand globals into all sections. Returns a new dict — never mutates input."""
    g = raw.get("globals")
    if not g:
        return raw

    cfg = copy.deepcopy(raw)
    gl = cfg.pop("globals")

    # ── Root-level defaults ──────────────────────────────────────────────
    cfg.setdefault("log_level", gl.get("log_level", "INFO"))
    cfg.setdefault("log_format", gl.get("log_format", "text"))
    cfg.setdefault("secret_key", gl.get("secret_key", ""))
    cfg.setdefault("skip_ssl", gl.get("skip_ssl", False))
    cfg.setdefault("base_url", gl.get("cribl_url", ""))
    cfg.setdefault("cribl_service_url", gl.get("cribl_service_url", ""))
    cfg.setdefault("ece_service_url", gl.get("ece_service_url", ""))
    cfg.setdefault("etn_onboarding_url", gl.get("etn_onboarding_url", ""))

    # ── credentials ──────────────────────────────────────────────────────
    creds = cfg.setdefault("credentials", {})
    creds.setdefault("token", gl.get("cribl_token", ""))
    creds.setdefault("username", gl.get("cribl_username", ""))
    creds.setdefault("password", gl.get("cribl_password", ""))

    # ── database ─────────────────────────────────────────────────────────
    db = cfg.setdefault("database", {})
    db.setdefault("url", gl.get("database_url", ""))

    # ── datastream ───────────────────────────────────────────────────────
    ds = cfg.setdefault("datastream", {})
    ds.setdefault("elk_url", gl.get("elasticsearch_url", ""))
    ds.setdefault("token", gl.get("elasticsearch_token", ""))
    ds.setdefault("username", gl.get("elasticsearch_username", ""))
    ds.setdefault("password", gl.get("elasticsearch_password", ""))
    ds.setdefault("skip_ssl", gl.get("skip_ssl", False))
    ds.setdefault("index", "cribl-onboarding-requests")
    ds.setdefault("timeout", 30)

    # ── entitlement ──────────────────────────────────────────────────────
    ent = cfg.setdefault("entitlement", {})
    ent.setdefault("entitlementFilter", "entitlements")
    clusters = ent.setdefault("clusters", [])
    for cluster in clusters:
        cluster.setdefault("url", gl.get("elasticsearch_url", ""))
        cluster.setdefault("token", gl.get("elasticsearch_token", ""))
        cluster.setdefault("username", gl.get("elasticsearch_username", ""))
        cluster.setdefault("password", gl.get("elasticsearch_password", ""))
        cluster.setdefault("skip_ssl", gl.get("skip_ssl", False))

    # ── ece ───────────────────────────────────────────────────────────────
    ece = cfg.setdefault("ece", {})
    ece.setdefault("es_url", gl.get("elasticsearch_url", ""))
    ece.setdefault("es_token", gl.get("elasticsearch_token", ""))
    ece.setdefault("es_username", gl.get("elasticsearch_username", ""))
    ece.setdefault("es_password", gl.get("elasticsearch_password", ""))
    ece.setdefault("es_url_prod", "")
    ece.setdefault("es_token_prod", "")
    ece.setdefault("es_username_prod", "")
    ece.setdefault("es_password_prod", "")
    ece.setdefault("kibana_url", "")
    ece.setdefault("kibana_token", "")
    ece.setdefault("kibana_username", "")
    ece.setdefault("kibana_password", "")
    ece.setdefault("skip_ssl", gl.get("skip_ssl", False))
    ece.setdefault("timeout", 60)
    ece.setdefault("templates_dir", "ops_rm_r_templates_output")

    # ── etn_onboarding ───────────────────────────────────────────────────
    etn = cfg.setdefault("etn_onboarding", {})
    etn.setdefault("database_url", gl.get("database_url", ""))
    etn.setdefault("secret_key", gl.get("secret_key", ""))
    etn.setdefault("auth_backend", "local")
    etn.setdefault("cribl_service_url", gl.get("cribl_service_url", ""))
    etn.setdefault("ece_service_url", gl.get("ece_service_url", ""))
    etn.setdefault("etn_onboarding_url", gl.get("etn_onboarding_url", ""))
    etn.setdefault("token", gl.get("inter_service_token", ""))
    etn.setdefault("etn_portal_url", "")
    etn.setdefault("etn_portal_api_key", "")
    # Wire inter_service_token into auth_local_users if not explicitly set
    token = etn.get("token") or gl.get("inter_service_token", "")
    if token and "auth_local_users" not in etn:
        etn["auth_local_users"] = [
            {"username": "portal", "token": token, "roles": ["platform_admin"]}
        ]

    return cfg
