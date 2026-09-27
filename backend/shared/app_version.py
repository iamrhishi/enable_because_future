"""
Force/soft update gate. The backend is the single source of truth for which
app versions are still supported - thresholds live in Config (env vars), not
in the app itself, so they can change without a new release.
"""

from __future__ import annotations

from typing import Optional, Tuple

from flask import Request


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


def get_client_build(request: Request) -> Optional[int]:
    """
    Parses X-App-Build (mobile's PackageInfo.buildNumber, sent on every
    request - see api_client.dart) as an int. None if missing or
    non-numeric, which covers every build shipped before this header
    existed - never treat None as 0, since a feature gated on "build >= N"
    must stay off for those, not just for builds below N.
    """
    raw = request.headers.get('X-App-Build')
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def is_build_gated_feature_enabled(request: Request, min_build: int) -> bool:
    """
    General mechanism for rolling out a new backend behavior only to
    builds that shipped with support for it, without waiting on a
    marketing-version bump - multiple TestFlight builds can share one
    unbumped version (Config.APP_LATEST_VERSION et al) before the next App
    Store submission forces one, so version string alone can't
    distinguish them the way the build number can.

    True only if the client sent X-App-Build and it's >= min_build.
    Missing header, non-numeric header, or a build below the threshold
    all resolve to False - the old/safe behavior, same as if this check
    didn't exist.
    """
    client_build = get_client_build(request)
    return client_build is not None and client_build >= min_build
