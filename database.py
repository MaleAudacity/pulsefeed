"""
PulseFeed Database Layer
Manages SQLite connection, schemas, migrations, default seeds, and CRUD queries.
"""

import sqlite3
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "pulsefeed.db")

DEFAULT_FEEDS = [
    # 1. Daily News US
    {
        "category": "daily_news_us",
        "name": "Google News US Top Stories",
        "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "icon": "🇺🇸"
    },
    {
        "category": "daily_news_us",
        "name": "NPR US News",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "icon": "📻"
    },
    {
        "category": "daily_news_us",
        "name": "Reuters US News",
        "url": "https://news.google.com/rss/search?q=source:Reuters+when:1d&hl=en-US&gl=US&ceid=US:en",
        "icon": "📰"
    },

    # 2. Daily News IND
    {
        "category": "daily_news_ind",
        "name": "Google News India Top",
        "url": "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
        "icon": "🇮🇳"
    },
    {
        "category": "daily_news_ind",
        "name": "The Hindu National News",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "icon": "🏛️"
    },
    {
        "category": "daily_news_ind",
        "name": "NDTV Top Stories",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "icon": "📺"
    },

    # 3. Singers USA
    {
        "category": "singers_usa",
        "name": "Billboard News",
        "url": "https://www.billboard.com/feed/",
        "icon": "🎤"
    },
    {
        "category": "singers_usa",
        "name": "Rolling Stone Music News",
        "url": "https://www.rollingstone.com/music/music-news/feed/",
        "icon": "🎸"
    },
    {
        "category": "singers_usa",
        "name": "US Singers & Pop Stars",
        "url": "https://news.google.com/rss/search?q=%22US+singers%22+OR+%22American+singer%22+OR+%22pop+artist%22+when:2d&hl=en-US&gl=US&ceid=US:en",
        "icon": "🎵"
    },

    # 4. Hollywood Stars
    {
        "category": "hollywood_stars",
        "name": "Deadline Hollywood",
        "url": "https://deadline.com/feed/",
        "icon": "🎬"
    },
    {
        "category": "hollywood_stars",
        "name": "Variety Film & TV",
        "url": "https://variety.com/feed/",
        "icon": "🌟"
    },
    {
        "category": "hollywood_stars",
        "name": "Hollywood Stars & Celebrities",
        "url": "https://news.google.com/rss/search?q=%22Hollywood+actor%22+OR+%22Hollywood+actress%22+OR+%22movie+star%22&hl=en-US&gl=US&ceid=US:en",
        "icon": "🍿"
    },

    # 5. Mix Sports Baseball NFL
    {
        "category": "mix_sports",
        "name": "ESPN NFL News",
        "url": "https://www.espn.com/espn/rss/nfl/news",
        "icon": "🏈"
    },
    {
        "category": "mix_sports",
        "name": "ESPN MLB Baseball News",
        "url": "https://www.espn.com/espn/rss/mlb/news",
        "icon": "⚾"
    },
    {
        "category": "mix_sports",
        "name": "NFL & Baseball Mix",
        "url": "https://news.google.com/rss/search?q=%22NFL%22+OR+%22MLB%22+OR+%22Baseball%22+OR+%22Super+Bowl%22&hl=en-US&gl=US&ceid=US:en",
        "icon": "🏆"
    }
]

