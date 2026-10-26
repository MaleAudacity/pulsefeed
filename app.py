"""
PulseFeed FastAPI Backend Server
Provides REST APIs for feeds, articles, triggers, alerts, settings, and serves the UI.
"""

import os
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from database import get_db, init_db, generate_guid_hash
from fetcher import fetch_all_active_feeds, fetch_single_feed
from notifier import send_windows_toast

app = FastAPI(title="PulseFeed - Local RSS & Alert Engine")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Ensure static folder exists
os.makedirs(STATIC_DIR, exist_ok=True)

# --- Real-Time Server-Sent Events (SSE) Hub ---
sse_clients: List[asyncio.Queue] = []
main_loop: Optional[asyncio.AbstractEventLoop] = None


async def broadcast_event(event_type: str, data: dict):
    """Pushes event down active SSE connections to browser dashboards."""
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    for queue in list(sse_clients):
        try:
            queue.put_nowait(payload)
        except Exception:
            pass


def broadcast_event_sync(event_type: str, data: dict):
    """Thread-safe event broadcaster for background poller thread."""
    global main_loop
    if main_loop and main_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(broadcast_event(event_type, data), main_loop)
        except Exception:
            pass


# --- Request Models ---
class ArticleActionRequest(BaseModel):
    is_read: Optional[int] = None
    is_starred: Optional[int] = None


class MarkAllReadRequest(BaseModel):
    category: Optional[str] = None


class FeedCreateRequest(BaseModel):
    category: str
    name: str
    url: str
    icon: Optional[str] = "📰"


class FeedUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    enabled: Optional[int] = None


class TriggerCreateRequest(BaseModel):
    name: str
    category: str = "all"
    keywords: str
    match_mode: str = "any"  # any, all, exact, regex
    priority: str = "high"    # low, medium, high, urgent
    notify_desktop: int = 1
    notify_sound: int = 1
    enabled: int = 1


class TriggerUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    keywords: Optional[str] = None
    match_mode: Optional[str] = None
    priority: Optional[str] = None
    notify_desktop: Optional[int] = None
    notify_sound: Optional[int] = None
    enabled: Optional[int] = None


class SettingsUpdateRequest(BaseModel):
    poll_interval_minutes: Optional[str] = None
    desktop_notifications: Optional[str] = None
    sound_enabled: Optional[str] = None
    quiet_hours_enabled: Optional[str] = None
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None


# --- Startup Event ---
@app.on_event("startup")
async def on_startup():
    global main_loop
    main_loop = asyncio.get_running_loop()
    init_db()


# --- Real-Time SSE Stream Endpoint ---
@app.get("/api/stream")
async def sse_stream(request: Request):
    """
    Real-Time Server-Sent Events stream.
    Instantly pushes new articles, trigger matches, and sync events to connected browsers.
    """
    queue = asyncio.Queue()
    sse_clients.append(queue)

    async def event_generator():
        # Send initial connected greeting
        yield f"event: connected\ndata: {json.dumps({'status': 'live', 'timestamp': datetime.now().isoformat()})}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                # Wait for next event or send heartbeat every 20 seconds
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield message
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in sse_clients:
                sse_clients.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# --- API Endpoints ---

