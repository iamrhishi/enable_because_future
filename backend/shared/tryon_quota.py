"""
Per-user monthly try-on quota (Config.TRYON_MONTHLY_LIMIT, default 30/month).

Counts against a single shared pool across /tryon, /tryon/multi,
/tryon/layered and /tryon-gemini - one increment per accepted API call,
regardless of how many jobs that call creates internally (e.g. /tryon/multi
creates two tryon_jobs rows for one user action but only costs 1 quota).

Read-then-write, not a single atomic statement - same approximation used by
shared/rate_limit.py, acceptable on the single-instance deployment this runs on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from config import Config
from shared.database import db_manager
from shared.errors import QuotaExceededError
from shared.logger import logger


def _year_month(now: datetime = None) -> str:
    return (now or datetime.now()).strftime('%Y-%m')


def _is_exempt(user_id: str) -> bool:
    exempt_ids = [
        e.strip() for e in Config.TRYON_LIMIT_EXEMPT_USER_IDS.split(',') if e.strip()
    ]
    return user_id in exempt_ids


def get_tryon_usage(user_id: str) -> Dict:
    """Return current month's usage for a user: {used, limit, remaining, month}."""
    year_month = _year_month()
    limit = Config.TRYON_MONTHLY_LIMIT

    if _is_exempt(user_id):
        return {'used': 0, 'limit': limit, 'remaining': limit, 'month': year_month, 'unlimited': True}

    row = db_manager.execute_query(
        "SELECT count FROM tryon_monthly_usage WHERE user_id = ? AND year_month = ?",
        (user_id, year_month),
        fetch_one=True
    )
    used = row['count'] if row else 0
    return {
        'used': used,
        'limit': limit,
        'remaining': max(0, limit - used),
        'month': year_month,
        'unlimited': False,
    }


def check_and_increment_tryon_quota(user_id: str) -> int:
    """
    Raise QuotaExceededError if the user has hit their monthly try-on limit,
    otherwise increment usage and return the new count.

    Call this once per accepted try-on request, before any expensive work.
    """
    if _is_exempt(user_id):
        logger.info(f"tryon_quota: user_id={user_id} exempt, skipping quota check")
        return -1

    year_month = _year_month()
    limit = Config.TRYON_MONTHLY_LIMIT

    row = db_manager.execute_query(
        "SELECT count FROM tryon_monthly_usage WHERE user_id = ? AND year_month = ?",
        (user_id, year_month),
        fetch_one=True
    )
    current = row['count'] if row else 0

    if current >= limit:
        logger.info(f"tryon_quota: user_id={user_id} blocked, {current}/{limit} for {year_month}")
        raise QuotaExceededError(
            f"Monthly try-on limit reached ({limit} per month). Resets at the start of next month."
        )

    if row:
        db_manager.execute_query(
            "UPDATE tryon_monthly_usage SET count = count + 1, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id = ? AND year_month = ?",
            (user_id, year_month)
        )
    else:
        db_manager.execute_query(
            "INSERT INTO tryon_monthly_usage (user_id, year_month, count) VALUES (?, ?, 1)",
            (user_id, year_month)
        )

    return current + 1
