"""
Lightweight per-request tracking for the "API calls per website / device /
user count" section of the daily analytics report.

Fires from a global before_request hook (see app.py) on every /api/* call,
unlike shared/analytics.track_event which only fires on curated business
events (login, tryon, etc).

Platform detection:
  - The mobile app sends X-Client-Platform: mobile on every request (see
    api_client.dart) - if present, trust it.
  - Otherwise, treat the call as web. If Origin or Referer is present, its
    host is the specific retailer site the browser extension is running on;
    if neither is present, it's still web, just with an unknown site.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlparse

from flask import Request
from shared.database import db_manager
from shared.logger import logger


def _extract_host(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).netloc
        return host or None
    except Exception:
        return None


def categorize_feature(path: str, method: str = '') -> str:
    """
    Maps a request path (+ method, for the one ambiguous case) to one of
    the named feature buckets used in the drill-down report sections.
    Order matters - checked most-specific first.
    """
    p = path or ''
    m = (method or '').upper()

    if p.startswith('/api/create-account'):
        return 'signup'
    if p.startswith('/api/body-measurements'):
        return 'body_measurements'
    if (p.startswith('/api/save-avatar') or p.startswith('/api/get-avatar')
            or p.startswith('/api/update-avatar') or p.startswith('/api/avatar/')):
        return 'avatar'
    if (p.startswith('/api/tryon') or p.startswith('/api/job/')
            or p.startswith('/api/tryon-results') or p == '/api/users/tryon-status'):
        return 'tryon'
    if (p.startswith('/api/garments/scrape') or p.startswith('/api/garments/defaults')
            or p.startswith('/api/garments/refresh')
            or p.startswith('/api/wardrobe/extract-from-url')):
        return 'garment_search'
    if p.startswith('/api/garments/extract-images'):
        return 'garment_upload'
    if p.startswith('/api/wardrobe/items') and m == 'POST':
        # GET on the same path is just browsing the user's existing
        # wardrobe, not an upload - only POST (adding an item) counts.
        return 'garment_upload'
    return 'other'


def detect_platform_and_website(request: Request) -> tuple[str, Optional[str]]:
    """Returns (platform, website_domain). platform is 'mobile' or 'web'."""
    client_platform = (request.headers.get('X-Client-Platform') or '').strip().lower()
    if client_platform == 'mobile':
        return 'mobile', None

    website_domain = _extract_host(request.headers.get('Origin')) or \
        _extract_host(request.headers.get('Referer'))
    return 'web', website_domain


def log_api_call(request: Request, user_id: Optional[str] = None) -> None:
    """Best-effort log of one API call. Never raises - must not break requests."""
    try:
        platform, website_domain = detect_platform_and_website(request)
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)

        db_manager.execute_query(
            """
            INSERT INTO api_call_events (path, method, user_id, platform, website_domain, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (request.path, request.method, user_id, platform, website_domain, ip_address)
        )
    except Exception as e:
        logger.warning(f"api_call_tracking.log_api_call failed: {e}")


