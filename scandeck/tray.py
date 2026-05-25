"""System tray integration (optional dependency: pystray + pillow)."""

import sys
import threading
import time
from typing import Optional

from .store import SessionStore


def run_tray(store: Optional[SessionStore] = None):
    """Launch the system tray icon with session monitoring."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("System tray requires pystray and pillow:")
        print("  pip install scandeck[tray]")
        print("  # or: pip install pystray pillow")
        sys.exit(1)

    if store is None:
        store = SessionStore()

    def create_icon(count: int) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        if count > 0:
            draw.ellipse([4, 4, 60, 60], fill=(34, 139, 34))
        else:
            draw.ellipse([4, 4, 60, 60], fill=(100, 100, 100))
        if count > 0:
            text = str(count) if count < 10 else "9+"
            draw.text((22, 16), text, fill=(255, 255, 255))
        return img

    def get_menu():
        from .detect import detect_claude_code_sessions, detect_finished_sessions
        detect_claude_code_sessions(store)
        detect_finished_sessions(store)
        store.detect_stuck(timeout_minutes=30)

        sessions = store.list_sessions()
        running = [s for s in sessions if s["status"] == "running"]

        items = []
        if running:
            for s in running[:10]:
                repo = s["repo"]
                if len(repo) > 30:
                    repo = "..." + repo[-27:]
                label = f"{s['tool']}: {repo}"
                if s.get("branch"):
                    label += f" ({s['branch'][:15]})"
                items.append(pystray.MenuItem(label, lambda: None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)

        total = len(sessions)
        stuck = len([s for s in sessions if s["status"] == "stuck"])
        status_line = f"{len(running)} running"
        if stuck:
            status_line += f", {stuck} stuck"
        status_line += f" ({total} total)"
        items.append(pystray.MenuItem(status_line, lambda: None, enabled=False))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Refresh", lambda icon, item: _refresh(icon, store)))
        items.append(pystray.MenuItem("Quit", lambda icon, item: icon.stop()))

        return pystray.Menu(*items)

    def _refresh(icon, st):
        running = [s for s in st.list_sessions() if s["status"] == "running"]
        icon.icon = create_icon(len(running))
        icon.menu = get_menu()

    running = [s for s in store.list_sessions() if s["status"] == "running"]
    icon = pystray.Icon(
        "scandeck",
        create_icon(len(running)),
        "ScanDeck",
        menu=get_menu(),
    )

    def auto_refresh():
        while icon.visible:
            time.sleep(10)
            try:
                _refresh(icon, store)
            except Exception:
                pass

    refresh_thread = threading.Thread(target=auto_refresh, daemon=True)
    refresh_thread.start()

    icon.run()
