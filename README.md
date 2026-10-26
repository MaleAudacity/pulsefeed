# 🚀 PulseFeed - Local RSS & Alert Engine

A high-performance, local-running RSS aggregator and intelligent trigger/alert engine built for Windows with native Desktop Toast notifications, Web Audio chimes, and an ultra-modern dark cyber-glass dashboard.

---

## 🌟 Key Features

- **Pre-Configured for Your 5 Topics**:
  - 🇺🇸 **Daily News US**: Google News US Top Stories, NPR News, Reuters US News.
  - 🇮🇳 **Daily News IND**: Google News India Top Stories, The Hindu National, NDTV Top Stories.
  - 🎤 **Singers USA**: Billboard Latest, Rolling Stone Music, US Pop & Singer Highlights.
  - 🎬 **Hollywood Stars**: Deadline Hollywood, Variety Film & TV, Hollywood Stars & Celebrities.
  - ⚾🏈 **Mix Sports (Baseball & NFL)**: ESPN NFL, ESPN MLB Baseball, NFL & MLB Postseason Mix.

- **Intelligent Alert Rules & Trigger Engine**:
  - Match modes: `Any keyword (OR)`, `All keywords (AND)`, `Exact phrase`, and `Regular Expression (Regex)`.
  - Priority levels: `Urgent` (Alarm), `High` (Alert), `Medium` (Toast), `Low` (Silent).
  - Pre-seeded with smart triggers: *Breaking News Alert*, *Taylor Swift & Pop Stars*, *Super Bowl & NFL*, *World Series & MLB*, *Oscars & Blockbusters*, and *India Key Updates*.
  - 1-click **"⚡ Create Rule From This"** button on every article card.

- **Native Windows Desktop Notifications**:
  - Uses native Windows 10/11 toast notifications (`winotify` + PowerShell fallback).
  - Displays headline, summary snippet, and an interactive **"Read Article ↗"** button that opens the story in your browser.
  - Built-in rate limiting to prevent notification flooding during bulk syncs.

- **Web Audio Chime Synthesizer**:
  - Synthesized dual-tone notification chime built right into the dashboard (zero external audio files, zero lag, works 100% offline).

- **Sleek Cyber-Glass Dashboard**:
  - Real-time search, category navigation, unread filters, and star bookmarks.
  - Feed manager: add any custom RSS / Atom URL, enable/disable feeds, delete feeds.
  - Configurable polling intervals (1 min, 5 min, 10 min, 30 min, 1 hr).

---

## 📁 Project Structure

```
C:\Users\Administrator\rss-pulse\
  ├── database.py         # SQLite database models, schemas, and default seeds
  ├── fetcher.py          # RSS parser, HTML sanitizer, deduplication engine
  ├── trigger_engine.py   # Keyword & regex evaluator and alert dispatcher
  ├── notifier.py         # Windows Toast notification engine (winotify + PowerShell fallback)
  ├── app.py              # FastAPI REST API backend & static file server
  ├── main.py             # Server launcher with background async polling loop
  ├── requirements.txt    # Python dependencies
  ├── run.bat             # 1-Click launcher (starts server + opens browser)
  ├── run_headless.bat    # Background service launcher (headless mode)
  ├── pulsefeed.db        # SQLite database (auto-generated)
  └── static\
      ├── index.html      # Responsive cyber-glass dashboard
      ├── style.css       # High-contrast dark theme & animations
      └── app.js          # Reactive frontend, Web Audio chime, modal handlers
```

---

## 🚀 How to Run

### Method 1: 1-Click Batch Launcher (Recommended)
Double-click:
```bat
C:\Users\Administrator\rss-pulse\run.bat
```
This script will:
1. Verify required Python packages.
2. Start the local server on `http://127.0.0.1:8000`.
3. Automatically launch your default web browser to the dashboard.

### Method 2: Command Line
```powershell
cd C:\Users\Administrator\rss-pulse
python main.py
```

### Method 3: Headless Mode (Quiet Background Service)
```bat
C:\Users\Administrator\rss-pulse\run_headless.bat
```

---

## 🛠️ REST API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/stats` | GET | Metric counts (total, unread, active triggers, alerts fired) |
| `GET /api/articles` | GET | Paginated articles with category, search, and status filters |
| `POST /api/articles/{id}/read` | POST | Toggle read/unread status |
| `POST /api/articles/{id}/star` | POST | Toggle starred status |
| `POST /api/articles/mark-all-read` | POST | Mark all articles (or category) as read |
| `GET /api/feeds` | GET | List all configured RSS feeds |
| `POST /api/feeds` | POST | Add a new RSS/Atom feed URL |
| `PUT /api/feeds/{id}` | PUT | Update feed (toggle enabled, edit category/url) |
| `DELETE /api/feeds/{id}` | DELETE | Delete feed and its articles |
| `POST /api/sync` | POST | Trigger immediate manual fetch across all feeds |
| `GET /api/triggers` | GET | List all keyword alert triggers |
| `POST /api/triggers` | POST | Create a new alert rule |
| `PUT /api/triggers/{id}` | PUT | Edit or enable/disable an alert rule |
| `DELETE /api/triggers/{id}` | DELETE | Remove an alert rule |
| `GET /api/alerts` | GET | View historical log of triggered alerts |
| `DELETE /api/alerts` | DELETE | Clear alert history log |
| `POST /api/test-notification` | POST | Dispatch a test Windows desktop toast & chime |
| `GET /api/settings` | GET | Retrieve engine settings |
| `POST /api/settings` | POST | Update polling interval and notification preferences |

---

## ⚙️ Adding Custom Feeds
You can add custom feeds anytime:
1. Click **"Manage Feeds"** in the top navigation bar.
2. Enter the Feed Name, select the category, and paste the RSS/Atom URL.
3. Click **"Add RSS Source"**. The engine will immediately fetch the latest articles and evaluate your alert rules!