@app.get("/api/stats")
def get_stats():
    """Returns high-level metric counts for dashboard cards."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM articles")
    total_articles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = 0")
    unread_articles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM articles WHERE is_starred = 1")
    starred_articles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM articles WHERE has_alert = 1")
    alert_articles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM feeds")
    total_feeds = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM feeds WHERE enabled = 1")
    active_feeds = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM triggers WHERE enabled = 1")
    active_triggers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alert_logs")
    total_alerts_fired = cursor.fetchone()[0]

    cursor.execute("SELECT MAX(last_checked) FROM feeds")
    last_sync = cursor.fetchone()[0]

    # Category counts
    cursor.execute("""
        SELECT category, COUNT(*) as cnt, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread_cnt
        FROM articles GROUP BY category
    """)
    cat_counts = {}
    for row in cursor.fetchall():
        cat_counts[row["category"]] = {
            "total": row["cnt"],
            "unread": row["unread_cnt"]
        }

    conn.close()

    return {
        "total_articles": total_articles,
        "unread_articles": unread_articles,
        "starred_articles": starred_articles,
        "alert_articles": alert_articles,
        "total_feeds": total_feeds,
        "active_feeds": active_feeds,
        "active_triggers": active_triggers,
        "total_alerts_fired": total_alerts_fired,
        "last_sync": last_sync,
        "category_counts": cat_counts
    }


@app.get("/api/articles")
def get_articles(
    category: Optional[str] = None,
    filter: Optional[str] = "all",  # 'all', 'unread', 'starred', 'alert_only'
    search: Optional[str] = None,
    sort: Optional[str] = "latest",  # 'latest', 'alerts_first', 'published'
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Retrieves paginated articles with optional category, search, sort, and status filters."""
    conn = get_db()
    cursor = conn.cursor()

    conditions = []
    params = []

    if category and category != "all":
        conditions.append("a.category = ?")
        params.append(category)

    if filter == "unread":
        conditions.append("a.is_read = 0")
    elif filter == "starred":
        conditions.append("a.is_starred = 1")
    elif filter == "alert_only":
        conditions.append("a.has_alert = 1")

    if search and search.strip():
        search_pattern = f"%{search.strip()}%"
        conditions.append("(a.title LIKE ? OR a.summary LIKE ? OR a.author LIKE ?)")
        params.extend([search_pattern, search_pattern, search_pattern])

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Count total matching
    count_query = f"SELECT COUNT(*) FROM articles a {where_clause}"
    cursor.execute(count_query, params)
    total_matching = cursor.fetchone()[0]

    # Determine sort order
    if sort == "published":
        order_clause = "ORDER BY a.published_at DESC, a.id DESC"
    elif sort == "alerts_first":
        order_clause = "ORDER BY a.has_alert DESC, a.id DESC"
    else:  # default: 'latest' - strictly guarantees that newly arrived news and alerts appear at top of feed
        order_clause = "ORDER BY a.id DESC"

    # Fetch articles
    query = f"""
        SELECT 
            a.id, a.guid_hash, a.feed_id, a.category, a.title, a.summary,
            a.link, a.author, a.published_at, a.fetched_at, a.is_read,
            a.is_starred, a.has_alert, a.alert_rule_name, a.alert_priority,
            f.name as feed_name, f.icon as feed_icon
        FROM articles a
        LEFT JOIN feeds f ON a.feed_id = f.id
        {where_clause}
        {order_clause}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    cursor.execute(query, params)
    articles = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "total": total_matching,
        "limit": limit,
        "offset": offset,
        "articles": articles
    }


@app.post("/api/articles/{article_id}/read")
def update_article_read_status(article_id: int, req: Optional[ArticleActionRequest] = None):
    conn = get_db()
    cursor = conn.cursor()

    if req and req.is_read is not None:
        new_val = req.is_read
    else:
        # Toggle
        cursor.execute("SELECT is_read FROM articles WHERE id = ?", (article_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Article not found")
        new_val = 0 if row["is_read"] == 1 else 1

    cursor.execute("UPDATE articles SET is_read = ? WHERE id = ?", (new_val, article_id))
    conn.commit()
    conn.close()
    return {"id": article_id, "is_read": new_val}


@app.post("/api/articles/{article_id}/star")
def update_article_star_status(article_id: int, req: Optional[ArticleActionRequest] = None):
    conn = get_db()
    cursor = conn.cursor()

    if req and req.is_starred is not None:
        new_val = req.is_starred
    else:
        cursor.execute("SELECT is_starred FROM articles WHERE id = ?", (article_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Article not found")
        new_val = 0 if row["is_starred"] == 1 else 1

    cursor.execute("UPDATE articles SET is_starred = ? WHERE id = ?", (new_val, article_id))
    conn.commit()
    conn.close()
    return {"id": article_id, "is_starred": new_val}


@app.post("/api/articles/mark-all-read")
def mark_all_articles_read(req: MarkAllReadRequest):
    conn = get_db()
    cursor = conn.cursor()
    if req.category and req.category != "all":
        cursor.execute("UPDATE articles SET is_read = 1 WHERE category = ?", (req.category,))
    else:
        cursor.execute("UPDATE articles SET is_read = 1")
    conn.commit()
    conn.close()
    return {"status": "success"}


# --- Feeds Management ---

@app.get("/api/feeds")
def list_feeds():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feeds ORDER BY category ASC, id ASC")
    feeds = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"feeds": feeds}


@app.post("/api/feeds")
def add_feed(req: FeedCreateRequest):
    conn = get_db()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    try:
        cursor.execute("""
            INSERT INTO feeds (category, name, url, icon, enabled, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (req.category, req.name, req.url.strip(), req.icon or "📰", now_iso))
        feed_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="A feed with this URL already exists.")
    conn.close()

    # Automatically fetch initial items in background
    feed_dict = {
        "id": feed_id,
        "name": req.name,
        "category": req.category,
        "url": req.url.strip()
    }
    fetch_res = fetch_single_feed(feed_dict)

    return {"status": "created", "id": feed_id, "initial_fetch": fetch_res}


