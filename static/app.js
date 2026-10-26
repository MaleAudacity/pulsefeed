/**
 * PulseFeed Client Application
 * Handles reactive UI updates, Web Audio chime synthesizer,
 * REST API communication, modals, and filtering.
 */

// --- Global State ---
const state = {
  category: 'all',
  filter: 'all', // 'all', 'unread', 'starred', 'alert_only'
  search: '',
  articles: [],
  triggers: [],
  feeds: [],
  alertLogs: [],
  settings: {},
  stats: {},
  isSyncing: false
};

// --- Web Audio API Chime Synthesizer ---
let audioCtx = null;
let lastChimeTime = 0;

function isSoundMuted() {
  return localStorage.getItem('pulsefeed_sound_muted') === 'true';
}

function playAlertChime() {
  if (isSoundMuted()) return;
  const nowMs = Date.now();
  if (nowMs - lastChimeTime < 10000) return; // 10s cooldown to prevent notification spam
  lastChimeTime = nowMs;

  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!audioCtx) {
      audioCtx = new AudioContext();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }

    const now = audioCtx.currentTime;

    // First tone (E6 ~ 1318 Hz)
    const osc1 = audioCtx.createOscillator();
    const gain1 = audioCtx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(1318.51, now);
    gain1.gain.setValueAtTime(0.2, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
    osc1.connect(gain1);
    gain1.connect(audioCtx.destination);
    osc1.start(now);
    osc1.stop(now + 0.3);

    // Second harmonious tone (B6 ~ 1975 Hz)
    const osc2 = audioCtx.createOscillator();
    const gain2 = audioCtx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(1975.53, now + 0.1);
    gain2.gain.setValueAtTime(0.25, now + 0.1);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
    osc2.connect(gain2);
    gain2.connect(audioCtx.destination);
    osc2.start(now + 0.1);
    osc2.stop(now + 0.45);
  } catch (err) {
    console.warn("Web Audio chime could not play:", err);
  }
}

// --- In-App Toast Notification ---
function showInAppToast(title, desc, icon = '🔔', duration = 4000) {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-content">
      <div class="toast-title">${title}</div>
      <div class="toast-desc">${desc}</div>
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// --- Date Formatter ---
function formatTimeAgo(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diffSec = Math.floor((now - date) / 1000);

  if (diffSec < 60) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// --- API Service Calls ---

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    state.stats = await res.json();
    renderStats();
  } catch (err) {
    console.error("fetchStats error:", err);
  }
}

