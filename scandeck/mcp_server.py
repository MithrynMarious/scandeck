"""ScanDeck MCP server: agents report session status via stdio."""

import json
import sys
import time
from typing import Any, Optional

from .store import SessionStore


PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "session_register",
        "description": "Register a new agent session. Returns the session ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "description": "Agent tool name (claude-code, cursor, codex, etc.)",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository path or name",
                },
                "branch": {
                    "type": "string",
                    "description": "Git branch name",
                    "default": "",
                },
                "summary": {
                    "type": "string",
                    "description": "What the session is working on",
                    "default": "",
                },
            },
            "required": ["tool", "repo"],
        },
    },
    {
        "name": "session_heartbeat",
        "description": "Send a heartbeat for an active session. Keeps it from being marked stuck.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID from registration",
                },
                "summary": {
                    "type": "string",
                    "description": "Updated status summary",
                    "default": "",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "session_complete",
        "description": "Mark a session as finished.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to complete",
                },
                "summary": {
                    "type": "string",
                    "description": "Completion summary",
                    "default": "",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "session_list",
        "description": "List all tracked sessions, optionally filtered by status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: running, finished, stuck, needs_attention",
                    "enum": ["running", "finished", "stuck", "needs_attention"],
                },
            },
        },
    },
    {
        "name": "worktree_list",
        "description": "List git worktrees for a repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository path (default: server cwd)",
                    "default": "",
                },
            },
        },
    },
    {
        "name": "worktree_create",
        "description": "Create a git worktree with automatic config file copying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch name for the worktree",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository path (default: server cwd)",
                    "default": "",
                },
                "base_branch": {
                    "type": "string",
                    "description": "Base branch to create from (default: main)",
                    "default": "main",
                },
            },
            "required": ["branch"],
        },
    },
]


class MCPServer:
    def __init__(self):
        self.store = SessionStore()
        self._request_id = 0

    def handle_request(self, msg: dict) -> Optional[dict]:
        method = msg.get("method", "")
        params = msg.get("params", {})
        msg_id = msg.get("id")

        if method == "initialize":
            return self._respond(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "scandeck", "version": "0.1.0"},
            })

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return self._respond(msg_id, {"tools": TOOLS})

        if method == "tools/call":
            return self._handle_tool_call(msg_id, params)

        if method == "ping":
            return self._respond(msg_id, {})

        return self._error(msg_id, -32601, f"Method not found: {method}")

    def _handle_tool_call(self, msg_id: Any, params: dict) -> dict:
        name = params.get("name", "")
        args = params.get("arguments", {})

        try:
            if name == "session_register":
                sid = self.store.register(
                    tool=args["tool"],
                    repo=args["repo"],
                    branch=args.get("branch", ""),
                    summary=args.get("summary", ""),
                )
                return self._tool_result(msg_id, f"Registered session: {sid}")

            elif name == "session_heartbeat":
                kwargs = {}
                if args.get("summary"):
                    kwargs["summary"] = args["summary"]
                ok = self.store.update(args["session_id"], **kwargs)
                if ok:
                    return self._tool_result(msg_id, f"Heartbeat: {args['session_id']}")
                return self._tool_result(msg_id, f"Session not found: {args['session_id']}", is_error=True)

            elif name == "session_complete":
                ok = self.store.complete(args["session_id"], summary=args.get("summary", ""))
                if ok:
                    return self._tool_result(msg_id, f"Completed: {args['session_id']}")
                return self._tool_result(msg_id, f"Session not found: {args['session_id']}", is_error=True)

            elif name == "session_list":
                sessions = self.store.list_sessions(status=args.get("status"))
                return self._tool_result(msg_id, json.dumps(sessions, indent=2, default=str))

            elif name == "worktree_list":
                from .worktree import list_worktrees
                worktrees = list_worktrees(repo_path=args.get("repo") or None)
                return self._tool_result(msg_id, json.dumps(worktrees, indent=2))

            elif name == "worktree_create":
                from .worktree import create_worktree
                result = create_worktree(
                    args["branch"],
                    repo_path=args.get("repo") or None,
                    base_branch=args.get("base_branch", "main"),
                )
                if result["ok"]:
                    return self._tool_result(msg_id, json.dumps(result, indent=2))
                return self._tool_result(msg_id, result["error"], is_error=True)

            else:
                return self._tool_result(msg_id, f"Unknown tool: {name}", is_error=True)

        except Exception as e:
            return self._tool_result(msg_id, f"Error: {e}", is_error=True)

    def _respond(self, msg_id: Any, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error(self, msg_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    def _tool_result(self, msg_id: Any, text: str, is_error: bool = False) -> dict:
        return self._respond(msg_id, {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        })


def run_stdio():
    """Run the MCP server on stdin/stdout."""
    server = MCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle_request(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
