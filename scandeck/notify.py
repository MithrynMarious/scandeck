"""Cross-platform notification system for session state changes."""

import subprocess
import sys
import time
from typing import Optional

from .store import SessionStore, SessionStatus


def notify_desktop(title: str, message: str):
    """Send a desktop notification. Falls back to stdout if unavailable."""
    if sys.platform == "win32":
        _notify_windows(title, message)
    elif sys.platform == "darwin":
        _notify_macos(title, message)
    else:
        _notify_linux(title, message)


def _notify_windows(title: str, message: str):
    script = (
        f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        f"ContentType = WindowsRuntime] > $null; "
        f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(0); "
        f"$text = $xml.GetElementsByTagName('text'); "
        f"$text[0].AppendChild($xml.CreateTextNode('{title}')) > $null; "
        f"$text[1].AppendChild($xml.CreateTextNode('{message}')) > $null; "
        f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ScanDeck').Show($toast)"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _notify_macos(title: str, message: str):
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            capture_output=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _notify_linux(title: str, message: str):
    try:
        subprocess.run(
            ["notify-send", title, message],
            capture_output=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def watch_sessions(
    store: SessionStore,
    interval: float = 5.0,
    stuck_timeout: float = 30.0,
    desktop: bool = True,
    callback: Optional[callable] = None,
):
    """Poll session state and emit notifications on transitions.

    Args:
        store: SessionStore instance
        interval: Seconds between polls
        stuck_timeout: Minutes before a running session is marked stuck
        desktop: Send desktop notifications (in addition to stdout)
        callback: Optional function(event_type, session) for testing
    """
    from .detect import detect_claude_code_sessions, detect_finished_sessions

    prev_states: dict[str, str] = {}
    for s in store.list_sessions():
        prev_states[s["id"]] = s["status"]

    print(f"Watching sessions (poll every {int(interval)}s, stuck after {int(stuck_timeout)}m)")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            detect_claude_code_sessions(store)
            detect_finished_sessions(store)
            store.detect_stuck(timeout_minutes=stuck_timeout)

            current = store.list_sessions()
            current_states = {s["id"]: s["status"] for s in current}
            current_map = {s["id"]: s for s in current}

            for sid, status in current_states.items():
                prev = prev_states.get(sid)
                if prev is None:
                    session = current_map[sid]
                    _emit("new", session, desktop, callback)
                elif prev != status:
                    session = current_map[sid]
                    if status == SessionStatus.FINISHED.value:
                        _emit("finished", session, desktop, callback)
                    elif status == SessionStatus.STUCK.value:
                        _emit("stuck", session, desktop, callback)
                    elif status == SessionStatus.NEEDS_ATTENTION.value:
                        _emit("attention", session, desktop, callback)

            prev_states = current_states
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")


def _emit(event: str, session: dict, desktop: bool, callback: Optional[callable]):
    repo = session["repo"]
    if len(repo) > 40:
        repo = "..." + repo[-37:]
    tool = session["tool"]
    summary = session.get("summary", "")

    if event == "new":
        msg = f"[new] {tool} started on {repo}"
        title = "ScanDeck: New Session"
    elif event == "finished":
        msg = f"[done] {tool} finished on {repo}"
        if summary:
            msg += f": {summary}"
        title = "ScanDeck: Session Finished"
    elif event == "stuck":
        msg = f"[stuck] {tool} on {repo} has stopped responding"
        title = "ScanDeck: Session Stuck"
    elif event == "attention":
        msg = f"[!] {tool} on {repo} needs attention"
        title = "ScanDeck: Needs Attention"
    else:
        msg = f"[{event}] {tool} on {repo}"
        title = f"ScanDeck: {event}"

    ts = time.strftime("%H:%M:%S")
    print(f"{ts}  {msg}")

    if desktop:
        notify_desktop(title, msg)

    if callback:
        callback(event, session)
