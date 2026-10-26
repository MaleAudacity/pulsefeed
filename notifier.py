"""
PulseFeed Windows Desktop Notification Module
Uses winotify for native Windows 10/11 toast notifications with click-to-open article actions
and fallback to PowerShell toast if needed.
"""

import os
import sys
import html
import subprocess
import logging
from typing import Optional

logger = logging.getLogger("pulsefeed.notifier")

APP_ID = "PulseFeed Local News & Alerts"

try:
    import winotify
    WINOTIFY_AVAILABLE = True
except ImportError:
    WINOTIFY_AVAILABLE = False


def clean_text_for_toast(text: Optional[str], max_len: int = 140) -> str:
    """Sanitizes and shortens text for notification display."""
    if not text:
        return ""
    text = html.unescape(text)
    # Strip common line breaks
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[:max_len - 3] + "..."
    return text


def send_windows_toast(
    title: str,
    message: str,
    url: Optional[str] = None,
    priority: str = "medium",
    sound: bool = True
) -> bool:
    """
    Sends a native Windows Toast notification.
    If clicked, opens the article URL in the default browser.
    """
    clean_title = clean_text_for_toast(title, 80)
    clean_msg = clean_text_for_toast(message, 150)

    # Priority prefix badge
    prefix = ""
    if priority == "urgent":
        prefix = "🚨 [URGENT] "
    elif priority == "high":
        prefix = "⚡ [ALERT] "
    elif priority == "medium":
        prefix = "📌 "

    final_title = f"{prefix}{clean_title}"

    # Try winotify first
    if WINOTIFY_AVAILABLE:
        try:
            toast = winotify.Notification(
                app_id=APP_ID,
                title=final_title,
                msg=clean_msg,
                duration="long" if priority in ["urgent", "high"] else "short"
            )

            # Audio setup
            if sound:
                if priority == "urgent":
                    toast.set_audio(winotify.audio.LoopingAlarm, loop=False)
                elif priority == "high":
                    toast.set_audio(winotify.audio.Reminder, loop=False)
                else:
                    toast.set_audio(winotify.audio.Default, loop=False)
            else:
                toast.set_audio(winotify.audio.Silent, loop=False)

            # Add interactive buttons
            if url and url.startswith("http"):
                toast.add_actions(label="Read Article ↗", launch=url)
            toast.add_actions(label="Open PulseFeed", launch="http://localhost:8000")

            toast.show()
            return True
        except Exception as e:
            logger.warning(f"winotify error: {e}. Falling back to PowerShell toast.")

        # Fallback to PowerShell Windows notification if on Windows
        if sys.platform == "win32":
            return _send_powershell_toast(final_title, clean_msg, url)

    # Cross-platform desktop notification fallbacks
    if sys.platform == "win32":
        return _send_powershell_toast(final_title, clean_msg, url)
    elif sys.platform == "darwin":
        return _send_macos_notification(final_title, clean_msg)
    elif sys.platform.startswith("linux"):
        return _send_linux_notification(final_title, clean_msg)

    return False


def _send_macos_notification(title: str, message: str) -> bool:
    """macOS notification fallback via osascript."""
    try:
        clean_t = title.replace('"', '\\"')
        clean_m = message.replace('"', '\\"')
        script = f'display notification "{clean_m}" with title "{clean_t}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=4)
        return True
    except Exception as e:
        logger.warning(f"macOS notification failed: {e}")
        return False


def _send_linux_notification(title: str, message: str) -> bool:
    """Linux notification fallback via notify-send."""
    try:
        subprocess.run(["notify-send", title, message], capture_output=True, timeout=4)
        return True
    except Exception as e:
        logger.warning(f"Linux notify-send failed: {e}")
        return False


def _send_powershell_toast(title: str, message: str, url: Optional[str] = None) -> bool:
    """Fallback PowerShell script for Windows Notification."""
    try:
        # Escape quotes for PowerShell
        safe_title = title.replace('"', '`"')
        safe_msg = message.replace('"', '`"')
        ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{safe_title}</text>
            <text>{safe_msg}</text>
        </binding>
    </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{APP_ID}").Show($toast)
"""
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
        subprocess.run(cmd, capture_output=True, timeout=5)
        return True
    except Exception as e:
        logger.error(f"PowerShell toast failed: {e}")
        return False
