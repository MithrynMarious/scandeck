"""Tests for multi-agent coordination."""

import time

from scandeck.store import SessionStore
from scandeck.coordination import (
    find_overlapping_sessions,
    detect_conflicts,
    update_file_tracking,
    detect_file_conflicts,
)


def test_find_overlapping_same_repo(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    store.register(tool="claude", repo="/tmp/myrepo", branch="main")
    store.register(tool="cursor", repo="/tmp/myrepo", branch="main")
    matches = find_overlapping_sessions(store, "/tmp/myrepo", "main")
    assert len(matches) == 2


def test_find_overlapping_different_branch(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    store.register(tool="claude", repo="/tmp/repo", branch="main")
    store.register(tool="cursor", repo="/tmp/repo", branch="feature/x")
    matches = find_overlapping_sessions(store, "/tmp/repo", "main")
    assert len(matches) == 1


def test_find_overlapping_no_branch_filter(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    store.register(tool="claude", repo="/tmp/repo", branch="main")
    store.register(tool="cursor", repo="/tmp/repo", branch="feature/x")
    matches = find_overlapping_sessions(store, "/tmp/repo")
    assert len(matches) == 2


def test_find_overlapping_windows_paths(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    store.register(tool="claude", repo="C:\\Users\\dev\\repo")
    matches = find_overlapping_sessions(store, "C:/Users/dev/repo")
    assert len(matches) == 1


def test_detect_conflicts_none(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    store.register(tool="claude", repo="/tmp/a")
    store.register(tool="cursor", repo="/tmp/b")
    assert detect_conflicts(store) == []


def test_detect_conflicts_same_repo(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    store.register(tool="claude", repo="/tmp/repo", branch="main")
    store.register(tool="cursor", repo="/tmp/repo", branch="main")
    conflicts = detect_conflicts(store)
    assert len(conflicts) == 1
    assert len(conflicts[0]["sessions"]) == 2
    assert conflicts[0]["risk"] == "high"


def test_file_tracking(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    sid = store.register(tool="claude", repo="/tmp/repo")
    assert update_file_tracking(store, sid, ["src/main.py", "src/utils.py"])
    session = store.get(sid)
    assert session["tracked_files"] == ["src/main.py", "src/utils.py"]


def test_file_tracking_nonexistent(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    assert update_file_tracking(store, "nope", ["a.py"]) is False


def test_detect_file_conflicts(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    s1 = store.register(tool="claude", repo="/tmp/repo")
    s2 = store.register(tool="cursor", repo="/tmp/repo")
    update_file_tracking(store, s1, ["src/main.py", "src/config.py"])
    update_file_tracking(store, s2, ["src/main.py", "tests/test.py"])
    conflicts = detect_file_conflicts(store)
    assert len(conflicts) == 1
    assert "src/main.py" in conflicts[0]["file"]


def test_detect_file_conflicts_none(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    s1 = store.register(tool="claude", repo="/tmp/repo")
    s2 = store.register(tool="cursor", repo="/tmp/repo")
    update_file_tracking(store, s1, ["src/a.py"])
    update_file_tracking(store, s2, ["src/b.py"])
    assert detect_file_conflicts(store) == []