async function fetchArticles() {
  const container = document.getElementById('articlesContainer');
  try {
    let url = `/api/articles?category=${encodeURIComponent(state.category)}&filter=${encodeURIComponent(state.filter)}&limit=100`;
    if (state.search.trim()) {
      url += `&search=${encodeURIComponent(state.search.trim())}`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load articles");
    const data = await res.json();
    state.articles = data.articles || [];
    renderArticles();
    document.getElementById('resultsCount').textContent = `Showing ${state.articles.length} of ${data.total} items`;
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <p>⚠️ Error loading news articles. Check if local backend is active.</p>
      </div>
    `;
    console.error("fetchArticles error:", err);
  }
}

async function fetchTriggers() {
  try {
    const res = await fetch('/api/triggers');
    if (!res.ok) return;
    const data = await res.json();
    state.triggers = data.triggers || [];
    renderTriggers();
  } catch (err) {
    console.error("fetchTriggers error:", err);
  }
}

async function fetchFeeds() {
  try {
    const res = await fetch('/api/feeds');
    if (!res.ok) return;
    const data = await res.json();
    state.feeds = data.feeds || [];
    renderFeeds();
  } catch (err) {
    console.error("fetchFeeds error:", err);
  }
}

async function fetchAlertLogs() {
  try {
    const res = await fetch('/api/alerts?limit=100');
    if (!res.ok) return;
    const data = await res.json();
    state.alertLogs = data.alerts || [];
    renderAlertLogs();
  } catch (err) {
    console.error("fetchAlertLogs error:", err);
  }
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const data = await res.json();
    state.settings = data.settings || {};
    populateSettingsForm();
  } catch (err) {
    console.error("fetchSettings error:", err);
  }
}

// --- Rendering Functions ---

function updateClock() {
  const clockEl = document.getElementById('ticketClock');
  if (clockEl) {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}

function renderStats() {
  const s = state.stats;
  const total = s.total_articles || 0;
  const unread = s.unread_articles || 0;
  const alerts = s.total_alerts_fired || 0;
  const triggers = s.active_triggers || 0;
  const feeds = s.active_feeds || 15;

  if (document.getElementById('statTotalArticles')) {
    document.getElementById('statTotalArticles').textContent = total.toLocaleString();
  }
  if (document.getElementById('statUnreadCountBadge')) {
    document.getElementById('statUnreadCountBadge').textContent = `${unread.toLocaleString()} Unread`;
  }
  if (document.getElementById('statActiveTriggersCount')) {
    document.getElementById('statActiveTriggersCount').textContent = `${triggers} Active Alert Rules`;
  }
  if (document.getElementById('heroAlertsBadge')) {
    document.getElementById('heroAlertsBadge').textContent = alerts.toLocaleString();
  }
  if (document.getElementById('statAlertsFired')) {
    document.getElementById('statAlertsFired').textContent = alerts.toLocaleString();
  }
  if (document.getElementById('statActiveFeeds')) {
    document.getElementById('statActiveFeeds').textContent = `${feeds} Sources`;
  }

  // Topic count badges
  const cat = s.category_counts || {};
  if (document.getElementById('countAll')) document.getElementById('countAll').textContent = total;
  if (document.getElementById('countDailyNewsUS')) {
    document.getElementById('countDailyNewsUS').textContent = (cat.daily_news_us ? cat.daily_news_us.total : 0);
  }
  if (document.getElementById('countDailyNewsIND')) {
    document.getElementById('countDailyNewsIND').textContent = (cat.daily_news_ind ? cat.daily_news_ind.total : 0);
  }
  if (document.getElementById('countSingersUSA')) {
    document.getElementById('countSingersUSA').textContent = (cat.singers_usa ? cat.singers_usa.total : 0);
  }
  if (document.getElementById('countHollywoodStars')) {
    document.getElementById('countHollywoodStars').textContent = (cat.hollywood_stars ? cat.hollywood_stars.total : 0);
  }
  if (document.getElementById('countMixSports')) {
    document.getElementById('countMixSports').textContent = (cat.mix_sports ? cat.mix_sports.total : 0);
  }
  if (document.getElementById('countAlertsLog')) {
    document.getElementById('countAlertsLog').textContent = alerts;
  }
}

function getCategoryBadge(category) {
  const map = {
    daily_news_us: { label: 'US News', class: 'cat-daily_news_us' },
    daily_news_ind: { label: 'India News', class: 'cat-daily_news_ind' },
    singers_usa: { label: 'Singers USA', class: 'cat-singers_usa' },
    hollywood_stars: { label: 'Hollywood', class: 'cat-hollywood_stars' },
    mix_sports: { label: 'MLB / NFL', class: 'cat-mix_sports' }
  };
  const c = map[category] || { label: category, class: 'cat-daily_news_us' };
  return `<span class="category-capsule ${c.class}">${c.label}</span>`;
}

function renderArticles() {
  const container = document.getElementById('articlesContainer');
  if (!container) return;

  if (!state.articles.length) {
    container.innerHTML = `
      <div class="empty-state">
        <p style="font-size: 2rem; margin-bottom: 0.5rem;">📭</p>
        <p style="font-weight: 800; font-size: 1.15rem; color: var(--ink-primary);">No articles found</p>
        <p style="font-size: 0.85rem; margin-top: 0.35rem; color: var(--ink-secondary);">Try changing your search filter or click "Sync" to fetch live news.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = state.articles.map(art => {
    const isAlert = art.has_alert === 1;
    const isRead = art.is_read === 1;
    const isStarred = art.is_starred === 1;
    const timeAgo = formatTimeAgo(art.published_at);
    const catBadge = getCategoryBadge(art.category);

    return `
      <article class="bento-article-card ${isAlert ? 'has-alert' : ''} ${isRead ? 'is-read' : ''}" data-id="${art.id}">
        ${isAlert ? `
          <div class="card-punch-accent">
            ◆ ${escapeHtml(art.alert_rule_name || 'ALERT')}
          </div>
        ` : ''}

        <div class="article-card-top">
          <div class="article-publisher">
            <span>${art.feed_icon || '📰'}</span>
            <span>${escapeHtml(art.feed_name || art.author || 'PulseFeed')}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.45rem;">
            ${catBadge}
            <span style="font-size: 0.72rem; font-family: var(--font-mono); color: var(--ink-secondary);">${timeAgo}</span>
          </div>
        </div>

        <h3 class="article-headline">
          <a href="${escapeHtml(art.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(art.title)}</a>
        </h3>

        <div class="article-snippet">
          ${escapeHtml(art.summary || 'Click below to read full coverage on publisher website.')}
        </div>

        <div class="card-ticket-footer">
          <div class="card-actions-group">
            <button class="tactile-btn ${isStarred ? 'active-star' : ''}" onclick="toggleStar(${art.id})" title="${isStarred ? 'Unstar' : 'Star Article'}">
              ${isStarred ? '★' : '☆'}
            </button>
            <button class="tactile-btn ${isRead ? 'active-read' : ''}" onclick="toggleRead(${art.id})" title="${isRead ? 'Mark Unread' : 'Mark as Read'}">
              ${isRead ? '✓' : '📖'}
            </button>
            <button class="tactile-btn" onclick="quickCreateRule('${escapeHtml(art.title.replace(/'/g, "\\'"))}', '${art.category}')" title="Create Alert Rule from Headline">
              ⚡
            </button>
          </div>
          <a class="read-story-pill" href="${escapeHtml(art.link)}" target="_blank" rel="noopener noreferrer">
            Read Story ↗
          </a>
        </div>
      </article>
    `;
  }).join('');
}

function renderTriggers() {
  const container = document.getElementById('triggersList');
  document.getElementById('triggerListCount').textContent = state.triggers.length;

  if (!state.triggers.length) {
    container.innerHTML = `<div class="empty-state"><p>No alert triggers defined yet.</p></div>`;
    return;
  }

  container.innerHTML = state.triggers.map(t => {
    const isUrgent = t.priority === 'urgent';
    const isHigh = t.priority === 'high';
    const priorityColor = isUrgent ? '#ef4444' : isHigh ? '#f59e0b' : '#38bdf8';

    return `
      <div class="trigger-item-card ${t.enabled ? '' : 'disabled'}">
        <div class="trigger-item-top">
          <span class="trigger-item-name">${escapeHtml(t.name)}</span>
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span style="font-size:0.7rem; font-weight:700; color:${priorityColor}; text-transform:uppercase;">${t.priority}</span>
            <input type="checkbox" ${t.enabled ? 'checked' : ''} onchange="toggleTriggerEnabled(${t.id}, this.checked)" title="Enable / Disable Rule" />
          </div>
        </div>
        <div class="trigger-item-kws">
          ${escapeHtml(t.keywords)}
        </div>
        <div class="trigger-item-bottom">
          <span>Topic: <b>${escapeHtml(t.category)}</b> (${t.match_mode})</span>
          <div style="display:flex; gap:0.5rem;">
            <span>Fired: <b>${t.fire_count}x</b></span>
            <button class="btn btn-sm btn-ghost" onclick="editTrigger(${t.id})" style="padding:0.15rem 0.4rem;">Edit</button>
            <button class="btn btn-sm btn-danger" onclick="deleteTrigger(${t.id})" style="padding:0.15rem 0.4rem;">✕</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function renderFeeds() {
  const container = document.getElementById('feedsList');
  document.getElementById('feedListCount').textContent = state.feeds.length;

  if (!state.feeds.length) {
    container.innerHTML = `<div class="empty-state"><p>No feeds configured.</p></div>`;
    return;
  }

  container.innerHTML = state.feeds.map(f => {
    return `
      <div class="feed-item-card ${f.enabled ? '' : 'disabled'}">
        <div class="feed-item-left">
          <span style="font-size:1.15rem;">${f.icon || '📰'}</span>
          <div>
            <div class="feed-item-name">${escapeHtml(f.name)}</div>
            <div class="feed-item-meta">${escapeHtml(f.category)} • ${f.article_count || 0} items</div>
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <input type="checkbox" ${f.enabled ? 'checked' : ''} onchange="toggleFeedEnabled(${f.id}, this.checked)" title="Enable / Disable Feed" />
          <button class="btn btn-sm btn-danger" onclick="deleteFeed(${f.id})" style="padding:0.2rem 0.5rem;" title="Remove Feed">✕</button>
        </div>
      </div>
    `;
  }).join('');
}

function renderAlertLogs() {
  const tbody = document.getElementById('alertsTableBody');
  if (!state.alertLogs.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:2rem;">No triggered alerts recorded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.alertLogs.map(log => {
    const timeAgo = formatTimeAgo(log.created_at);
    const isUrgent = log.priority === 'urgent';
    const isHigh = log.priority === 'high';
    const badgeColor = isUrgent ? '#ef4444' : isHigh ? '#f59e0b' : '#38bdf8';

    return `
      <tr>
        <td style="font-family:var(--font-mono); font-size:0.75rem; color:#94a3b8;">${timeAgo}</td>
        <td><span style="color:${badgeColor}; font-weight:700; text-transform:uppercase;">${log.priority}</span></td>
        <td><b>${escapeHtml(log.trigger_name)}</b></td>
        <td><code style="background:rgba(255,255,255,0.08); padding:0.15rem 0.4rem; border-radius:4px;">${escapeHtml(log.matched_keyword || '')}</code></td>
        <td>${escapeHtml(log.article_title)}</td>
        <td><span class="category-tag">${escapeHtml(log.category)}</span></td>
        <td>
          <a href="${escapeHtml(log.article_link)}" target="_blank" rel="noopener noreferrer" class="read-link">
            Open ↗
          </a>
        </td>
      </tr>
    `;
  }).join('');
}

function populateSettingsForm() {
  const s = state.settings;
  if (s.poll_interval_minutes) {
    document.getElementById('settingPollInterval').value = s.poll_interval_minutes;
  }
  if (s.desktop_notifications) {
    document.getElementById('settingDesktopNotify').value = s.desktop_notifications;
  }
  if (s.sound_enabled) {
    document.getElementById('settingSound').checked = s.sound_enabled.toLowerCase() === 'true';
  }
}

// --- Action Handlers ---

window.toggleStar = async function(id) {
  try {
    const res = await fetch(`/api/articles/${id}/star`, { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();
    const art = state.articles.find(a => a.id === id);
    if (art) art.is_starred = data.is_starred;
    renderArticles();
    fetchStats();
  } catch (err) {
    console.error("toggleStar error:", err);
  }
};

window.toggleRead = async function(id) {
  try {
    const res = await fetch(`/api/articles/${id}/read`, { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();
    const art = state.articles.find(a => a.id === id);
    if (art) art.is_read = data.is_read;
    renderArticles();
    fetchStats();
  } catch (err) {
    console.error("toggleRead error:", err);
  }
};

window.quickCreateRule = function(title, category) {
  // Extract key words from title (skip trivial stopwords)
  const stopwords = new Set(['the','a','an','and','or','in','on','at','to','for','of','with','is','are','was','were','as','by','its','from','that','this','who','what','how','why']);
  const words = title.replace(/[^a-zA-Z0-9\s]/g, '').split(/\s+/).filter(w => w.length > 3 && !stopwords.has(w.toLowerCase()));
  const sampleKws = words.slice(0, 3).join(', ');

  document.getElementById('modalTriggers').style.display = 'flex';
  document.getElementById('triggerEditId').value = '';
  document.getElementById('triggerFormHeading').textContent = 'Create New Alert Trigger';
  document.getElementById('triggerName').value = `Alert: ${words[0] || 'Custom'}`;
  document.getElementById('triggerCategory').value = category || 'all';
  document.getElementById('triggerKeywords').value = sampleKws || title.slice(0, 30);
  document.getElementById('triggerPriority').value = 'high';
  document.getElementById('btnCancelTriggerEdit').style.display = 'none';
};

window.toggleTriggerEnabled = async function(id, enabled) {
  try {
    await fetch(`/api/triggers/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: enabled ? 1 : 0 })
    });
    fetchTriggers();
    fetchStats();
  } catch (err) {
    console.error("toggleTriggerEnabled error:", err);
  }
};

