#!/usr/bin/env python3
"""
Check if a user exists in the database and their active status.

Usage:
    python scripts/check_user_status.py <email_or_userid>

Examples:
    python scripts/check_user_status.py john@example.com
    python scripts/check_user_status.py user_abc123
"""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import db_manager


def check_user_status(identifier: str) -> dict | None:
    """
    Check if user exists and their status.

    Args:
        identifier: Email address or userid

    Returns:
        Dict with user info or None if not found
    """
    # Try email first, then userid
    query = """
        SELECT id, userid, email, first_name, last_name, is_active, created_at, updated_at
        FROM users
        WHERE email = ? OR userid = ?
    """

    result = db_manager.execute_query(query, (identifier, identifier), fetch_one=True)

    if result:
        return dict(result)
    return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_user_status.py <email_or_userid>")
        print("Example: python scripts/check_user_status.py john@example.com")
        sys.exit(1)

    identifier = sys.argv[1]
    print(f"Checking user: {identifier}")
    print("-" * 50)

    user = check_user_status(identifier)

    if not user:
        print(f"NOT FOUND: No user with email or userid '{identifier}'")
        sys.exit(1)

    print(f"User ID:      {user['id']}")
    print(f"UserID:       {user['userid']}")
    print(f"Email:        {user['email']}")
    print(f"Name:         {user['first_name']} {user['last_name']}")
    print(f"Created:      {user['created_at']}")
    print(f"Updated:      {user['updated_at']}")
    print("-" * 50)

    if user['is_active']:
        print("STATUS: ACTIVE ✓")
    else:
        print("STATUS: INACTIVE/DISABLED ✗")
        print("  (Account was deactivated - use reactivate_user.py to restore)")


if __name__ == "__main__":
    main()
