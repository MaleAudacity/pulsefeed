"""
PulseFeed Trigger & Alert Rule Engine
Evaluates new articles against user-defined keyword rules, regexes, and category filters.
Dispatches desktop notifications and records alert history.
"""

import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from database import get_db
from notifier import send_windows_toast

logger = logging.getLogger("pulsefeed.trigger_engine")


def evaluate_article_against_triggers(
    article: Dict[str, Any],
    active_triggers: List[Dict[str, Any]]
) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Checks if an article matches any of the active trigger rules.
    Returns (matched_trigger, matched_keyword) or None.
    Priority order: urgent > high > medium > low.
    """
    article_cat = article.get("category", "")
    title = (article.get("title") or "").strip()
    summary = (article.get("summary") or "").strip()
    combined_text = f"{title} {summary}".lower()

    # Sort triggers by priority rank so highest priority takes precedence
    priority_order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    sorted_triggers = sorted(
        active_triggers,
        key=lambda t: priority_order.get(t.get("priority", "medium").lower(), 2),
        reverse=True
    )

    for trig in sorted_triggers:
        # Category check
        trig_cat = trig.get("category", "all")
        if trig_cat != "all" and trig_cat != article_cat:
            continue

        raw_keywords = trig.get("keywords", "")
        mode = trig.get("match_mode", "any").lower()

        matched, matched_keyword = _check_keywords_match(combined_text, title.lower(), raw_keywords, mode)
        if matched:
            return trig, matched_keyword

    return None


def _check_keywords_match(
    text: str,
    title_text: str,
    keywords_str: str,
    mode: str
) -> Tuple[bool, str]:
    """Helper to check keyword condition."""
    if not keywords_str:
        return False, ""

    if mode == "regex":
        try:
            pattern = re.compile(keywords_str.strip(), re.IGNORECASE)
            match = pattern.search(text)
            if match:
                return True, match.group(0)
        except Exception as e:
            logger.warning(f"Invalid regex in trigger '{keywords_str}': {e}")
        return False, ""

    # Split keywords by comma
    raw_list = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]
    if not raw_list:
        return False, ""

    if mode == "exact":
        # Full phrase must be present with word boundary
        phrase = keywords_str.strip().lower()
        if re.search(r'\b' + re.escape(phrase) + r'\b', text, re.IGNORECASE):
            return True, phrase
        return False, ""

    if mode == "all":
        # All keywords must appear in text with word boundary
        for kw in raw_list:
            if not re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
                return False, ""
        return True, ", ".join(raw_list)

    # Default: "any" - at least one keyword matches with word boundary
    for kw in raw_list:
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
            return True, kw

    return False, ""


def process_new_articles_for_triggers(
    articles: List[Dict[str, Any]],
    max_desktop_toasts: int = 4
) -> List[Dict[str, Any]]:
    """
    Evaluates a batch of new articles against all enabled triggers in SQLite.
    Updates DB records and fires notifications for matches.
    Returns list of triggered alert details.
    """
    if not articles:
        return []

    conn = get_db()
    cursor = conn.cursor()

    # Load active triggers
    cursor.execute("SELECT * FROM triggers WHERE enabled = 1")
    triggers = [dict(row) for row in cursor.fetchall()]

    # Load settings
    cursor.execute("SELECT key, value FROM settings")
    settings = dict(cursor.fetchall())
    notify_setting = settings.get("desktop_notifications", "triggers_only")
    sound_enabled = settings.get("sound_enabled", "true").lower() == "true"

    triggered_alerts = []
    toasts_sent = 0
    now_str = datetime.now().isoformat()

    for art in articles:
        match_result = evaluate_article_against_triggers(art, triggers)
        if match_result:
            trig, matched_kw = match_result
            art_id = art.get("id")
            art_title = art.get("title", "")
            art_link = art.get("link", "")
            art_cat = art.get("category", "")
            priority = trig.get("priority", "high")

            # 1. Update article alert flag in DB
            if art_id:
                cursor.execute("""
                    UPDATE articles 
                    SET has_alert = 1, alert_rule_name = ?, alert_priority = ?
                    WHERE id = ?
                """, (trig["name"], priority, art_id))

            # 2. Record alert in alert_logs
            cursor.execute("""
                INSERT INTO alert_logs (trigger_id, trigger_name, article_id, article_title, article_link, category, matched_keyword, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (trig.get("id"), trig["name"], art_id, art_title, art_link, art_cat, matched_kw, priority, now_str))

            # 3. Increment trigger fire_count
            if trig.get("id"):
                cursor.execute("UPDATE triggers SET fire_count = fire_count + 1 WHERE id = ?", (trig["id"],))

            alert_info = {
                "trigger_name": trig["name"],
                "matched_keyword": matched_kw,
                "priority": priority,
                "title": art_title,
                "link": art_link,
                "category": art_cat,
                "article_id": art_id
            }
            triggered_alerts.append(alert_info)

            # 4. Dispatch Windows Desktop Toast if enabled
            if notify_setting in ["all", "triggers_only"] and trig.get("notify_desktop", 1):
                if toasts_sent < max_desktop_toasts:
                    toast_title = f"{trig['name']}: {matched_kw.upper()}"
                    send_windows_toast(
                        title=toast_title,
                        message=art_title,
                        url=art_link,
                        priority=priority,
                        sound=sound_enabled and bool(trig.get("notify_sound", 1))
                    )
                    toasts_sent += 1

    conn.commit()
    conn.close()

    return triggered_alerts
