import os
import sys
import unittest

# Add backend directory to system path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from features.auth.service import generate_token
from shared.database import db_manager
from features.body_measurements.model import BodyMeasurements

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

    @unittest.skip(
        "Integration test, not CI-safe: assumes user '3921f2fb' already exists "
        "with a real saved avatar photo a person can actually be detected in - "
        "that's real seeded data from a developer's local database, not "
        "something a schema migration alone can reproduce in a clean CI runner. "
        "Run manually against a local dev DB with that user/avatar present."
    )
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

    @unittest.skip(
        "Integration test, not CI-safe: same real-seeded-avatar dependency as "
        "test_estimate_with_avatar_success above."
    )
    def test_estimate_with_avatar_explicit_save(self):
        # 1. Fetch current measurements from database to compare
        old_measurements = BodyMeasurements.get_by_user(self.user_id)
        old_height = old_measurements.height if old_measurements else None
        
        # We will use a unique height so we can verify if it gets saved or not
        test_height = 181.0 if old_height != 181.0 else 182.0
        
        # 2. Call estimate with save=False (or omitted), check it does not save to DB
        payload = {
            'height': test_height,
            'weight': 75.0,
            'save': False
        }
        
        response = self.app.post(
            '/api/body-measurements/estimate-with-avatar',
            json=payload,
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Body measurements estimated successfully using avatar')
        
        # Verify db was NOT updated
        db_measurements = BodyMeasurements.get_by_user(self.user_id)
        if db_measurements:
            self.assertNotEqual(db_measurements.height, test_height)
            
        # 3. Call estimate with save=True, check it DOES save to DB
        payload['save'] = True
        response = self.app.post(
            '/api/body-measurements/estimate-with-avatar',
            json=payload,
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertTrue('saved' in data['message'] or 'updated' in data['message'] or 'created' in data['message'])
        
        # Verify db WAS updated
        db_measurements_after = BodyMeasurements.get_by_user(self.user_id)
        self.assertIsNotNone(db_measurements_after)
        self.assertEqual(db_measurements_after.height, test_height)

if __name__ == '__main__':
    unittest.main()