DEFAULT_TRIGGERS = [
    {
        "name": "🚨 Breaking News Alert",
        "category": "all",
        "keywords": "BREAKING, URGENT, Just In, Developing Story, Red Alert",
        "match_mode": "any",
        "priority": "urgent",
        "notify_desktop": 1,
        "notify_sound": 1,
        "enabled": 1
    },
    {
        "name": "🎤 Taylor Swift & Pop Stars",
        "category": "singers_usa",
        "keywords": "Taylor Swift, Beyonce, Billie Eilish, Bruno Mars, Drake, Sabrina Carpenter, Lady Gaga, Olivia Rodrigo",
        "match_mode": "any",
        "priority": "high",
        "notify_desktop": 1,
        "notify_sound": 1,
        "enabled": 1
    },
    {
        "name": "🏈 Super Bowl & NFL Action",
        "category": "mix_sports",
        "keywords": "Super Bowl, Touchdown, Quarterback, Chiefs, Cowboys, 49ers, Eagles, NFL, Patrick Mahomes",
        "match_mode": "any",
        "priority": "high",
        "notify_desktop": 1,
        "notify_sound": 1,
        "enabled": 1
    },
    {
        "name": "⚾ World Series & MLB Buzz",
        "category": "mix_sports",
        "keywords": "World Series, Home Run, Yankees, Dodgers, Shohei Ohtani, Aaron Judge, Mets, MLB, Pitcher",
        "match_mode": "any",
        "priority": "high",
        "notify_desktop": 1,
        "notify_sound": 1,
        "enabled": 1
    },
    {
        "name": "🎬 Oscars, Blockbusters & Hollywood Stars",
        "category": "hollywood_stars",
        "keywords": "Oscar, Academy Award, Box Office, Marvel, Christopher Nolan, Margot Robbie, Tom Cruise, Leonardo DiCaprio, Zendaya",
        "match_mode": "any",
        "priority": "medium",
        "notify_desktop": 1,
        "notify_sound": 1,
        "enabled": 1
    },
    {
        "name": "🇮🇳 India Key News & Updates",
        "category": "daily_news_ind",
        "keywords": "Supreme Court, Prime Minister, Modi, Parliament, ISRO, Chandrayaan, RBI, Budget, Sensex",
        "match_mode": "any",
        "priority": "high",
        "notify_desktop": 1,
        "notify_sound": 1,
        "enabled": 1
    }
]

DEFAULT_SETTINGS = {
    "poll_interval_minutes": "2",
    "desktop_notifications": "triggers_only",  # 'all', 'triggers_only', 'disabled'
    "sound_enabled": "true",
    "quiet_hours_enabled": "false",
    "quiet_start": "22:00",
    "quiet_end": "08:00"
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes tables and seeds default feeds, triggers, and settings."""
    conn = get_db()
    cursor = conn.cursor()

    # Feeds Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            icon TEXT DEFAULT '📰',
            enabled INTEGER DEFAULT 1,
            last_checked TEXT,
            last_status TEXT DEFAULT 'IDLE',
            error_message TEXT,
            article_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # Articles Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid_hash TEXT UNIQUE NOT NULL,
            feed_id INTEGER,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            link TEXT NOT NULL,
            author TEXT,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            is_starred INTEGER DEFAULT 0,
            has_alert INTEGER DEFAULT 0,
            alert_rule_name TEXT,
            alert_priority TEXT,
            FOREIGN KEY(feed_id) REFERENCES feeds(id) ON DELETE SET NULL
        )
    """)

    # Index on category and publication time
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_cat_pub ON articles(category, published_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_guid ON articles(guid_hash)")

    # Triggers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'all',
            keywords TEXT NOT NULL,
            match_mode TEXT NOT NULL DEFAULT 'any',
            priority TEXT NOT NULL DEFAULT 'high',
            notify_desktop INTEGER DEFAULT 1,
            notify_sound INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1,
            fire_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # Alert Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_id INTEGER,
            trigger_name TEXT NOT NULL,
            article_id INTEGER,
            article_title TEXT NOT NULL,
            article_link TEXT NOT NULL,
            category TEXT NOT NULL,
            matched_keyword TEXT,
            priority TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(trigger_id) REFERENCES triggers(id) ON DELETE SET NULL,
            FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
        )
    """)

    # Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Seed Default Settings
    for key, val in DEFAULT_SETTINGS.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    # Seed Default Feeds
    now_str = datetime.now().isoformat()
    for feed in DEFAULT_FEEDS:
        cursor.execute("""
            INSERT OR IGNORE INTO feeds (category, name, url, icon, enabled, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (feed["category"], feed["name"], feed["url"], feed["icon"], now_str))

    # Seed Default Triggers
    cursor.execute("SELECT COUNT(*) FROM triggers")
    trigger_count = cursor.fetchone()[0]
    if trigger_count == 0:
        for trig in DEFAULT_TRIGGERS:
            cursor.execute("""
                INSERT INTO triggers (name, category, keywords, match_mode, priority, notify_desktop, notify_sound, enabled, fire_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                trig["name"], trig["category"], trig["keywords"],
                trig["match_mode"], trig["priority"],
                trig["notify_desktop"], trig["notify_sound"],
                trig["enabled"], now_str
            ))

    conn.commit()
    conn.close()


def generate_guid_hash(link: str, title: str) -> str:
    """Creates a deterministic SHA256 hash for deduplication."""
    norm = f"{(link or '').strip()}::{(title or '').strip()}".lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()
