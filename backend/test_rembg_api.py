#!/usr/bin/env python3
"""
Test script for /api/remove-bg-rembg endpoint
This tests the new rembg-based background removal API
"""

import requests
import sys
from pathlib import Path

def test_rembg_api(image_path, output_path="output_no_bg.png"):
    """
    Test the /api/remove-bg-rembg endpoint
    
    Args:
        image_path: Path to input image file
        output_path: Path to save the output PNG with transparent background
    """
    url = "http://localhost:5000/api/remove-bg-rembg"
    
    print(f"🧪 Testing /api/remove-bg-rembg")
    print(f"📁 Input image: {image_path}")
    print(f"📁 Output will be saved to: {output_path}")
    print()
    
    # Check if file exists
    if not Path(image_path).exists():
        print(f"❌ Error: File not found: {image_path}")
        return False
    
    try:
        # Prepare the request
        with open(image_path, 'rb') as f:
            files = {'image': f}
            
            print("🚀 Sending request to API...")
            response = requests.post(url, files=files, timeout=60)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📊 Response headers:")
        for key, value in response.headers.items():
            if key.startswith('X-'):
                print(f"   {key}: {value}")
        print()
        
        if response.status_code == 200:
            # Save the output image
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Success! Background removed")
            print(f"📁 Output saved to: {output_path}")
            print(f"📏 Output size: {len(response.content)} bytes")
            return True
        else:
            print(f"❌ Error: API returned status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Message: {error_data.get('message', 'No message')}")
                print(f"   Code: {error_data.get('code', 'No code')}")
            except:
                print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server. Is it running on localhost:5000?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_rembg_api.py <image_path> [output_path]")
        print()
        print("Example:")
        print("  python test_rembg_api.py person.jpg")
        print("  python test_rembg_api.py person.jpg no_bg.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "output_no_bg.png"
    
    success = test_rembg_api(image_path, output_path)
    sys.exit(0 if success else 1)
