"""Tests for the branch-aware proxy routing logic."""

from scandeck.proxy import resolve_target, load_topology


def test_resolve_simple_service():
    services = {"web": 3000, "api": 8080}
    assert resolve_target("web.localhost", services) == 3000
    assert resolve_target("api.localhost", services) == 8080


def test_resolve_unknown_service():
    services = {"web": 3000}
    assert resolve_target("db.localhost", services) is None


def test_resolve_branch_routing():
    services = {"web": {"default": 3000, "feature-x": 3001}}
    assert resolve_target("web.localhost", services) == 3000
    assert resolve_target("web.feature-x.localhost", services) == 3001


def test_resolve_branch_fallback_to_default():
    services = {"web": {"default": 3000}}
    assert resolve_target("web.unknown-branch.localhost", services) == 3000


def test_resolve_empty_host():
    services = {"web": 3000}
    assert resolve_target("", services) is None


def test_resolve_localhost_only():
    services = {"web": 3000}
    assert resolve_target("localhost", services) is None


def test_load_topology_missing_file(tmp_path):
    result = load_topology(str(tmp_path))
    assert result == {}


def test_load_topology_valid(tmp_path):
    cfg = tmp_path / ".scandeck.json"
    cfg.write_text('{"services": {"web": 3000, "api": 8080}}')
    result = load_topology(str(tmp_path))
    assert result == {"web": 3000, "api": 8080}


def test_load_topology_invalid_json(tmp_path):
    cfg = tmp_path / ".scandeck.json"
    cfg.write_text('not json')
    result = load_topology(str(tmp_path))
    assert result == {}
