"""
PulseFeed Main Runner
Initializes database, runs background feed polling loop,
and launches the FastAPI server with auto-browser launch.
"""

import os
import sys
import time
import socket
import urllib.request
import threading
import webbrowser
import logging
import uvicorn

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database import init_db, get_db
from fetcher import fetch_all_active_feeds
from app import app

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("pulsefeed.main")

stop_event = threading.Event()


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a TCP port is currently open and bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def check_existing_pulsefeed_instance(port: int, host: str = "127.0.0.1") -> bool:
    """Tests if an existing instance of PulseFeed is actively serving requests on this port."""
    try:
        req = urllib.request.Request(f"http://{host}:{port}/api/stats")
        with urllib.request.urlopen(req, timeout=1.0) as res:
            return res.status == 200
    except Exception:
        return False


def find_available_port(start_port: int = 8000, max_tries: int = 20, host: str = "127.0.0.1") -> int:
    """Finds the next free TCP port."""
    for p in range(start_port, start_port + max_tries):
        if not is_port_in_use(p, host):
            return p
    return start_port


def get_poll_interval_seconds() -> int:
    """Reads current polling interval from database settings."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'poll_interval_minutes'")
        row = cursor.fetchone()
        conn.close()
        if row:
            mins = float(row[0])
            return max(int(mins * 60), 30)  # Min 30 seconds
    except Exception:
        pass
    return 600  # Default 10 mins


def background_poller():
    """
    Continuous background loop that periodically fetches RSS feeds
    and processes triggers.
    """
    logger.info("Starting background RSS polling engine...")
    # Initial sync on launch
    try:
        logger.info("Executing initial feed sync...")
        res = fetch_all_active_feeds()
        logger.info(f"Initial sync complete: {res.get('total_new_articles', 0)} new articles, {res.get('total_triggered_alerts', 0)} alerts triggered.")
    except Exception as e:
        logger.error(f"Error during initial sync: {e}")

    last_poll_time = time.time()

    while not stop_event.is_set():
        interval = get_poll_interval_seconds()
        elapsed = time.time() - last_poll_time

        if elapsed >= interval:
            try:
                logger.info(f"Running periodic feed sync (interval: {interval//60}m)...")
                res = fetch_all_active_feeds()
                logger.info(f"Periodic sync complete: {res.get('total_new_articles', 0)} new articles, {res.get('total_triggered_alerts', 0)} alerts.")
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")
            last_poll_time = time.time()

        # Sleep in small slices to remain responsive to shutdown
        stop_event.wait(5.0)


def open_browser_delayed(url: str, delay: float = 1.8):
    """Opens browser after server starts."""
    time.sleep(delay)
    try:
        logger.info(f"Opening dashboard in default browser: {url}")
        webbrowser.open(url)
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")


def main():
    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    # Parse arguments
    no_browser = "--no-browser" in sys.argv or "--headless" in sys.argv
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
                url = f"http://{host}:{port}"
            except ValueError:
                pass

    # Check if port is already in use
    if is_port_in_use(port, host):
        if check_existing_pulsefeed_instance(port, host):
            print("=" * 65)
            print("  [*] PulseFeed is ALREADY RUNNING and active!")
            print(f"  [>] Dashboard URL: {url}")
            print("  [*] Opening dashboard in your default browser...")
            print("=" * 65)
            if not no_browser:
                webbrowser.open(url)
            print("\n  [Tip] PulseFeed is actively monitoring RSS feeds in background.")
            print("  Press Enter to close this launcher window...")
            try:
                input()
            except Exception:
                pass
            return
        else:
            new_port = find_available_port(port + 1, 20, host)
            print(f"  [!] Port {port} is occupied. Auto-switching to port {new_port}...")
            port = new_port
            url = f"http://{host}:{port}"

    print("=" * 65)
    print("  [*] PulseFeed - Local RSS & Alert Engine")
    print(f"  [>] Dashboard URL: {url}")
    print("  Topics: Daily News US, IND, Singers USA, Hollywood, Sports")
    print("=" * 65)

    # Initialize database
    init_db()

    # Start background polling thread
    poller_thread = threading.Thread(target=background_poller, daemon=True)
    poller_thread.start()

    # Auto-open browser if requested
    if not no_browser:
        browser_thread = threading.Thread(target=open_browser_delayed, args=(url,), daemon=True)
        browser_thread.start()

    # Start Uvicorn Server with automatic port retry
    try:
        current_port = port
        for _ in range(15):
            try:
                config = uvicorn.Config(app, host=host, port=current_port, log_level="warning")
                server = uvicorn.Server(config)
                server.run()
                break
            except OSError as e:
                if "10048" in str(e) or "already in use" in str(e).lower():
                    logger.warning(f"Port {current_port} busy or in TIME_WAIT. Trying port {current_port + 1}...")
                    current_port += 1
                else:
                    raise
    except KeyboardInterrupt:
        logger.info("Shutting down PulseFeed...")
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
