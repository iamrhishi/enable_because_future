#!/usr/bin/env python3
"""
Check user activity history from analytics events.

Usage:
    python scripts/check_user_history.py <email_or_userid>
"""

import sys
import os
import json
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import db_manager


def get_user(identifier: str) -> Optional[dict]:
    """Get user by email or userid."""
    query = """
        SELECT userid, email, first_name, last_name, is_active, created_at
        FROM users
        WHERE email = ? OR userid = ?
    """
    result = db_manager.execute_query(query, (identifier, identifier), fetch_one=True)
    return dict(result) if result else None


def get_analytics_events(userid: str):
    """Get all analytics events for user."""
    query = """
        SELECT event_type, metadata, ip_address, user_agent, created_at
        FROM analytics_events
        WHERE user_id = ?
        ORDER BY created_at DESC
    """
    return db_manager.execute_query(query, (userid,), fetch_all=True)


def get_analytics_by_email(email: str):
    """Get analytics events by email (for failed logins etc)."""
    query = """
        SELECT event_type, user_id, metadata, created_at
        FROM analytics_events
        WHERE user_email = ?
        ORDER BY created_at DESC
    """
    return db_manager.execute_query(query, (email,), fetch_all=True)


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_user_history.py <email_or_userid>")
        sys.exit(1)

    identifier = sys.argv[1]

    user = get_user(identifier)
    if not user:
        print(f"User not found: {identifier}")
        sys.exit(1)

    print(f"User: {user['email']} ({user['userid']})")
    print(f"Name: {user['first_name']} {user['last_name']}")
    print(f"Created: {user['created_at']}")
    print("=" * 80)

    # Get events by userid
    events = get_analytics_events(user['userid'])

    # Also check by email
    email_events = get_analytics_by_email(user['email'])

    all_events = list(events) + [e for e in email_events if e not in events]

    if not all_events:
        print("No analytics events found for this user.")
        print("\nNote: Analytics events are wiped daily after reporting.")
        print("Older activity data is not recoverable from analytics_events.")
        sys.exit(0)

    print(f"Found {len(all_events)} analytics event(s):\n")

    for event in all_events:
        print("-" * 60)
        print(f"Event:     {event['event_type']}")
        print(f"Time:      {event['created_at']}")

        if event.get('metadata'):
            try:
                meta = json.loads(event['metadata']) if isinstance(event['metadata'], str) else event['metadata']
                print(f"Metadata:  {json.dumps(meta, indent=2)}")
            except:
                print(f"Metadata:  {event['metadata']}")

        if event.get('ip_address'):
            print(f"IP:        {event['ip_address']}")
        if event.get('user_agent'):
            ua = event['user_agent'][:80] + '...' if len(event.get('user_agent', '')) > 80 else event.get('user_agent', '')
            print(f"UA:        {ua}")

    print("\n" + "=" * 80)
    print("Note: Analytics events are wiped daily. This shows only recent activity.")
    print("Deleted wardrobe items cannot be recovered - no backup/history table exists.")


if __name__ == "__main__":
    main()
