#!/usr/bin/env python3
"""Merge Conjur secrets into config.json by replacing "from_conjur" markers.

Usage:
    echo '<secrets_json>' | python3 merge_creds.py [config_path]

Reads the full Conjur JSON from stdin. Walks config.json recursively:
  - Any string value equal to "from_conjur" is replaced by the value at the
    same path in the Conjur JSON.
  - Any list that contains "from_conjur" anywhere is replaced wholesale.
  - Everything else stays untouched.

The config.base.json markers are the single source of truth — no hardcoded
key lists needed.
"""
import json
import os
import sys

MARKER = "from_conjur"
APP_DIR = os.getcwd()


def merge(base, source):
    """Recursively replace 'from_conjur' markers in *base* with values from *source*."""
    if not isinstance(base, dict) or not isinstance(source, dict):
        return
    for key in list(base.keys()):
        val = base[key]
        if isinstance(val, str) and MARKER in val:
            if key in source:
                base[key] = source[key]
        elif isinstance(val, dict):
            merge(val, source.get(key, {}))
        elif isinstance(val, list):
            # If the list contains MARKER anywhere (even nested), replace it
            if _list_has_marker(val) and key in source:
                base[key] = source[key]


def _list_has_marker(lst):
    """Return True if any element in the list (recursively) equals MARKER."""
    for item in lst:
        if isinstance(item, str) and item == MARKER:
            return True
        if isinstance(item, dict):
            for v in item.values():
                if isinstance(v, str) and v == MARKER:
                    return True
                if isinstance(v, list) and _list_has_marker(v):
                    return True
        if isinstance(item, list) and _list_has_marker(item):
            return True
    return False


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else f"{APP_DIR}/config.json"

    secrets = json.load(sys.stdin)

    with open(config_path) as f:
        cfg = json.load(f)

    merge(cfg, secrets)

    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)

    print("Credentials merged into config.json")


if __name__ == "__main__":
    main()
