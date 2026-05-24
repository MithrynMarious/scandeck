"""Git worktree manager with conventions."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional


DEFAULT_COPY_PATTERNS = [
    ".env",
    ".env.local",
    ".claude/",
    ".cursor/",
    ".vscode/",
]


def load_config() -> dict:
    cfg_path = Path.home() / ".scandeck" / "config.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"copy_patterns": DEFAULT_COPY_PATTERNS, "stale_days": 14}


def create_worktree(
    branch: str,
    repo_path: Optional[str] = None,
    base_branch: str = "main",
) -> dict:
    """Create a worktree for a branch with config file copying."""
    repo = Path(repo_path) if repo_path else Path.cwd()
    if not (repo / ".git").exists():
        return {"ok": False, "error": f"Not a git repo: {repo}"}

    worktree_dir = repo.parent / f"{repo.name}-worktrees" / branch.replace("/", "-")
    if worktree_dir.exists():
        return {"ok": False, "error": f"Worktree already exists: {worktree_dir}"}

    try:
        subprocess.run(
            ["git", "-C", str(repo), "branch", branch, base_branch],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    result = subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", str(worktree_dir), branch],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip()}

    cfg = load_config()
    copied = []
    for pattern in cfg.get("copy_patterns", DEFAULT_COPY_PATTERNS):
        src = repo / pattern
        dst = worktree_dir / pattern
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            copied.append(pattern)
        elif src.is_dir():
            if dst.exists():
                shutil.rmtree(str(dst))
            shutil.copytree(str(src), str(dst))
            copied.append(pattern)

    return {
        "ok": True,
        "path": str(worktree_dir),
        "branch": branch,
        "copied": copied,
    }


def list_worktrees(repo_path: Optional[str] = None) -> list[dict]:
    """List all worktrees for a repo."""
    repo = Path(repo_path) if repo_path else Path.cwd()
    result = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return []

    worktrees = []
    current = {}
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1][:8]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True
    if current:
        worktrees.append(current)
    return worktrees


def remove_worktree(
    branch: str,
    repo_path: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Remove a worktree by branch name."""
    repo = Path(repo_path) if repo_path else Path.cwd()
    worktrees = list_worktrees(str(repo))
    target = None
    for wt in worktrees:
        if wt.get("branch") == branch:
            target = wt
            break

    if not target:
        return {"ok": False, "error": f"No worktree found for branch: {branch}"}

    cmd = ["git", "-C", str(repo), "worktree", "remove", target["path"]]
    if force:
        cmd.append("--force")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip()}

    return {"ok": True, "removed": target["path"], "branch": branch}


def clean_stale(repo_path: Optional[str] = None) -> list[str]:
    """Remove worktrees older than the configured stale threshold."""
    import time

    repo = Path(repo_path) if repo_path else Path.cwd()
    cfg = load_config()
    stale_seconds = cfg.get("stale_days", 14) * 86400
    cutoff = time.time() - stale_seconds

    worktrees = list_worktrees(str(repo))
    removed = []
    for wt in worktrees:
        wt_path = Path(wt["path"])
        if wt_path == repo:
            continue
        if not wt_path.exists():
            continue
        mtime = wt_path.stat().st_mtime
        if mtime < cutoff:
            result = remove_worktree(
                wt.get("branch", ""), str(repo), force=True
            )
            if result.get("ok"):
                removed.append(wt["path"])
    return removed
