"""Multi-agent coordination: conflict detection and session overlap queries."""

import time
from typing import Optional

from .store import SessionStore


def find_overlapping_sessions(store: SessionStore, repo: str, branch: str = "") -> list[dict]:
    """Find other running sessions on the same repo/branch."""
    sessions = store.list_sessions(status="running")
    matches = []
    for s in sessions:
        if _repo_matches(s["repo"], repo):
            if not branch or not s.get("branch") or s["branch"] == branch:
                matches.append(s)
    return matches


def detect_conflicts(store: SessionStore) -> list[dict]:
    """Find potential conflicts: multiple running sessions on the same repo+branch."""
    sessions = store.list_sessions(status="running")
    by_target: dict[str, list[dict]] = {}
    for s in sessions:
        key = _normalize_repo(s["repo"])
        if s.get("branch"):
            key += f":{s['branch']}"
        by_target.setdefault(key, []).append(s)

    conflicts = []
    for target, group in by_target.items():
        if len(group) > 1:
            conflicts.append({
                "target": target,
                "sessions": [
                    {
                        "id": s["id"],
                        "tool": s["tool"],
                        "summary": s.get("summary", ""),
                        "duration_minutes": round((time.time() - s["start_time"]) / 60, 1),
                    }
                    for s in group
                ],
                "risk": "high" if all(s.get("branch") for s in group) else "medium",
            })
    return conflicts


def update_file_tracking(store: SessionStore, session_id: str, files: list[str]) -> bool:
    """Record which files a session is currently touching."""
    session = store.get(session_id)
    if not session:
        return False
    session["tracked_files"] = files
    session["last_activity"] = time.time()
    store._save()
    return True


def detect_file_conflicts(store: SessionStore) -> list[dict]:
    """Find sessions touching the same files."""
    sessions = store.list_sessions(status="running")
    file_owners: dict[str, list[dict]] = {}
    for s in sessions:
        for f in s.get("tracked_files", []):
            normalized = f.replace("\\", "/").lower()
            file_owners.setdefault(normalized, []).append({
                "session_id": s["id"],
                "tool": s["tool"],
                "repo": s["repo"],
            })

    conflicts = []
    for filepath, owners in file_owners.items():
        if len(owners) > 1:
            conflicts.append({"file": filepath, "sessions": owners})
    return conflicts


def _normalize_repo(repo: str) -> str:
    return repo.replace("\\", "/").rstrip("/").lower()


def _repo_matches(a: str, b: str) -> bool:
    return _normalize_repo(a) == _normalize_repo(b)
