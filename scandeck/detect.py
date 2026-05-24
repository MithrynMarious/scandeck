"""Agent session detection from filesystem signals."""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from .store import SessionStore


def detect_claude_code_sessions(store: SessionStore) -> list[str]:
    """Detect active Claude Code sessions from filesystem markers."""
    detected = []
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return detected

    for project_dir in claude_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for session_file in project_dir.glob("*.jsonl"):
            lock_file = session_file.with_suffix(".jsonl.lock")
            if not lock_file.exists():
                continue
            sid = session_file.stem[:8]
            existing = store.get(sid)
            if existing:
                store.update(sid, last_activity=time.time())
                continue
            repo_path = _project_dir_to_repo(project_dir.name)
            branch = _get_branch(repo_path) if repo_path else ""
            store.register(
                tool="claude-code",
                repo=repo_path or project_dir.name,
                branch=branch,
                session_id=sid,
            )
            detected.append(sid)
    return detected


def detect_finished_sessions(store: SessionStore) -> list[str]:
    """Mark sessions as finished if their lock files are gone."""
    finished = []
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return finished

    for session in store.list_sessions(status="running"):
        if session["tool"] != "claude-code":
            continue
        sid = session["id"]
        found_lock = False
        for project_dir in claude_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for session_file in project_dir.glob(f"{sid}*.jsonl"):
                if session_file.with_suffix(".jsonl.lock").exists():
                    found_lock = True
                    break
            if found_lock:
                break
        if not found_lock:
            age_minutes = (time.time() - session["last_activity"]) / 60
            if age_minutes > 2:
                store.complete(sid)
                finished.append(sid)
    return finished


def _project_dir_to_repo(dir_name: str) -> Optional[str]:
    """Convert Claude Code project directory name back to a path."""
    parts = dir_name.replace("-", os.sep)
    candidate = Path(parts)
    if candidate.exists() and (candidate / ".git").exists():
        return str(candidate)
    return None


def _get_branch(repo_path: str) -> str:
    """Get current git branch for a repo path."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def scan_git_for_agent_commits(repo_path: str, since_minutes: int = 60) -> list[dict]:
    """Find recent commits authored by AI agents."""
    agent_markers = [
        "Co-Authored-By: Claude",
        "Co-Authored-By: Sofer",
        "Co-Authored-By: Cursor",
        "Co-Authored-By: Codex",
        "Co-Authored-By: Devin",
    ]
    try:
        result = subprocess.run(
            [
                "git", "-C", repo_path, "log",
                f"--since={since_minutes} minutes ago",
                "--format=%H|%an|%ae|%s|%b",
                "--no-merges",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 4)
        if len(parts) < 4:
            continue
        body = parts[4] if len(parts) > 4 else ""
        for marker in agent_markers:
            if marker.lower() in (parts[3] + body).lower():
                commits.append({
                    "hash": parts[0][:8],
                    "author": parts[1],
                    "subject": parts[3],
                    "agent": marker.split("By: ")[1],
                })
                break
    return commits
