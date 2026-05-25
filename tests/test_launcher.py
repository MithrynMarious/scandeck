"""Tests for the workspace launcher."""

import subprocess
from pathlib import Path

from scandeck.store import SessionStore
from scandeck.launcher import list_workspaces


def test_list_workspaces_from_sessions(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    store.register(tool="claude", repo=str(repo_dir), branch="main")
    workspaces = list_workspaces(store)
    assert len(workspaces) == 1
    assert workspaces[0]["tool"] == "claude"
    assert workspaces[0]["branch"] == "main"


def test_list_workspaces_deduplicates(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    store.register(tool="claude", repo=str(repo_dir), branch="main")
    store.register(tool="cursor", repo=str(repo_dir), branch="main")
    workspaces = list_workspaces(store)
    assert len(workspaces) == 1


def test_list_workspaces_scan_paths(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    repo_a = repos_dir / "alpha"
    repo_a.mkdir()
    (repo_a / ".git").mkdir()
    repo_b = repos_dir / "beta"
    repo_b.mkdir()
    (repo_b / ".git").mkdir()
    not_repo = repos_dir / "notes"
    not_repo.mkdir()

    workspaces = list_workspaces(store, scan_paths=[str(repos_dir)])
    paths = [w["path"] for w in workspaces]
    assert str(repo_a) in paths
    assert str(repo_b) in paths
    assert str(not_repo) not in paths


def test_list_workspaces_nonexistent_scan_path(tmp_path):
    store = SessionStore(path=tmp_path / "s.json")
    workspaces = list_workspaces(store, scan_paths=[str(tmp_path / "nope")])
    assert workspaces == []
