"""
PulseFeed RSS/Atom Feed Ingestion Engine
Fetches, sanitizes, deduplicates articles, stores them in SQLite,
and dispatches them to the Trigger Engine.
"""

import time
import re
import html
import calendar
import urllib.request
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import feedparser

from database import get_db, generate_guid_hash
from trigger_engine import process_new_articles_for_triggers

logger = logging.getLogger("pulsefeed.fetcher")


def clean_html(raw_html: Optional[str]) -> str:
    """Removes HTML tags and decodes HTML entities."""
    if not raw_html:
        return ""
    # Remove script and style tags completely
    cleaned = re.sub(r'<script.*?</script>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<style.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    # Remove remaining HTML tags
    cleaned = re.sub(r'<[^<]+?>', '', cleaned)
    # Unescape HTML entities
    cleaned = html.unescape(cleaned)
    # Normalize whitespaces
    return " ".join(cleaned.split()).strip()


def parse_date_to_iso(entry: Any) -> str:
    """Extracts published or updated date as ISO string in UTC."""
    parsed_time = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed_time:
        try:
            epoch = calendar.timegm(parsed_time)
            dt = datetime.fromtimestamp(epoch, timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat()


def fetch_single_feed(feed_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetches and parses a single RSS feed.
    Returns status dict with new articles count and errors.
    """
    feed_id = feed_record["id"]
    feed_url = feed_record["url"]
    category = feed_record["category"]
    feed_name = feed_record["name"]

    now_iso = datetime.now(timezone.utc).isoformat()
    new_articles = []

    try:
        req = urllib.request.Request(
            feed_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PulseFeed/1.0",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read()

        parsed = feedparser.parse(content)

        if not parsed.entries and parsed.bozo and parsed.bozo_exception:
            raise Exception(str(parsed.bozo_exception))

        conn = get_db()
        cursor = conn.cursor()

        for entry in parsed.entries:
            title = clean_html(getattr(entry, "title", "Untitled"))
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue

            # Summary cleanup
            raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            summary = clean_html(raw_summary)

            author = getattr(entry, "author", "") or feed_name
            published_at = parse_date_to_iso(entry)
            guid_hash = generate_guid_hash(link, title)

            # Check if article already exists
            cursor.execute("SELECT id FROM articles WHERE guid_hash = ?", (guid_hash,))
            existing = cursor.fetchone()

            if not existing:
                cursor.execute("""
                    INSERT INTO articles (
                        guid_hash, feed_id, category, title, summary, link, author,
                        published_at, fetched_at, is_read, is_starred, has_alert
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
                """, (
                    guid_hash, feed_id, category, title, summary, link,
                    author, published_at, now_iso
                ))
                new_art_id = cursor.lastrowid
                new_articles.append({
                    "id": new_art_id,
                    "guid_hash": guid_hash,
                    "feed_id": feed_id,
                    "category": category,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "author": author,
                    "published_at": published_at
                })

        # Count total articles for this feed
        cursor.execute("SELECT COUNT(*) FROM articles WHERE feed_id = ?", (feed_id,))
        total_for_feed = cursor.fetchone()[0]

        # Update feed record status
        cursor.execute("""
            UPDATE feeds
            SET last_checked = ?, last_status = 'OK', error_message = NULL, article_count = ?
            WHERE id = ?
        """, (now_iso, total_for_feed, feed_id))

        conn.commit()
        conn.close()

        # Run trigger evaluation on new articles
        triggered_alerts = []
        if new_articles:
            triggered_alerts = process_new_articles_for_triggers(new_articles)
            # Instantly push real-time events to connected dashboards
            try:
                from app import broadcast_event_sync
                for alert in triggered_alerts:
                    broadcast_event_sync("alert", alert)
                broadcast_event_sync("new_articles", {
                    "count": len(new_articles),
                    "feed_name": feed_name,
                    "category": category
                })
            except Exception:
                pass

        return {
            "success": True,
            "feed_id": feed_id,
            "name": feed_name,
            "new_count": len(new_articles),
            "triggered_alerts": triggered_alerts,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error fetching feed {feed_name} ({feed_url}): {e}")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE feeds
            SET last_checked = ?, last_status = 'ERROR', error_message = ?
            WHERE id = ?
        """, (now_iso, str(e)[:250], feed_id))
        conn.commit()
        conn.close()

        return {
            "success": False,
            "feed_id": feed_id,
            "name": feed_name,
            "new_count": 0,
            "triggered_alerts": [],
            "error": str(e)
        }


def fetch_all_active_feeds() -> Dict[str, Any]:
    """
    Fetches all enabled feeds in database.
    Returns summary statistics.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feeds WHERE enabled = 1")
    feeds = [dict(row) for row in cursor.fetchall()]
    conn.close()

    total_new = 0
    all_triggered = []
    feed_results = []

    for f in feeds:
        res = fetch_single_feed(f)
        feed_results.append(res)
        total_new += res.get("new_count", 0)
        all_triggered.extend(res.get("triggered_alerts", []))

    return {
        "timestamp": datetime.now().isoformat(),
        "feeds_checked": len(feeds),
        "total_new_articles": total_new,
        "total_triggered_alerts": len(all_triggered),
        "triggered_alerts": all_triggered,
        "feed_results": feed_results
    }
