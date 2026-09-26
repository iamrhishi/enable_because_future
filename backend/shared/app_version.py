"""
Force/soft update gate. The backend is the single source of truth for which
app versions are still supported - thresholds live in Config (env vars), not
in the app itself, so they can change without a new release.
"""

from __future__ import annotations

from typing import Tuple


def _parse(version: str) -> Tuple[int, ...]:
    """'3.1.0' -> (3, 1, 0). Non-numeric/missing parts become 0."""
    parts = []
    for p in (version or '0').split('.'):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def version_lt(a: str, b: str) -> bool:
    """True if version a < version b, comparing numerically part by part."""
    pa, pb = _parse(a), _parse(b)
    length = max(len(pa), len(pb))
    pa = pa + (0,) * (length - len(pa))
    pb = pb + (0,) * (length - len(pb))
    return pa < pb


def get_update_status(client_version: str) -> str:
    """Returns 'force', 'soft', or 'none' for a given client app version string."""
    from config import Config

    if not client_version:
        return 'none'

    if version_lt(client_version, Config.APP_MIN_SUPPORTED_VERSION):
        return 'force'
    if version_lt(client_version, Config.APP_LATEST_VERSION):
        return 'soft'
    return 'none'