@app.put("/api/feeds/{feed_id}")
def update_feed(feed_id: int, req: FeedUpdateRequest):
    conn = get_db()
    cursor = conn.cursor()

    updates = []
    params = []
    if req.name is not None:
        updates.append("name = ?")
        params.append(req.name)
    if req.category is not None:
        updates.append("category = ?")
        params.append(req.category)
    if req.url is not None:
        updates.append("url = ?")
        params.append(req.url.strip())
    if req.icon is not None:
        updates.append("icon = ?")
        params.append(req.icon)
    if req.enabled is not None:
        updates.append("enabled = ?")
        params.append(req.enabled)

    if not updates:
        conn.close()
        return {"status": "no change"}

    params.append(feed_id)
    cursor.execute(f"UPDATE feeds SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return {"status": "updated", "id": feed_id}


@app.delete("/api/feeds/{feed_id}")
def delete_feed(feed_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE feed_id = ?", (feed_id,))
    cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": feed_id}


# --- Triggers & Alerts Management ---

@app.get("/api/triggers")
def list_triggers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM triggers ORDER BY priority DESC, id ASC")
    triggers = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"triggers": triggers}


@app.post("/api/triggers")
def create_trigger(req: TriggerCreateRequest):
    conn = get_db()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO triggers (
            name, category, keywords, match_mode, priority,
            notify_desktop, notify_sound, enabled, fire_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        req.name, req.category, req.keywords, req.match_mode, req.priority,
        req.notify_desktop, req.notify_sound, req.enabled, now_iso
    ))
    trig_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"status": "created", "id": trig_id}


@app.put("/api/triggers/{trigger_id}")
def update_trigger(trigger_id: int, req: TriggerUpdateRequest):
    conn = get_db()
    cursor = conn.cursor()

    updates = []
    params = []
    for field, val in req.dict(exclude_unset=True).items():
        updates.append(f"{field} = ?")
        params.append(val)

    if not updates:
        conn.close()
        return {"status": "no change"}

    params.append(trigger_id)
    cursor.execute(f"UPDATE triggers SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return {"status": "updated", "id": trigger_id}


@app.delete("/api/triggers/{trigger_id}")
def delete_trigger(trigger_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": trigger_id}


@app.get("/api/alerts")
def list_alert_logs(limit: int = 50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM alert_logs 
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"alerts": logs}


@app.delete("/api/alerts")
def clear_alert_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alert_logs")
    conn.commit()
    conn.close()
    return {"status": "cleared"}


# --- Feed Sync Trigger ---

@app.post("/api/sync")
def trigger_sync():
    """Immediately synchronizes all active feeds and runs trigger checks."""
    result = fetch_all_active_feeds()
    return result


# --- Settings ---

@app.get("/api/settings")
def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = dict(cursor.fetchall())
    conn.close()
    return {"settings": settings}


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    conn = get_db()
    cursor = conn.cursor()
    for key, val in req.dict(exclude_unset=True).items():
        if val is not None:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()
    return {"status": "updated"}


# --- Test Notification ---

@app.post("/api/test-notification")
def test_notification():
    """Fires a live Windows Desktop Toast to verify user notifications."""
    success = send_windows_toast(
        title="🔔 PulseFeed System Check",
        message="Desktop notifications & trigger alerts are functioning properly!",
        url="http://127.0.0.1:8000",
        priority="high",
        sound=True
    )
    return {
        "success": success,
        "message": "Desktop toast notification sent. Check bottom-right of Windows screen!"
    }


# --- Static Files & Single Page App UI ---

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "PulseFeed backend running. Place index.html in static/"})

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
