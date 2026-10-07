"""
fips_patch.py — Monkey-patch hashlib for FIPS-enabled environments (e.g. ARO/RHEL).

FIPS mode blocks MD5 and SHA1 unless usedforsecurity=False.
Libraries like Flask, urllib3, and OTel use these for non-security
purposes (ETags, cache keys, trace IDs) and crash on FIPS nodes.

This patch wraps hashlib so all calls default to usedforsecurity=False.

Import this module BEFORE any other imports:
    import fips_patch  # noqa: F401
"""
import hashlib
import functools


def _wrap(orig):
    @functools.wraps(orig)
    def wrapper(*args, **kwargs):
        kwargs.setdefault("usedforsecurity", False)
        return orig(*args, **kwargs)
    return wrapper


# Patch named constructors: hashlib.md5(), hashlib.sha1(), hashlib.sha256(), etc.
for _name in ("md5", "sha1", "sha224", "sha256", "sha384", "sha512"):
    _orig = getattr(hashlib, _name, None)
    if _orig is not None:
        setattr(hashlib, _name, _wrap(_orig))

# Patch hashlib.new("md5", ...)
_orig_new = hashlib.new


@functools.wraps(_orig_new)
def _patched_new(name, *args, **kwargs):
    kwargs.setdefault("usedforsecurity", False)
    return _orig_new(name, *args, **kwargs)


hashlib.new = _patched_new
