#!/usr/bin/env python3
"""
Reactivate a user account that was mistakenly deactivated.

Note: This only restores is_active=True. Personal data (name, address, etc.)
that was scrubbed during deactivation cannot be recovered - user must re-enter it.

Usage:
    python scripts/reactivate_user.py <email_or_userid>

Examples:
    python scripts/reactivate_user.py john@example.com
    python scripts/reactivate_user.py user_abc123
"""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import db_manager


def get_user(identifier: str) -> dict | None:
    """Get user by email or userid."""
    query = """
        SELECT id, userid, email, first_name, last_name, is_active
        FROM users
        WHERE email = ? OR userid = ?
    """
    result = db_manager.execute_query(query, (identifier, identifier), fetch_one=True)
    return dict(result) if result else None


def reactivate_user(userid: str) -> bool:
    """
    Set is_active=True for user.

    Args:
        userid: The user's userid (not email)

    Returns:
        True if updated, False otherwise
    """
    query = """
        UPDATE users
        SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
        WHERE userid = ?
    """
    db_manager.execute_query(query, (userid,))
    return True


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/reactivate_user.py <email_or_userid>")
        print("Example: python scripts/reactivate_user.py john@example.com")
        sys.exit(1)

    identifier = sys.argv[1]
    print(f"Looking up user: {identifier}")
    print("-" * 50)

    user = get_user(identifier)

    if not user:
        print(f"ERROR: No user found with email or userid '{identifier}'")
        sys.exit(1)

    print(f"Found user:")
    print(f"  UserID: {user['userid']}")
    print(f"  Email:  {user['email']}")
    print(f"  Name:   {user['first_name']} {user['last_name']}")
    print(f"  Status: {'ACTIVE' if user['is_active'] else 'INACTIVE'}")
    print("-" * 50)

    if user['is_active']:
        print("User is already active. No changes needed.")
        sys.exit(0)

    # Confirm before reactivating
    confirm = input("Reactivate this user? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("Cancelled.")
        sys.exit(0)

    reactivate_user(user['userid'])
    print(f"SUCCESS: User '{user['userid']}' has been reactivated.")
    print()
    print("Note: Personal data (name, address, etc.) scrubbed during deactivation")
    print("cannot be recovered. User will need to re-enter this information.")


if __name__ == "__main__":
    main()