def get_api_call_events_since(since: datetime) -> List[Dict]:
    try:
        rows = db_manager.execute_query(
            """
            SELECT id, path, method, user_id, platform, website_domain, ip_address, created_at
            FROM api_call_events
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (since.strftime('%Y-%m-%d %H:%M:%S'),),
            fetch_all=True
        )
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"api_call_tracking.get_api_call_events_since failed: {e}")
        return []


def _user_display_names(user_ids: List[str]) -> Dict[str, str]:
    """userid -> 'First Last' (or email if no name on file). Never IP-based -
    this is the only identity lookup the feature/user drill-down uses."""
    ids = [u for u in set(user_ids) if u]
    if not ids:
        return {}
    placeholders = ','.join('?' for _ in ids)
    rows = db_manager.execute_query(
        f"SELECT userid, email, first_name, last_name FROM users WHERE userid IN ({placeholders})",
        tuple(ids), fetch_all=True
    )
    names = {}
    for row in rows:
        full_name = ' '.join(p for p in [row['first_name'], row['last_name']] if p).strip()
        names[row['userid']] = full_name or row['email'] or row['userid']
    return names


def get_api_call_summary(date: datetime = None) -> Dict:
    """
    Summary for a day: totals by platform, by website domain, unique user
    count (always by user_id/name - never by IP), plus feature drill-downs:
    by_feature, by_feature_and_platform (device), by_feature_and_user (name),
    and by_search_website (garment-search calls grouped by referring brand site).
    """
    if date is None:
        date = datetime.now() - timedelta(days=1)

    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
    start_s = start.strftime('%Y-%m-%d %H:%M:%S')
    end_s = end.strftime('%Y-%m-%d %H:%M:%S')

    summary = {
        'date': date.strftime('%Y-%m-%d'),
        'total_calls': 0,
        'by_platform': {},
        'by_website': {},
        'unique_users': 0,
        'by_feature': {},
        'by_feature_and_platform': {},
        'by_feature_and_user': {},
        'by_search_website': {},
    }

    try:
        rows = db_manager.execute_query(
            """SELECT path, method, user_id, platform, website_domain FROM api_call_events
               WHERE created_at >= ? AND created_at <= ?""",
            (start_s, end_s), fetch_all=True
        )
        rows = [dict(r) for r in rows]

        names = _user_display_names([r['user_id'] for r in rows])
        user_ids_seen = set()

        for r in rows:
            summary['total_calls'] += 1
            summary['by_platform'][r['platform']] = summary['by_platform'].get(r['platform'], 0) + 1

            if r['website_domain']:
                summary['by_website'][r['website_domain']] = summary['by_website'].get(r['website_domain'], 0) + 1

            if r['user_id']:
                user_ids_seen.add(r['user_id'])

            feature = categorize_feature(r['path'], r['method'])
            summary['by_feature'][feature] = summary['by_feature'].get(feature, 0) + 1

            by_platform_for_feature = summary['by_feature_and_platform'].setdefault(feature, {})
            by_platform_for_feature[r['platform']] = by_platform_for_feature.get(r['platform'], 0) + 1

            if r['user_id']:
                display_name = names.get(r['user_id'], r['user_id'])
                by_user_for_feature = summary['by_feature_and_user'].setdefault(feature, {})
                by_user_for_feature[display_name] = by_user_for_feature.get(display_name, 0) + 1

            if feature == 'garment_search' and r['website_domain']:
                summary['by_search_website'][r['website_domain']] = (
                    summary['by_search_website'].get(r['website_domain'], 0) + 1
                )

        summary['unique_users'] = len(user_ids_seen)

    except Exception as e:
        logger.error(f"api_call_tracking.get_api_call_summary failed: {e}")

    return summary


def delete_api_call_events_before(before: datetime) -> int:
    """Archive then delete api_call_events older than `before`. Mirrors
    shared/analytics.delete_events_before."""
    try:
        cutoff = before.strftime('%Y-%m-%d %H:%M:%S')

        count_row = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM api_call_events WHERE created_at < ?",
            (cutoff,), fetch_one=True
        )
        count = count_row['count'] if count_row else 0

        try:
            db_manager.execute_query(
                """INSERT INTO api_call_events_archive
                   (path, method, user_id, platform, website_domain, ip_address, created_at)
                   SELECT path, method, user_id, platform, website_domain, ip_address, created_at
                   FROM api_call_events WHERE created_at < ?""",
                (cutoff,)
            )
        except Exception as archive_error:
            logger.warning(f"api_call_tracking.delete_api_call_events_before: Failed to archive (continuing with wipe): {archive_error}")

        db_manager.execute_query(
            "DELETE FROM api_call_events WHERE created_at < ?",
            (cutoff,)
        )

        logger.info(f"api_call_tracking.delete_api_call_events_before: Deleted {count} events before {before}")
        return count

    except Exception as e:
        logger.error(f"api_call_tracking.delete_api_call_events_before failed: {e}")
        return 0
