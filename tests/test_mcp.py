"""Tests for the MCP server protocol handling."""

import json

from scandeck.mcp_server import MCPServer


def test_initialize():
    server = MCPServer()
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    })
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "scandeck"


def test_tools_list():
    server = MCPServer()
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    tools = resp["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "session_register" in names
    assert "session_heartbeat" in names
    assert "session_complete" in names
    assert "session_list" in names


def test_session_register_via_mcp():
    server = MCPServer()
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "session_register",
            "arguments": {"tool": "claude-code", "repo": "/tmp/test"},
        },
    })
    text = resp["result"]["content"][0]["text"]
    assert text.startswith("Registered session:")


def test_session_lifecycle_via_mcp():
    server = MCPServer()

    reg = server.handle_request({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": "session_register", "arguments": {"tool": "a", "repo": "r"}},
    })
    sid = reg["result"]["content"][0]["text"].split(": ")[1]

    hb = server.handle_request({
        "jsonrpc": "2.0", "id": 2,
        "method": "tools/call",
        "params": {"name": "session_heartbeat", "arguments": {"session_id": sid}},
    })
    assert "Heartbeat" in hb["result"]["content"][0]["text"]

    comp = server.handle_request({
        "jsonrpc": "2.0", "id": 3,
        "method": "tools/call",
        "params": {"name": "session_complete", "arguments": {"session_id": sid, "summary": "done"}},
    })
    assert "Completed" in comp["result"]["content"][0]["text"]

    ls = server.handle_request({
        "jsonrpc": "2.0", "id": 4,
        "method": "tools/call",
        "params": {"name": "session_list", "arguments": {}},
    })
    sessions = json.loads(ls["result"]["content"][0]["text"])
    assert any(s["id"] == sid and s["status"] == "finished" for s in sessions)


def test_ping():
    server = MCPServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 99, "method": "ping", "params": {}})
    assert resp["id"] == 99
    assert "error" not in resp


def test_unknown_method():
    server = MCPServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 5, "method": "nope", "params": {}})
    assert "error" in resp
