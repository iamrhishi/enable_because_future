"""
Automated unit and integration tests for AI-powered Conversational Garment Discovery feature.
"""

import unittest
import json
from app import app
from shared.database import db_manager
from shared.models.discovery import DiscoverySession, DiscoveryMessage
from features.garment_discovery.search_service import GarmentSearchService
from features.garment_discovery.ai_engine import ConversationalAIEngine

class TestGarmentDiscovery(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_01_search_service_scoring(self):
        """Test search service filtering and scoring logic."""
        prefs = {
            "category": "Upper body",
            "max_price": 100.0,
            "color": "Beige",
            "gender": "women"
        }
        results = GarmentSearchService.search_garments(prefs, limit=5)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        top_item = results[0]
        self.assertIn("title", top_item)
        self.assertIn("price", top_item)
        self.assertLessEqual(top_item["price"], 100.0)

    def test_02_ai_engine_rule_fallback(self):
        """Test AI engine preference extraction and dialogue turn generation."""
        user_msg = "I need a beige linen blazer under $90 for a summer wedding"
        result = ConversationalAIEngine.process_message(
            user_message=user_msg,
            history=[],
            current_preferences={},
            user_profile={"gender": "women"}
        )
        self.assertIn("extracted_preferences", result)
        extracted = result["extracted_preferences"]
        self.assertEqual(extracted.get("color"), "Beige")
        self.assertEqual(extracted.get("max_price"), 90.0)
        self.assertTrue(result.get("ready_to_search"))

    def test_03_create_and_get_session(self):
        """Test discovery session model creation, querying, and updating."""
        session = DiscoverySession.create(user_id="test_user_123", title="Wedding Outfit Search")
        self.assertIsNotNone(session.session_id)
        
        session.update_preferences({"category": "Upper body", "max_price": 150.0})
        fetched = DiscoverySession.get_by_session_id(session.session_id)
        self.assertEqual(fetched.preferences.get("max_price"), 150.0)
        
        session.delete()
        self.assertIsNone(DiscoverySession.get_by_session_id(session.session_id))

    def test_04_api_create_session_endpoint(self):
        """Test POST /api/garment-discovery/sessions endpoint."""
        response = self.client.post(
            '/api/garment-discovery/sessions',
            json={"user_id": "test_user_api", "title": "API Test Session"}
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("session", data)
        session_id = data["session"]["session_id"]
        
        # Cleanup
        s = DiscoverySession.get_by_session_id(session_id)
        if s:
            s.delete()

    def test_05_api_chat_flow(self):
        """Test complete conversational turn flow via POST /api/garment-discovery/chat."""
        # Turn 1
        resp1 = self.client.post(
            '/api/garment-discovery/chat',
            json={
                "user_id": "test_user_chat",
                "message": "I am looking for a white shirt under $50 for beach vacation"
            }
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.get_json()
        self.assertTrue(data1.get("success"))
        session_id = data1.get("session_id")
        self.assertIsNotNone(session_id)
        self.assertIn("garments", data1)
        self.assertGreater(len(data1["garments"]), 0)

        # Turn 2: Refinement turn
        resp2 = self.client.post(
            '/api/garment-discovery/chat',
            json={
                "session_id": session_id,
                "message": "Show me cheaper options instead"
            }
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertTrue(data2.get("success"))
        self.assertEqual(data2.get("session_id"), session_id)

        # Cleanup
        s = DiscoverySession.get_by_session_id(session_id)
        if s:
            s.delete()

    def test_06_user_screenshot_flow(self):
        """Test exact conversation flow from user screenshot: 'black clothes' -> 'blazer' -> 'different_color'."""
        # Turn 1: "show me some black clothes"
        resp1 = self.client.post(
            '/api/garment-discovery/chat',
            json={"user_id": "test_flow", "message": "show me some black clothes"}
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.get_json()
        session_id = data1["session_id"]
        self.assertEqual(data1["preferences"].get("color"), "Black")

        # Turn 2: "blazer"
        resp2 = self.client.post(
            '/api/garment-discovery/chat',
            json={"session_id": session_id, "message": "blazer"}
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        garments2 = data2["garments"]
        self.assertGreater(len(garments2), 0)
        # All returned garments must be Blazers / Suit Jackets in Black
        for item in garments2:
            title_and_sub = (item["title"] + " " + item.get("subcategory", "")).lower()
            self.assertTrue("blazer" in title_and_sub or "suit" in title_and_sub or "jacket" in title_and_sub)
            self.assertEqual(item["color"], "Black")

        # Turn 3: Refine different_color
        resp3 = self.client.post(
            '/api/garment-discovery/refine',
            json={"session_id": session_id, "refinement_type": "different_color"}
        )
        self.assertEqual(resp3.status_code, 200)
        data3 = resp3.get_json()
        garments3 = data3["garments"]
        self.assertGreater(len(garments3), 0)
        # All returned garments must be Blazers / Suit Jackets in colors OTHER than Black
        for item in garments3:
            title_and_sub = (item["title"] + " " + item.get("subcategory", "")).lower()
            self.assertTrue("blazer" in title_and_sub or "suit" in title_and_sub or "jacket" in title_and_sub)
            self.assertNotEqual(item["color"], "Black")

        # Cleanup
        s = DiscoverySession.get_by_session_id(session_id)
        if s:
            s.delete()

    def test_07_blue_trousers_query(self):
        """Test that searching for 'Blue Trousers' strictly returns trousers/chinos/jeans in blue/navy, NEVER blazers."""
        resp = self.client.post(
            '/api/garment-discovery/chat',
            json={"user_id": "test_blue_trousers", "message": "Blue Trousers"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        garments = data.get("garments", [])
        self.assertGreater(len(garments), 0)
        for item in garments:
            title_and_sub = (item["title"] + " " + item.get("subcategory", "")).lower()
            # Must be trousers/pants/chinos/jeans, NEVER blazer
            self.assertFalse("blazer" in title_and_sub and "trouser" not in title_and_sub)
            self.assertTrue("trouser" in title_and_sub or "pant" in title_and_sub or "chino" in title_and_sub or "jean" in title_and_sub)

    def test_08_single_keyword_queries(self):
        """Test that single-keyword queries ('zara', 'under $50', 'casual outfit', 'party dress', 'men') ALWAYS return results."""
        keywords = ["zara", "under $50", "casual outfit", "party dress", "men"]
        for kw in keywords:
            resp = self.client.post(
                '/api/garment-discovery/chat',
                json={"user_id": "test_kw", "message": kw}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("success"), f"Failed for keyword: {kw}")
            garments = data.get("garments", [])
            print(f"\n[Test08] Keyword: '{kw}' | Returned {len(garments)} garments:")
            for idx, g in enumerate(garments[:3]):
                print(f"  {idx+1}. {g.get('title')} - {g.get('brand')} - {g.get('price')}")
            self.assertGreater(len(garments), 0, f"No garments returned for keyword: {kw}")

    def test_09_yellow_shirt_query(self):
        """Test that searching for 'yellow shirt' returns Yellow Shirts with yellow photos and no duplicates."""
        resp = self.client.post(
            '/api/garment-discovery/chat',
            json={"user_id": "test_yellow", "message": "i am looking for a yellow shirt"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        garments = data.get("garments", [])
        self.assertGreater(len(garments), 0)
        top_item = garments[0]
        self.assertEqual(top_item["color"], "Yellow")
        valid_words = ["shirt", "top", "blouse", "tee", "t-shirt", "polo", "apparel", "button", "wear"]
        self.assertTrue(any(w in top_item["title"].lower() for w in valid_words), f"Title '{top_item['title']}' did not contain expected garment words.")
        # Check no exact duplicates returned
        titles = [g["title"] for g in garments]
        self.assertEqual(len(titles), len(set(titles)))

    def test_10_zara_internal_search_fallback(self):
        """Test that Option 1 Zara search handles queries safely."""
        prefs = {"brand": "Zara", "color": "red"}
        results = GarmentSearchService._search_zara_internal("red dress", prefs)
        # Should return a list (empty if the mock fails or returns nothing, which triggers fallback)
        self.assertIsInstance(results, list)

    def test_11_duckduckgo_api_search(self):
        """Test that Option 2 DuckDuckGo API search returns valid results for a generic query."""
        prefs = {"brand": "H&M", "color": "blue"}
        results = GarmentSearchService._search_duckduckgo_api("blue shirt site:hm.com", "H&M", prefs)
        self.assertIsInstance(results, list)
        if len(results) > 0:
            top_item = results[0]
            self.assertIn("title", top_item)
            self.assertIn("url", top_item)
            self.assertTrue(top_item["url"].startswith("http"))

if __name__ == '__main__':
    unittest.main()
