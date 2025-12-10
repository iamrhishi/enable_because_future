#!/usr/bin/env python3
"""
Test script to verify avatar replacement functionality
Tests that a new avatar properly replaces an existing avatar in the database
"""

import mysql.connector
import requests
from PIL import Image
from io import BytesIO
import time

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'hello_db',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# API endpoint
API_BASE_URL = "http://localhost:5000"

def get_avatar_size_from_db(user_id):
    """Get avatar size directly from database"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("SELECT LENGTH(avatar) as avatar_size FROM users WHERE userid = %s", (user_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return result[0] if result and result[0] else 0
    except Exception as e:
        print(f"Error querying database: {e}")
        return None

def create_test_image(color, size=(200, 200)):
    """Create a test image with specific color and size"""
    img = Image.new('RGB', size, color=color)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

def test_avatar_replacement(user_id):
    """Test replacing an avatar multiple times"""
    print("\n" + "="*60)
    print("AVATAR REPLACEMENT TEST")
    print("="*60)
    
    # Step 1: Check initial avatar
    print(f"\n1. Checking initial avatar for user: {user_id}")
    initial_size = get_avatar_size_from_db(user_id)
    if initial_size:
        print(f"   ✅ User has existing avatar: {initial_size} bytes")
    else:
        print(f"   ℹ️ User has no avatar")
    
    # Step 2: Upload first avatar (RED)
    print(f"\n2. Uploading FIRST avatar (red, 200x200)...")
    red_img = create_test_image('red', (200, 200))
    
    files = {'avatar': ('red_avatar.png', red_img, 'image/png')}
    data = {'user_id': user_id}
    
    response = requests.post(f"{API_BASE_URL}/api/save-avatar", files=files, data=data, timeout=10)
    print(f"   Response: {response.status_code} - {response.json()}")
    
    time.sleep(0.5)  # Give DB time to write
    
    size_after_first = get_avatar_size_from_db(user_id)
    print(f"   Database check: {size_after_first} bytes")
    
    if size_after_first and size_after_first > 0:
        print(f"   ✅ First avatar uploaded successfully!")
    else:
        print(f"   ❌ First avatar NOT saved!")
        return False
    
    # Step 3: Upload second avatar (BLUE) - should REPLACE first
    print(f"\n3. Uploading SECOND avatar (blue, 300x300) to REPLACE first...")
    blue_img = create_test_image('blue', (300, 300))
    
    files = {'avatar': ('blue_avatar.png', blue_img, 'image/png')}
    data = {'user_id': user_id}
    
    response = requests.post(f"{API_BASE_URL}/api/save-avatar", files=files, data=data, timeout=10)
    print(f"   Response: {response.status_code} - {response.json()}")
    
    time.sleep(0.5)  # Give DB time to write
    
    size_after_second = get_avatar_size_from_db(user_id)
    print(f"   Database check: {size_after_second} bytes")
    
    # Verify replacement
    print(f"\n4. Verifying avatar was REPLACED...")
    print(f"   Size after first upload:  {size_after_first} bytes")
    print(f"   Size after second upload: {size_after_second} bytes")
    
    if size_after_second != size_after_first:
        print(f"   ✅ Avatar was REPLACED successfully!")
        print(f"   ✅ Size changed from {size_after_first} to {size_after_second} bytes")
        return True
    else:
        print(f"   ❌ Avatar was NOT replaced!")
        print(f"   ❌ Size remained the same: {size_after_second} bytes")
        print(f"   ❌ The new avatar did not replace the old one in the database")
        return False

def test_update_avatar_endpoint(user_id):
    """Test the /api/update-avatar endpoint (base64 method)"""
    print("\n" + "="*60)
    print("UPDATE-AVATAR ENDPOINT TEST (base64)")
    print("="*60)
    
    import base64
    
    # Step 1: Check initial avatar
    print(f"\n1. Checking initial avatar for user: {user_id}")
    initial_size = get_avatar_size_from_db(user_id)
    print(f"   Current size: {initial_size} bytes")
    
    # Step 2: Upload green avatar
    print(f"\n2. Uploading GREEN avatar (250x250) via base64...")
    green_img = create_test_image('green', (250, 250))
    green_b64 = base64.b64encode(green_img.getvalue()).decode('utf-8')
    
    response = requests.put(
        f"{API_BASE_URL}/api/update-avatar",
        json={'user_id': user_id, 'avatar_data': f"data:image/png;base64,{green_b64}"},
        headers={'Content-Type': 'application/json'},
        timeout=10
    )
    print(f"   Response: {response.status_code} - {response.json()}")
    
    time.sleep(0.5)
    
    size_after_green = get_avatar_size_from_db(user_id)
    print(f"   Database check: {size_after_green} bytes")
    
    # Step 3: Upload yellow avatar (different size)
    print(f"\n3. Uploading YELLOW avatar (350x350) to REPLACE green...")
    yellow_img = create_test_image('yellow', (350, 350))
    yellow_b64 = base64.b64encode(yellow_img.getvalue()).decode('utf-8')
    
    response = requests.put(
        f"{API_BASE_URL}/api/update-avatar",
        json={'user_id': user_id, 'avatar_data': f"data:image/png;base64,{yellow_b64}"},
        headers={'Content-Type': 'application/json'},
        timeout=10
    )
    print(f"   Response: {response.status_code} - {response.json()}")
    
    time.sleep(0.5)
    
    size_after_yellow = get_avatar_size_from_db(user_id)
    print(f"   Database check: {size_after_yellow} bytes")
    
    # Verify replacement
    print(f"\n4. Verifying avatar was REPLACED...")
    print(f"   Size after green:  {size_after_green} bytes")
    print(f"   Size after yellow: {size_after_yellow} bytes")
    
    if size_after_yellow != size_after_green:
        print(f"   ✅ Avatar was REPLACED successfully via base64!")
        return True
    else:
        print(f"   ❌ Avatar was NOT replaced via base64!")
        return False

def main():
    print("\n" + "="*60)
    print("AVATAR REPLACEMENT DIAGNOSTIC TOOL")
    print("="*60)
    
    # Get a test user
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
        
        # Test save-avatar endpoint
        result1 = test_avatar_replacement(user_id)
        
        # Test update-avatar endpoint
        result2 = test_update_avatar_endpoint(user_id)
        
        # Final summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        if result1 and result2:
            print("\n✅ ALL TESTS PASSED!")
            print("   Avatar replacement is working correctly for both endpoints.")
        else:
            print("\n❌ SOME TESTS FAILED!")
            if not result1:
                print("   ❌ /api/save-avatar - Avatar not replaced")
            if not result2:
                print("   ❌ /api/update-avatar - Avatar not replaced")
            
            print("\nPossible causes:")
            print("  1. Flask server not running")
            print("  2. Database transaction issues")
            print("  3. Frontend sending wrong user_id")
            print("  4. Caching issue in extension")
            print("  5. MySQL max_allowed_packet too small")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