window.editTrigger = function(id) {
  const t = state.triggers.find(item => item.id === id);
  if (!t) return;
  document.getElementById('triggerEditId').value = t.id;
  document.getElementById('triggerFormHeading').textContent = 'Edit Alert Trigger';
  document.getElementById('triggerName').value = t.name;
  document.getElementById('triggerCategory').value = t.category;
  document.getElementById('triggerKeywords').value = t.keywords;
  document.getElementById('triggerMatchMode').value = t.match_mode;
  document.getElementById('triggerPriority').value = t.priority;
  document.getElementById('triggerNotifyDesktop').checked = Boolean(t.notify_desktop);
  document.getElementById('triggerNotifySound').checked = Boolean(t.notify_sound);
  document.getElementById('btnCancelTriggerEdit').style.display = 'inline-flex';
};

window.deleteTrigger = async function(id) {
  if (!confirm("Are you sure you want to delete this alert rule?")) return;
  try {
    await fetch(`/api/triggers/${id}`, { method: 'DELETE' });
    showInAppToast("Trigger Removed", "The alert rule has been deleted.", "🗑️");
    fetchTriggers();
    fetchStats();
  } catch (err) {
    console.error("deleteTrigger error:", err);
  }
};

window.toggleFeedEnabled = async function(id, enabled) {
  try {
    await fetch(`/api/feeds/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: enabled ? 1 : 0 })
    });
    fetchFeeds();
    fetchStats();
  } catch (err) {
    console.error("toggleFeedEnabled error:", err);
  }
};

window.deleteFeed = async function(id) {
  if (!confirm("Are you sure you want to remove this RSS feed and its articles?")) return;
  try {
    await fetch(`/api/feeds/${id}`, { method: 'DELETE' });
    showInAppToast("Feed Removed", "Feed and its articles removed.", "🗑️");
    fetchFeeds();
    fetchArticles();
    fetchStats();
  } catch (err) {
    console.error("deleteFeed error:", err);
  }
};

// --- Helper Functions ---
function escapeHtml(text) {
  if (!text) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// --- Event Listeners Initialization ---

document.addEventListener('DOMContentLoaded', () => {
  // Initial Data Load
  fetchStats();
  fetchArticles();
  fetchTriggers();
  fetchFeeds();
  fetchAlertLogs();
  fetchSettings();
  updateClock();
  setInterval(updateClock, 1000);

  // Theme Toggle (Light Bento Cream / Dark Obsidian Glass)
  const themeBtn = document.getElementById('btnThemeToggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('dark-mode');
      const isDark = document.body.classList.contains('dark-mode');
      showInAppToast(
        "Theme Switched",
        isDark ? "Dark Obsidian Glass mode active" : "Warm Bento Cream mode active",
        "🌓",
        2500
      );
    });
  }

  // Sound Mute / Unmute Toggle Button
  const btnSound = document.getElementById('btnSoundToggle');
  const soundIcon = document.getElementById('soundIcon');
  const soundText = document.getElementById('soundText');

  function renderSoundBtn() {
    if (!btnSound) return;
    const muted = isSoundMuted();
    if (muted) {
      btnSound.classList.add('muted');
      if (soundIcon) soundIcon.textContent = '🔇';
      if (soundText) soundText.textContent = 'Muted';
    } else {
      btnSound.classList.remove('muted');
      if (soundIcon) soundIcon.textContent = '🔊';
      if (soundText) soundText.textContent = 'Sound ON';
    }
  }
  renderSoundBtn();

  if (btnSound) {
    btnSound.addEventListener('click', () => {
      const willMute = !isSoundMuted();
      localStorage.setItem('pulsefeed_sound_muted', willMute ? 'true' : 'false');
      renderSoundBtn();
      showInAppToast(
        willMute ? "Audio Muted" : "Audio Chime Enabled",
        willMute ? "Alert chimes silenced." : "Chimes will ring for breaking & urgent alerts.",
        willMute ? "🔇" : "🔊",
        2500
      );
      if (!willMute) {
        playAlertChime(); // Brief test sound on unmute
      }
    });
  }

  // Dismiss Breaking Alert Banner
  const btnDismissAlert = document.getElementById('btnDismissAlertBanner');
  if (btnDismissAlert) {
    btnDismissAlert.addEventListener('click', () => {
      const banner = document.getElementById('liveAlertBanner');
      if (banner) banner.style.display = 'none';
    });
  }

  // Connect to Real-Time Server-Sent Events (SSE) Push Stream
  function setupRealtimeStream() {
    const statusText = document.getElementById('engineStatusText');
    const sse = new EventSource('/api/stream');

    sse.addEventListener('connected', () => {
      if (statusText) statusText.textContent = 'Live SSE';
    });

    sse.addEventListener('alert', (e) => {
      try {
        const alert = JSON.parse(e.data);
        
        // Update top alert banner with headline
        const banner = document.getElementById('liveAlertBanner');
        const bannerRule = document.getElementById('alertBannerRule');
        const bannerTitle = document.getElementById('alertBannerTitle');
        const bannerLink = document.getElementById('alertBannerLink');

        if (banner && bannerRule && bannerTitle && bannerLink) {
          bannerRule.textContent = alert.trigger_name || 'BREAKING';
          bannerTitle.textContent = alert.title || '';
          bannerLink.href = alert.link || '#';
          banner.style.display = 'flex';
        }

        // Only chime if priority is urgent or high and sound is active
        if (alert.priority === 'urgent' || alert.priority === 'high') {
          playAlertChime();
        }

        showInAppToast(
          `🚨 ${alert.trigger_name || 'Alert Triggered'}`,
          alert.title,
          '⚡',
          7000
        );

        fetchStats();
        fetchArticles();
        fetchAlertLogs();
      } catch (err) {
        console.error("SSE alert parse err:", err);
      }
    });

    sse.addEventListener('new_articles', (e) => {
      try {
        const info = JSON.parse(e.data);
        fetchStats();
        fetchArticles();
      } catch (err) {
        console.error("SSE new_articles parse err:", err);
      }
    });

    sse.onerror = () => {
      if (statusText) statusText.textContent = 'Reconnecting...';
      sse.close();
      setTimeout(setupRealtimeStream, 4000);
    };
  }
  setupRealtimeStream();

  // Background Auto-Refresh UI fallback every 30 seconds
  setInterval(() => {
    fetchStats();
    if (state.category === 'alerts_log') {
      fetchAlertLogs();
    } else {
      fetchArticles();
    }
  }, 30000);

  // Sync Now Button
  const btnSync = document.getElementById('btnSyncNow');

  btnSync.addEventListener('click', async () => {
    if (state.isSyncing) return;
    state.isSyncing = true;
    const origHtml = btnSync.innerHTML;
    btnSync.innerHTML = '<span>⏳ Syncing...</span>';

    try {
      const res = await fetch('/api/sync', { method: 'POST' });
      const data = await res.json();
      
      const newCount = data.total_new_articles || 0;
      const alertCount = data.total_triggered_alerts || 0;

      if (alertCount > 0) {
        playAlertChime();
        showInAppToast(
          `🚨 ${alertCount} Alert(s) Triggered!`,
          `${newCount} new articles fetched. Matched your custom rules.`,
          '⚡',
          6000
        );
      } else {
        showInAppToast(
          'Sync Complete',
          `${newCount} new articles ingested across ${data.feeds_checked} active feeds.`,
          '✅'
        );
      }

      fetchStats();
      fetchArticles();
      fetchAlertLogs();
    } catch (err) {
      showInAppToast('Sync Failed', 'Could not reach local RSS server.', '❌');
    } finally {
      state.isSyncing = false;
      btnSync.innerHTML = origHtml;
    }
  });

  // Test Alert Button
  document.getElementById('btnTestNotify').addEventListener('click', async () => {
    playAlertChime();
    showInAppToast(
      "Desktop Alert Triggered",
      "Sent a native Windows toast notification to your desktop screen.",
      "🔔"
    );
    try {
      await fetch('/api/test-notification', { method: 'POST' });
    } catch (err) {
      console.error("test notification err:", err);
    }
  });

  // Category Tabs Navigation
  const topicTabs = document.getElementById('topicTabs');
  topicTabs.addEventListener('click', (e) => {
    const btn = e.target.closest('.nav-pill-link, .topic-tab');
    if (!btn) return;

    topicTabs.querySelectorAll('.nav-pill-link, .topic-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    state.category = btn.getAttribute('data-category');

    const articlesContainer = document.getElementById('articlesContainer');
    const alertsLogContainer = document.getElementById('alertsLogContainer');
    const toolbar = document.querySelector('.bento-toolbar, .toolbar');

    if (state.category === 'alerts_log') {
      articlesContainer.style.display = 'none';
      alertsLogContainer.style.display = 'block';
      if (toolbar) toolbar.style.display = 'none';
      fetchAlertLogs();
    } else {
      articlesContainer.style.display = 'grid';
      alertsLogContainer.style.display = 'none';
      if (toolbar) toolbar.style.display = 'flex';
      fetchArticles();
    }
  });

  // Filter Pills (All / Unread / Starred / Trigger Matches)
  const filterPills = document.getElementById('filterPills');
  filterPills.addEventListener('click', (e) => {
    const pill = e.target.closest('.pill-filter-btn, .pill-btn');
    if (!pill) return;

    filterPills.querySelectorAll('.pill-filter-btn, .pill-btn').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');

    state.filter = pill.getAttribute('data-filter');
    fetchArticles();
  });

  // Search Input (Debounced)
  const searchInput = document.getElementById('searchInput');
  const btnClearSearch = document.getElementById('btnClearSearch');
  let searchDebounceTimer = null;

  searchInput.addEventListener('input', () => {
    const val = searchInput.value;
    btnClearSearch.style.display = val ? 'block' : 'none';
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      state.search = val;
      fetchArticles();
    }, 280);
  });

  btnClearSearch.addEventListener('click', () => {
    searchInput.value = '';
    btnClearSearch.style.display = 'none';
    state.search = '';
    fetchArticles();
  });

  // Mark Visible as Read
  document.getElementById('btnMarkAllRead').addEventListener('click', async () => {
    try {
      await fetch('/api/articles/mark-all-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: state.category })
      });
      showInAppToast("Marked as Read", "Articles have been marked as read.", "✓");
      fetchArticles();
      fetchStats();
    } catch (err) {
      console.error("Mark all read err:", err);
    }
  });

  // Clear Alert Logs
  document.getElementById('btnClearAlertLogs').addEventListener('click', async () => {
    if (!confirm("Are you sure you want to clear the alert log history?")) return;
    try {
      await fetch('/api/alerts', { method: 'DELETE' });
      showInAppToast("Log Cleared", "Alert history was cleared.", "🗑️");
      fetchAlertLogs();
      fetchStats();
    } catch (err) {
      console.error("Clear alerts err:", err);
    }
  });

  // Modal: Triggers Open & Close
  const modalTriggers = document.getElementById('modalTriggers');
  document.getElementById('btnOpenTriggers').addEventListener('click', () => {
    modalTriggers.style.display = 'flex';
    fetchTriggers();
  });
  document.getElementById('btnCloseTriggers').addEventListener('click', () => {
    modalTriggers.style.display = 'none';
  });

  // Modal: Feeds & Settings Open & Close
  const modalFeeds = document.getElementById('modalFeeds');
  document.getElementById('btnOpenFeeds').addEventListener('click', () => {
    modalFeeds.style.display = 'flex';
    fetchFeeds();
    fetchSettings();
  });
  document.getElementById('btnCloseFeeds').addEventListener('click', () => {
    modalFeeds.style.display = 'none';
  });

  // Close modals on clicking overlay backdrop
  [modalTriggers, modalFeeds].forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });
  });

  // Trigger Form Submit (Create or Update)
  const triggerForm = document.getElementById('triggerForm');
  const btnCancelTriggerEdit = document.getElementById('btnCancelTriggerEdit');

  triggerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const editId = document.getElementById('triggerEditId').value;
    const payload = {
      name: document.getElementById('triggerName').value.trim(),
      category: document.getElementById('triggerCategory').value,
      keywords: document.getElementById('triggerKeywords').value.trim(),
      match_mode: document.getElementById('triggerMatchMode').value,
      priority: document.getElementById('triggerPriority').value,
      notify_desktop: document.getElementById('triggerNotifyDesktop').checked ? 1 : 0,
      notify_sound: document.getElementById('triggerNotifySound').checked ? 1 : 0,
      enabled: 1
    };

    try {
      if (editId) {
        await fetch(`/api/triggers/${editId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        showInAppToast("Rule Updated", `Trigger rule "${payload.name}" updated.`, "⚡");
      } else {
        await fetch('/api/triggers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        showInAppToast("Rule Created", `Trigger rule "${payload.name}" is now active.`, "⚡");
      }

      // Reset form
      triggerForm.reset();
      document.getElementById('triggerEditId').value = '';
      document.getElementById('triggerFormHeading').textContent = 'Create New Alert Trigger';
      btnCancelTriggerEdit.style.display = 'none';
      document.getElementById('triggerNotifyDesktop').checked = true;
      document.getElementById('triggerNotifySound').checked = true;

      fetchTriggers();
      fetchStats();
    } catch (err) {
      console.error("Save trigger err:", err);
    }
  });

  btnCancelTriggerEdit.addEventListener('click', () => {
    triggerForm.reset();
    document.getElementById('triggerEditId').value = '';
    document.getElementById('triggerFormHeading').textContent = 'Create New Alert Trigger';
    btnCancelTriggerEdit.style.display = 'none';
  });

  // Add Custom Feed Form Submit
  const addFeedForm = document.getElementById('addFeedForm');
  addFeedForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById('feedName').value.trim(),
      category: document.getElementById('feedCategory').value,
      url: document.getElementById('feedUrl').value.trim(),
      icon: document.getElementById('feedIcon').value
    };

    try {
      const res = await fetch('/api/feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errData = await res.json();
        alert(errData.detail || "Could not add feed.");
        return;
      }
      showInAppToast("Feed Added", `RSS feed "${payload.name}" was added & synced!`, "📡");
      addFeedForm.reset();
      fetchFeeds();
      fetchArticles();
      fetchStats();
    } catch (err) {
      console.error("Add feed err:", err);
    }
  });

  // Settings Form Submit
  const settingsForm = document.getElementById('settingsForm');
  settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      poll_interval_minutes: document.getElementById('settingPollInterval').value,
      desktop_notifications: document.getElementById('settingDesktopNotify').value,
      sound_enabled: document.getElementById('settingSound').checked ? 'true' : 'false'
    };

    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showInAppToast("Settings Saved", "Polling & notification settings updated.", "⚙️");
      fetchSettings();
    } catch (err) {
      console.error("Save settings err:", err);
    }
  });
});
