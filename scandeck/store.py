"""Session state store: JSON file at ~/.scandeck/sessions.json."""

import json
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional


class SessionStatus(str, Enum):
    RUNNING = "running"
    FINISHED = "finished"
    STUCK = "stuck"
    NEEDS_ATTENTION = "needs_attention"


class SessionStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path.home() / ".scandeck" / "sessions.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._sessions = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._sessions = {}

    def _save(self):
        self.path.write_text(
            json.dumps(self._sessions, indent=2, default=str),
            encoding="utf-8",
        )

    def register(
        self,
        tool: str,
        repo: str,
        branch: str = "",
        summary: str = "",
        session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())[:8]
        self._sessions[sid] = {
            "id": sid,
            "tool": tool,
            "repo": repo,
            "branch": branch,
            "status": SessionStatus.RUNNING.value,
            "start_time": time.time(),
            "last_activity": time.time(),
            "summary": summary,
        }
        self._save()
        return sid

    def update(self, session_id: str, **kwargs):
        if session_id not in self._sessions:
            return False
        s = self._sessions[session_id]
        for k, v in kwargs.items():
            if k in s:
                s[k] = v
        s["last_activity"] = time.time()
        self._save()
        return True

    def complete(self, session_id: str, summary: str = ""):
        if session_id not in self._sessions:
            return False
        s = self._sessions[session_id]
        s["status"] = SessionStatus.FINISHED.value
        s["last_activity"] = time.time()
        if summary:
            s["summary"] = summary
        self._save()
        return True

    def list_sessions(self, status: Optional[str] = None) -> list[dict]:
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s["status"] == status]
        return sorted(sessions, key=lambda s: s["last_activity"], reverse=True)

    def get(self, session_id: str) -> Optional[dict]:
        return self._sessions.get(session_id)

    def prune(self, max_age_hours: float = 24.0) -> int:
        cutoff = time.time() - (max_age_hours * 3600)
        to_remove = [
            sid
            for sid, s in self._sessions.items()
            if s["status"] == SessionStatus.FINISHED.value
            and s["last_activity"] < cutoff
        ]
        for sid in to_remove:
            del self._sessions[sid]
        if to_remove:
            self._save()
        return len(to_remove)

    def detect_stuck(self, timeout_minutes: float = 30.0) -> list[str]:
        cutoff = time.time() - (timeout_minutes * 60)
        stuck = []
        for sid, s in self._sessions.items():
            if (
                s["status"] == SessionStatus.RUNNING.value
                and s["last_activity"] < cutoff
            ):
                s["status"] = SessionStatus.STUCK.value
                stuck.append(sid)
        if stuck:
            self._save()
        return stuck

    def remove(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save()
            return True
        return False
