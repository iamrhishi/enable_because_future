#!/usr/bin/env python3
"""
Find duplicate or similar user accounts by email.

Usage:
    python scripts/find_duplicate_users.py <email_pattern>

Examples:
    python scripts/find_duplicate_users.py bibifuhrmann@web.de
    python scripts/find_duplicate_users.py bibi
"""

import sys
import os
from typing import Optional

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import db_manager


def find_users_by_email(pattern: str):
    """Find all users matching email pattern."""
    query = """
        SELECT id, userid, email, first_name, last_name, is_active, created_at, updated_at
        FROM users
        WHERE email LIKE ? OR email = ?
        ORDER BY created_at
    """
    return db_manager.execute_query(query, (f'%{pattern}%', pattern), fetch_all=True)


def get_user_data_summary(userid: str):
    """Get summary of data associated with a user."""
    data = {}

    # Check body measurements
    query = "SELECT COUNT(*) as count FROM body_measurements WHERE userid = ?"
    result = db_manager.execute_query(query, (userid,), fetch_one=True)
    data['body_measurements'] = result['count'] if result else 0

    # Check wardrobe items
    query = "SELECT COUNT(*) as count FROM wardrobe WHERE userid = ?"
    result = db_manager.execute_query(query, (userid,), fetch_one=True)
    data['wardrobe_items'] = result['count'] if result else 0

    # Check outfits
    query = "SELECT COUNT(*) as count FROM outfits WHERE userid = ?"
    result = db_manager.execute_query(query, (userid,), fetch_one=True)
    data['outfits'] = result['count'] if result else 0

    # Check analytics events
    query = "SELECT COUNT(*) as count FROM analytics_events WHERE user_id = ?"
    result = db_manager.execute_query(query, (userid,), fetch_one=True)
    data['analytics_events'] = result['count'] if result else 0

    return data


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/find_duplicate_users.py <email_pattern>")
        print("Example: python scripts/find_duplicate_users.py bibifuhrmann@web.de")
        sys.exit(1)

    pattern = sys.argv[1]
    print(f"Searching for users matching: {pattern}")
    print("=" * 80)

    users = find_users_by_email(pattern)

    if not users:
        print("No matching users found.")
        sys.exit(0)

    print(f"Found {len(users)} user(s):\n")

    for user in users:
        print("-" * 80)
        print(f"Database ID:  {user['id']}")
        print(f"UserID:       {user['userid']}")
        print(f"Email:        {user['email']}")
        print(f"Name:         {user['first_name']} {user['last_name']}")
        print(f"Active:       {'YES' if user['is_active'] else 'NO (deactivated)'}")
        print(f"Created:      {user['created_at']}")
        print(f"Updated:      {user['updated_at']}")

        # Get associated data
        print(f"\nAssociated Data:")
        data = get_user_data_summary(user['userid'])
        print(f"  - Body measurements: {data['body_measurements']}")
        print(f"  - Wardrobe items:    {data['wardrobe_items']}")
        print(f"  - Outfits:           {data['outfits']}")
        print(f"  - Analytics events:  {data['analytics_events']}")
        print()

    print("=" * 80)
    if len(users) > 1:
        print("WARNING: Multiple accounts found! Data may be scattered.")
    elif not users[0]['is_active']:
        print("Account is DEACTIVATED. Use reactivate_user.py to restore access.")


if __name__ == "__main__":
    main()
