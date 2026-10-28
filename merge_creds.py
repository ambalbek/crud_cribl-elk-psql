#!/usr/bin/env python3
"""Merge only credential fields from a secrets JSON into config.json.

Usage:
    echo '<secrets_json>' | python3 merge_creds.py

Reads secrets JSON from stdin, merges credential keys into /app/config.json.
Non-credential keys (log_level, skip_ssl, worker_groups, etc.) are untouched.
"""
import json
import sys

CRED_KEYS = {
    "password", "token", "secret_key", "database_url",
    "bind_pw", "bind_dn", "base_dn", "server", "username",
    "base_url", "url",
    "elasticsearch_url", "elasticsearch_token", "elasticsearch_username", "elasticsearch_password",
    "cribl_url", "cribl_token", "cribl_username", "cribl_password",
    "inter_service_token",
    "es_url", "es_token", "es_username", "es_password",
    "es_url_prod", "es_token_prod", "es_username_prod", "es_password_prod",
    "kibana_url", "kibana_token", "kibana_username", "kibana_password",
    "elk_url",
    "etn_portal_api_key",
}

# Lists that contain embedded credentials — replaced wholesale
CRED_LISTS = {"local_admins", "local_users", "auth_local_users", "clusters"}


def merge_creds(base: dict, source: dict) -> None:
    """Deep-merge only credential keys from source into base."""
    if not isinstance(source, dict) or not isinstance(base, dict):
        return
    for key, val in source.items():
        if key in CRED_KEYS:
            base[key] = val
        elif isinstance(val, dict) and isinstance(base.get(key), dict):
            merge_creds(base[key], val)
        elif isinstance(val, list) and key in CRED_LISTS:
            base[key] = val


def main():
    secrets = json.load(sys.stdin)

    with open("/app/config.json") as f:
        cfg = json.load(f)

    merge_creds(cfg, secrets)

    with open("/app/config.json", "w") as f:
        json.dump(cfg, f, indent=2)

    print("Credentials merged into config.json")


if __name__ == "__main__":
    main()
