#!/usr/bin/env python3
"""
Test script to diagnose avatar storage issues
This script helps verify that avatar uploads are working correctly.
"""

import mysql.connector
import base64
import requests
from PIL import Image
from io import BytesIO
import os

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'hello_db',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# API endpoint (change to your server URL)
API_BASE_URL = "http://localhost:5000"

def check_users_table():
    """Check if users table exists and has avatar column"""
    print("\n" + "="*60)
    print("1. Checking users table structure...")
    print("="*60)
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("DESCRIBE users")
        columns = cursor.fetchall()
        
        print("\nUsers table columns:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]} (Null: {col[2]}, Key: {col[3]}, Default: {col[4]})")
        
        # Check if avatar column exists
        avatar_exists = any(col[0] == 'avatar' for col in columns)
        if avatar_exists:
            print("\n✅ Avatar column exists!")
        else:
            print("\n❌ Avatar column is MISSING!")
        
        cursor.close()
        conn.close()
        return avatar_exists
        
    except Exception as e:
        print(f"\n❌ Error checking table: {e}")
        return False

def check_existing_avatars():
    """Check which users have avatars"""
    print("\n" + "="*60)
    print("2. Checking existing avatars in database...")
    print("="*60)
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT userid, email, first_name,
                   CASE WHEN avatar IS NULL THEN 'No avatar' 
                        ELSE CONCAT('Has avatar (', LENGTH(avatar), ' bytes)') 
                   END as avatar_status
            FROM users
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        users = cursor.fetchall()
        
        if users:
            print("\nRecent users:")
            for user in users:
                print(f"  - {user[0]} ({user[1]}, {user[2]}): {user[3]}")
        else:
            print("\n⚠️ No users found in database")
        
        cursor.close()
        conn.close()
        
        return len([u for u in users if 'Has avatar' in u[3]])
        
    except Exception as e:
        print(f"\n❌ Error checking avatars: {e}")
        return 0

def test_avatar_upload(user_id):
    """Test uploading an avatar via API"""
    print("\n" + "="*60)
    print(f"3. Testing avatar upload for user: {user_id}...")
    print("="*60)
    
    # Create a simple test image (100x100 red square)
    img = Image.new('RGB', (100, 100), color='red')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    print(f"\n📤 Uploading test avatar (PNG, 100x100, red square)...")
    
    try:
        # Test /api/save-avatar endpoint (multipart/form-data)
        files = {'avatar': ('test_avatar.png', buffer, 'image/png')}
        data = {'user_id': user_id}
        
        response = requests.post(
            f"{API_BASE_URL}/api/save-avatar",
            files=files,
            data=data,
            timeout=10
        )
        
        print(f"\nResponse status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        if response.status_code == 200:
            print("\n✅ Avatar upload successful!")
            return True
        else:
            print(f"\n❌ Avatar upload failed: {response.json().get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during upload: {e}")
        return False

def test_avatar_update(user_id):
    """Test updating an avatar via API (base64 method)"""
    print("\n" + "="*60)
    print(f"4. Testing avatar update (base64) for user: {user_id}...")
    print("="*60)
    
    # Create a simple test image (100x100 blue square)
    img = Image.new('RGB', (100, 100), color='blue')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Convert to base64
    avatar_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    avatar_data_url = f"data:image/png;base64,{avatar_b64}"
    
    print(f"\n📤 Updating avatar via base64 (PNG, 100x100, blue square)...")
    
    try:
        response = requests.put(
            f"{API_BASE_URL}/api/update-avatar",
            json={'user_id': user_id, 'avatar_data': avatar_data_url},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"\nResponse status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        if response.status_code == 200:
            print("\n✅ Avatar update successful!")
            return True
        else:
            print(f"\n❌ Avatar update failed: {response.json().get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during update: {e}")
        return False

def verify_avatar_in_db(user_id):
    """Verify avatar was actually saved in database"""
    print("\n" + "="*60)
    print(f"5. Verifying avatar in database for user: {user_id}...")
    print("="*60)
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT userid, email, first_name, LENGTH(avatar) as avatar_size, avatar IS NOT NULL as has_avatar
            FROM users
            WHERE userid = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if user:
            print(f"\nUser found: {user[0]} ({user[1]}, {user[2]})")
            print(f"Has avatar: {bool(user[4])}")
            print(f"Avatar size: {user[3] if user[3] else 0} bytes")
            
            if user[4] and user[3] > 0:
                print("\n✅ Avatar is stored in database!")
                return True
            else:
                print("\n❌ Avatar is NOT stored in database!")
                return False
        else:
            print(f"\n❌ User {user_id} not found!")
            return False
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error verifying avatar: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("AVATAR STORAGE DIAGNOSTIC TOOL")
    print("="*60)
    
    # Step 1: Check table structure
    if not check_users_table():
        print("\n❌ CRITICAL: users table or avatar column is missing!")
        print("   Run: mysql -u root -proot hello_db < backend/users_setup.sql")
        return
    
    # Step 2: Check existing avatars
    avatar_count = check_existing_avatars()
    print(f"\n✅ Found {avatar_count} users with avatars")
    
    # Step 3: Get user to test with
    print("\n" + "="*60)
    print("Testing with a real user...")
    print("="*60)
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT userid, email, first_name FROM users LIMIT 1")
        test_user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not test_user:
            print("\n⚠️ No users found. Please create an account first.")
            return
        
        user_id = test_user[0]
        print(f"\nTesting with user: {user_id} ({test_user[1]}, {test_user[2]})")
        
        # Step 4: Test upload
        upload_success = test_avatar_upload(user_id)
        
        # Step 5: Verify
        if upload_success:
            verify_avatar_in_db(user_id)
        
        # Step 6: Test update
        update_success = test_avatar_update(user_id)
        
        # Step 7: Verify again
        if update_success:
            verify_avatar_in_db(user_id)
        
        print("\n" + "="*60)
        print("DIAGNOSTIC COMPLETE")
        print("="*60)
        
        if upload_success and update_success:
            print("\n✅ All tests passed! Avatar storage is working correctly.")
        else:
            print("\n❌ Some tests failed. Check the logs above for details.")
            print("\nCommon issues:")
            print("  1. Flask server not running on port 5000")
            print("  2. User ID doesn't exist in database")
            print("  3. MySQL max_allowed_packet too small for large images")
            print("  4. Permission issues with MySQL user")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")

if __name__ == '__main__':
    main()
