#!/usr/bin/env python3
"""
Migrate avatars from database BLOBs to files
This script:
1. Extracts avatar BLOBs from the database
2. Saves them as files in backend/images/avatars/{userid}/
3. Updates the users table with avatar_path field pointing to the files
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import db_manager
from shared.logger import logger


def migrate_avatars_to_files():
    """Migrate all avatar BLOBs to files"""
    print("🔄 Starting avatar migration from BLOB to files...")
    
    # Create avatars directory if it doesn't exist
    avatars_dir = Path(__file__).resolve().parent.parent / 'images' / 'avatars'
    avatars_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Avatars directory ready: {avatars_dir}")
    
    try:
        # Check if avatar_path column exists
        result = db_manager.execute_query(
            "PRAGMA table_info(users)",
            fetch_all=True
        )
        columns = [row['name'] for row in result]
        
        has_avatar_path = 'avatar_path' in columns
        has_avatar = 'avatar' in columns
        
        if not has_avatar:
            print("❌ Avatar column not found in users table")
            return False
        
        if not has_avatar_path:
            print("⚠️  avatar_path column not found. Creating it...")
            try:
                db_manager.execute_script(
                    "ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255)"
                )
                print("✅ avatar_path column added")
            except Exception as e:
                print(f"⚠️  avatar_path column might already exist: {e}")
        
        # Get all users with avatars
        users = db_manager.execute_query(
            "SELECT userid, avatar FROM users WHERE avatar IS NOT NULL",
            fetch_all=True
        )
        
        if not users:
            print("ℹ️  No avatars found in database")
            return True
        
        print(f"📦 Found {len(users)} users with avatars. Migrating...")
        
        migrated = 0
        errors = 0
        
        for user in users:
            userid = user['userid']
            avatar_blob = user['avatar']
            
            try:
                if not avatar_blob or len(avatar_blob) == 0:
                    continue
                
                # Create user-specific directory
                user_avatar_dir = avatars_dir / userid
                user_avatar_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate filename with hash of avatar data for uniqueness
                import hashlib
                avatar_hash = hashlib.md5(avatar_blob).hexdigest()[:8]
                avatar_filename = f"{userid}_{avatar_hash}.png"
                avatar_path = user_avatar_dir / avatar_filename
                
                # Save BLOB to file
                with open(avatar_path, 'wb') as f:
                    f.write(avatar_blob)
                
                # Update database with avatar_path
                relative_path = f"avatars/{userid}/{avatar_filename}"
                db_manager.execute_query(
                    "UPDATE users SET avatar_path = ? WHERE userid = ?",
                    (relative_path, userid)
                )
                
                print(f"✅ Migrated avatar for {userid}: {relative_path}")
                migrated += 1
                
            except Exception as e:
                print(f"❌ Error migrating avatar for {userid}: {str(e)}")
                logger.exception(f"Error migrating avatar for {userid}: {str(e)}")
                errors += 1
        
        print(f"\n✅ Migration complete!")
        print(f"   ✅ Successfully migrated: {migrated} avatars")
        print(f"   ❌ Errors: {errors}")
        
        if errors == 0:
            print("\n🎉 All avatars successfully migrated to files!")
            return True
        else:
            print(f"\n⚠️  {errors} avatars failed to migrate")
            return False
            
    except Exception as e:
        print(f"❌ Fatal error during migration: {str(e)}")
        logger.exception(f"Fatal error during migration: {str(e)}")
        return False


if __name__ == '__main__':
    success = migrate_avatars_to_files()
    sys.exit(0 if success else 1)
