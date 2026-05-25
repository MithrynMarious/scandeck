"""Quick launcher: list workspaces and open in editor."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .store import SessionStore
from .worktree import list_worktrees


def list_workspaces(store: SessionStore, scan_paths: Optional[list[str]] = None) -> list[dict]:
    """Build a list of available workspaces from sessions, worktrees, and scan paths."""
    workspaces = []
    seen_paths = set()

    for s in store.list_sessions():
        repo = s["repo"]
        if repo and repo not in seen_paths and Path(repo).exists():
            seen_paths.add(repo)
            workspaces.append({
                "path": repo,
                "branch": s.get("branch", ""),
                "session": s["id"],
                "status": s["status"],
                "tool": s["tool"],
            })

    if scan_paths:
        for scan_path in scan_paths:
            root = Path(scan_path)
            if not root.is_dir():
                continue
            for child in root.iterdir():
                if child.is_dir() and (child / ".git").exists():
                    p = str(child)
                    if p not in seen_paths:
                        seen_paths.add(p)
                        branch = _get_branch(p)
                        workspaces.append({
                            "path": p,
                            "branch": branch,
                            "session": None,
                            "status": None,
                            "tool": None,
                        })

    return workspaces


def pick_workspace(workspaces: list[dict]) -> Optional[dict]:
    """Interactive terminal picker for workspaces."""
    if not workspaces:
        print("No workspaces found.")
        return None

    print(f"\n  {'#':<4} {'Status':<10} {'Tool':<12} {'Branch':<20} Path")
    print(f"  {'─'*4} {'─'*10} {'─'*12} {'─'*20} {'─'*40}")

    for i, ws in enumerate(workspaces, 1):
        status = ws["status"] or "─"
        tool = ws["tool"] or "─"
        branch = ws["branch"][:18] or "─"
        path = ws["path"]
        if len(path) > 40:
            path = "..." + path[-37:]
        print(f"  {i:<4} {status:<10} {tool:<12} {branch:<20} {path}")

    print()
    try:
        choice = input("  Select workspace (number, or q to quit): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if choice.lower() in ("q", "quit", ""):
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(workspaces):
            return workspaces[idx]
    except ValueError:
        pass
    print("  Invalid selection.")
    return None


def open_in_editor(workspace: dict, editor: str = "code"):
    """Open a workspace in the specified editor."""
    path = workspace["path"]
    editors = {
        "code": ["code", path],
        "cursor": ["cursor", path],
        "claude": ["claude", path],
        "vim": ["vim", path],
        "nvim": ["nvim", path],
    }

    cmd = editors.get(editor, [editor, path])

    try:
        if sys.platform == "win32":
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS)
        else:
            subprocess.Popen(cmd, start_new_session=True)
        print(f"  Opened {path} in {editor}")
    except FileNotFoundError:
        print(f"  Editor not found: {editor}")
        print(f"  Available: {', '.join(editors.keys())}")


def run_launcher(store: SessionStore, scan_paths: Optional[list[str]] = None, editor: str = "code"):
    """Run the interactive workspace launcher."""
    workspaces = list_workspaces(store, scan_paths)
    ws = pick_workspace(workspaces)
    if ws:
        open_in_editor(ws, editor)


def _get_branch(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
