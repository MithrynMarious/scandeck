"""Tests for the session store."""

import json
import time
from pathlib import Path

from scandeck.store import SessionStore, SessionStatus


def test_register_and_get(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    sid = store.register(tool="claude-code", repo="/tmp/myrepo", branch="main")
    session = store.get(sid)
    assert session is not None
    assert session["tool"] == "claude-code"
    assert session["repo"] == "/tmp/myrepo"
    assert session["status"] == "running"


def test_complete(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    sid = store.register(tool="cursor", repo="/tmp/r")
    assert store.complete(sid, summary="done")
    session = store.get(sid)
    assert session["status"] == "finished"
    assert session["summary"] == "done"


def test_complete_nonexistent(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    assert store.complete("no-such-id") is False


def test_list_sessions_filter(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    s1 = store.register(tool="a", repo="r1")
    s2 = store.register(tool="b", repo="r2")
    store.complete(s2)
    running = store.list_sessions(status="running")
    assert len(running) == 1
    assert running[0]["id"] == s1


def test_prune(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    sid = store.register(tool="a", repo="r")
    store.complete(sid)
    s = store.get(sid)
    s["last_activity"] = time.time() - 100000
    store._save()
    removed = store.prune(max_age_hours=1)
    assert removed == 1
    assert store.get(sid) is None


def test_detect_stuck(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    sid = store.register(tool="a", repo="r")
    s = store.get(sid)
    s["last_activity"] = time.time() - 3600
    store._save()
    stuck = store.detect_stuck(timeout_minutes=30)
    assert sid in stuck
    assert store.get(sid)["status"] == "stuck"


def test_persistence(tmp_path):
    path = tmp_path / "sessions.json"
    store1 = SessionStore(path=path)
    sid = store1.register(tool="a", repo="r", summary="test")
    store2 = SessionStore(path=path)
    assert store2.get(sid) is not None
    assert store2.get(sid)["summary"] == "test"


def test_remove(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    sid = store.register(tool="a", repo="r")
    assert store.remove(sid) is True
    assert store.get(sid) is None
    assert store.remove(sid) is False
