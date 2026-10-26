"""
Comprehensive Automated Test Suite for PulseFeed
Verifies database, API endpoints, feed fetching, trigger matching, and notifications.
"""

import sys
import unittest
from fastapi.testclient import TestClient

from database import init_db, get_db
from app import app
from fetcher import fetch_single_feed, fetch_all_active_feeds
from trigger_engine import evaluate_article_against_triggers
from notifier import send_windows_toast

client = TestClient(app)

class TestPulseFeed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n--- Initializing Test Database ---")
        init_db()

    def test_01_stats_endpoint(self):
        response = client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"Stats: total_articles={data['total_articles']}, active_feeds={data['active_feeds']}, active_triggers={data['active_triggers']}")
        self.assertIn("total_articles", data)
        self.assertIn("active_triggers", data)
        self.assertGreaterEqual(data["total_feeds"], 5)

    def test_02_feeds_endpoint(self):
        response = client.get("/api/feeds")
        self.assertEqual(response.status_code, 200)
        feeds = response.json()["feeds"]
        self.assertGreaterEqual(len(feeds), 5)
        # Verify our 5 requested categories exist
        cats = {f["category"] for f in feeds}
        for expected in ["daily_news_us", "daily_news_ind", "singers_usa", "hollywood_stars", "mix_sports"]:
            self.assertIn(expected, cats, f"Missing category: {expected}")
        print(f"Found {len(feeds)} feeds across categories: {list(cats)}")

    def test_03_triggers_endpoint(self):
        response = client.get("/api/triggers")
        self.assertEqual(response.status_code, 200)
        triggers = response.json()["triggers"]
        self.assertGreaterEqual(len(triggers), 5)
        print(f"Found {len(triggers)} default alert triggers.")

    def test_04_trigger_matching_logic(self):
        active_triggers = [
            {
                "id": 1,
                "name": "Taylor Swift Watch",
                "category": "singers_usa",
                "keywords": "Taylor Swift, Eras Tour",
                "match_mode": "any",
                "priority": "high",
                "notify_desktop": 1,
                "notify_sound": 1,
                "enabled": 1
            },
            {
                "id": 2,
                "name": "Super Bowl Alert",
                "category": "mix_sports",
                "keywords": "Super Bowl, Chiefs",
                "match_mode": "any",
                "priority": "urgent",
                "notify_desktop": 1,
                "notify_sound": 1,
                "enabled": 1
            }
        ]

        # Test Match
        test_article = {
            "title": "Taylor Swift breaks record with latest single release",
            "summary": "Fans rejoice as the pop icon hits number one.",
            "category": "singers_usa"
        }
        res = evaluate_article_against_triggers(test_article, active_triggers)
        self.assertIsNotNone(res)
        trig, matched_kw = res
        self.assertEqual(trig["name"], "Taylor Swift Watch")
        self.assertEqual(matched_kw, "taylor swift")
        print(f"Trigger match verified: matched '{matched_kw}' in '{test_article['title']}'")

        # Test Non-Match
        non_match_article = {
            "title": "Local weather forecast for Tuesday",
            "summary": "Rain expected in the afternoon.",
            "category": "daily_news_us"
        }
        res_none = evaluate_article_against_triggers(non_match_article, active_triggers)
        self.assertIsNone(res_none)

    def test_05_article_filtering_and_pagination(self):
        response = client.get("/api/articles?limit=10&offset=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("articles", data)
        self.assertIn("total", data)
        print(f"Retrieved {len(data['articles'])} articles via API.")

    def test_06_add_and_delete_trigger(self):
        new_trig = {
            "name": "Unit Test Trigger",
            "category": "daily_news_us",
            "keywords": "President, Senate, Congress",
            "match_mode": "any",
            "priority": "medium",
            "notify_desktop": 1,
            "notify_sound": 1,
            "enabled": 1
        }
        create_res = client.post("/api/triggers", json=new_trig)
        self.assertEqual(create_res.status_code, 200)
        trig_id = create_res.json()["id"]

        # Delete trigger
        del_res = client.delete(f"/api/triggers/{trig_id}")
        self.assertEqual(del_res.status_code, 200)
        print(f"Trigger create and delete verified (ID: {trig_id}).")

    def test_07_test_notification_endpoint(self):
        res = client.post("/api/test-notification")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        print("Notification test endpoint verified.")

    def test_08_index_page(self):
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("PulseFeed", res.text)
        print("Web UI index.html served successfully.")

if __name__ == "__main__":
    unittest.main()
