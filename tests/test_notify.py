"""Tests for the notification system."""

import time
import threading
from pathlib import Path

from scandeck.store import SessionStore
from scandeck.notify import watch_sessions, _emit


def test_emit_new(capsys):
    session = {"tool": "claude-code", "repo": "/tmp/test", "summary": "", "status": "running"}
    _emit("new", session, desktop=False, callback=None)
    out = capsys.readouterr().out
    assert "[new]" in out
    assert "claude-code" in out


def test_emit_finished(capsys):
    session = {"tool": "cursor", "repo": "/tmp/test", "summary": "auth done", "status": "finished"}
    _emit("finished", session, desktop=False, callback=None)
    out = capsys.readouterr().out
    assert "[done]" in out
    assert "auth done" in out


def test_emit_stuck(capsys):
    session = {"tool": "codex", "repo": "/tmp/test", "summary": "", "status": "stuck"}
    _emit("stuck", session, desktop=False, callback=None)
    out = capsys.readouterr().out
    assert "[stuck]" in out


def test_emit_callback():
    events = []
    session = {"tool": "a", "repo": "r", "summary": "", "status": "running"}
    _emit("new", session, desktop=False, callback=lambda e, s: events.append((e, s["tool"])))
    assert events == [("new", "a")]


def test_emit_long_repo_truncation(capsys):
    session = {"tool": "a", "repo": "A" * 60, "summary": "", "status": "running"}
    _emit("new", session, desktop=False, callback=None)
    out = capsys.readouterr().out
    assert "..." in out


def test_watch_detects_new_session(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    events = []

    def run_watch():
        watch_sessions(
            store, interval=0.2, stuck_timeout=0.01, desktop=False,
            callback=lambda e, s: events.append(e),
        )

    t = threading.Thread(target=run_watch, daemon=True)
    t.start()
    time.sleep(0.3)
    store.register(tool="test", repo="r")
    time.sleep(0.5)

    assert "new" in events


def test_watch_detects_completion(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.json")
    sid = store.register(tool="test", repo="r")
    events = []

    def run_watch():
        watch_sessions(
            store, interval=0.2, stuck_timeout=60, desktop=False,
            callback=lambda e, s: events.append(e),
        )

    t = threading.Thread(target=run_watch, daemon=True)
    t.start()
    time.sleep(0.3)
    store.complete(sid, summary="done")
    time.sleep(0.5)

    assert "finished" in events
