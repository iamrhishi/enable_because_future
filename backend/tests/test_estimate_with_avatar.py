import os
import sys
import unittest

# Add backend directory to system path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from features.auth.service import generate_token
from shared.database import db_manager

class TestEstimateWithAvatar(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.user_id = '3921f2fb'
        self.email = 'vallabhlab@gmail.com'
        self.token = generate_token(self.user_id, self.email)
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

    def test_estimate_with_avatar_success(self):
        # We know user '3921f2fb' has a saved avatar. Let's call the endpoint.
        payload = {
            'height': 180.0,
            'weight': 75.0
        }
        
        print("Sending request to /api/body-measurements/estimate-with-avatar...")
        response = self.app.post(
            '/api/body-measurements/estimate-with-avatar',
            json=payload,
            headers=self.headers
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Data: {response.get_json()}")
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('measurements', data['data'])
        self.assertIn('confidence', data['data'])
        self.assertIn('frontOverlay', data['data'])
        
        measurements = data['data']['measurements']
        self.assertEqual(measurements['height'], 180.0)
        self.assertEqual(measurements['weight'], 75.0)
        self.assertIsNotNone(measurements['shoulder_circumference'])
        self.assertIsNotNone(measurements['breast_circumference'])

    def test_estimate_with_avatar_validation_error(self):
        # Missing height/weight
        payload = {
            'height': 180.0
        }
        response = self.app.post(
            '/api/body-measurements/estimate-with-avatar',
            json=payload,
            headers=self.headers
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error_code'], 'VALIDATION_ERROR')

        # Invalid range
        payload = {
            'height': 300.0,
            'weight': 75.0
        }
        response = self.app.post(
            '/api/body-measurements/estimate-with-avatar',
            json=payload,
            headers=self.headers
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Height must be between 50 and 250 cm', data['error'])

if __name__ == '__main__':
    unittest.main()
