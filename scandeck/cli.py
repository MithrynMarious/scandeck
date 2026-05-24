"""ScanDeck CLI: agent session monitor + worktree manager."""

import argparse
import json
import sys
import time

from . import __version__
from .store import SessionStore


# ANSI color codes
GREEN = "\033[32m"
BLUE = "\033[34m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

STATUS_COLORS = {
    "running": GREEN,
    "finished": BLUE,
    "stuck": RED,
    "needs_attention": YELLOW,
}


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    return f"{hours}h{minutes}m"


def _print_session_table(sessions: list[dict]):
    if not sessions:
        print("No sessions found.")
        return

    headers = ["ID", "Tool", "Repo", "Branch", "Status", "Duration", "Summary"]
    rows = []
    for s in sessions:
        duration = _format_duration(time.time() - s["start_time"])
        color = STATUS_COLORS.get(s["status"], "")
        repo = s["repo"]
        if len(repo) > 30:
            repo = "..." + repo[-27:]
        rows.append([
            s["id"],
            s["tool"],
            repo,
            s.get("branch", "")[:20],
            f"{color}{s['status']}{RESET}",
            duration,
            s.get("summary", "")[:40],
        ])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            visible_len = len(cell.replace(GREEN, "").replace(BLUE, "")
                             .replace(RED, "").replace(YELLOW, "")
                             .replace(RESET, ""))
            col_widths[i] = max(col_widths[i], visible_len)

    header_line = "  ".join(f"{BOLD}{h:<{col_widths[i]}}{RESET}" for i, h in enumerate(headers))
    separator = "  ".join("-" * w for w in col_widths)
    print(header_line)
    print(separator)
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            visible_len = len(cell.replace(GREEN, "").replace(BLUE, "")
                              .replace(RED, "").replace(YELLOW, "")
                              .replace(RESET, ""))
            padding = col_widths[i] - visible_len
            cells.append(cell + " " * padding)
        print("  ".join(cells))


def cmd_status(args, store: SessionStore):
    from .detect import detect_claude_code_sessions, detect_finished_sessions

    detect_claude_code_sessions(store)
    detect_finished_sessions(store)
    store.detect_stuck(timeout_minutes=args.stuck_timeout)

    sessions = store.list_sessions(status=args.filter)

    if args.json:
        print(json.dumps(sessions, indent=2, default=str))
        return

    print(f"{BOLD}ScanDeck{RESET} {DIM}v{__version__}{RESET}\n")
    _print_session_table(sessions)

    running = len([s for s in sessions if s["status"] == "running"])
    stuck = len([s for s in sessions if s["status"] == "stuck"])
    if running or stuck:
        print(f"\n{GREEN}{running} running{RESET}", end="")
        if stuck:
            print(f"  {RED}{stuck} stuck{RESET}", end="")
        print()


def cmd_register(args, store: SessionStore):
    sid = store.register(
        tool=args.tool,
        repo=args.repo,
        branch=args.branch or "",
        summary=args.summary or "",
    )
    print(f"Registered session: {sid}")


def cmd_complete(args, store: SessionStore):
    if store.complete(args.session_id, summary=args.summary or ""):
        print(f"Completed: {args.session_id}")
    else:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        sys.exit(1)


def cmd_prune(args, store: SessionStore):
    removed = store.prune(max_age_hours=args.hours)
    print(f"Pruned {removed} finished session(s).")


def cmd_worktree(args, store: SessionStore):
    from .worktree import create_worktree, list_worktrees, remove_worktree, clean_stale

    if args.wt_action == "create":
        result = create_worktree(args.branch, repo_path=args.repo)
        if result["ok"]:
            print(f"Created worktree: {result['path']}")
            if result.get("copied"):
                print(f"  Copied: {', '.join(result['copied'])}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    elif args.wt_action == "list":
        worktrees = list_worktrees(repo_path=args.repo)
        if not worktrees:
            print("No worktrees found.")
            return
        for wt in worktrees:
            branch = wt.get("branch", "(detached)")
            print(f"  {branch:<30s}  {wt['path']}")

    elif args.wt_action == "remove":
        result = remove_worktree(args.branch, repo_path=args.repo, force=args.force)
        if result["ok"]:
            print(f"Removed: {result['removed']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    elif args.wt_action == "clean":
        removed = clean_stale(repo_path=args.repo)
        if removed:
            print(f"Cleaned {len(removed)} stale worktree(s):")
            for p in removed:
                print(f"  {p}")
        else:
            print("No stale worktrees found.")


def cmd_watch(args, store: SessionStore):
    from .notify import watch_sessions
    watch_sessions(
        store,
        interval=args.interval,
        stuck_timeout=args.stuck_timeout,
        desktop=not args.no_desktop,
    )


def cmd_serve(args, store: SessionStore):
    from .mcp_server import run_stdio
    run_stdio()


def main():
    parser = argparse.ArgumentParser(
        prog="scandeck",
        description="ScanDeck: agent session monitor + worktree manager",
    )
    parser.add_argument("--version", action="version", version=f"scandeck {__version__}")
    sub = parser.add_subparsers(dest="command")

    # status
    sp = sub.add_parser("status", help="Show agent sessions")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.add_argument("--filter", choices=["running", "finished", "stuck", "needs_attention"])
    sp.add_argument("--stuck-timeout", type=float, default=30.0,
                    help="Minutes before a session is marked stuck (default: 30)")

    # register
    sp = sub.add_parser("register", help="Register an agent session")
    sp.add_argument("tool", help="Agent tool name (claude-code, cursor, codex, etc.)")
    sp.add_argument("repo", help="Repository path or name")
    sp.add_argument("--branch", help="Git branch")
    sp.add_argument("--summary", help="Session description")

    # complete
    sp = sub.add_parser("complete", help="Mark a session as finished")
    sp.add_argument("session_id", help="Session ID")
    sp.add_argument("--summary", help="Completion summary")

    # prune
    sp = sub.add_parser("prune", help="Remove old finished sessions")
    sp.add_argument("--hours", type=float, default=24.0,
                    help="Remove finished sessions older than N hours (default: 24)")

    # watch
    sp = sub.add_parser("watch", help="Watch sessions and notify on state changes")
    sp.add_argument("--interval", type=float, default=5.0,
                    help="Seconds between polls (default: 5)")
    sp.add_argument("--stuck-timeout", type=float, default=30.0,
                    help="Minutes before a session is marked stuck (default: 30)")
    sp.add_argument("--no-desktop", action="store_true",
                    help="Disable desktop notifications (CLI output only)")

    # serve
    sub.add_parser("serve", help="Run MCP server on stdin/stdout")

    # worktree
    sp = sub.add_parser("worktree", aliases=["wt"], help="Git worktree management")
    wt_sub = sp.add_subparsers(dest="wt_action")

    wt_create = wt_sub.add_parser("create", help="Create a worktree")
    wt_create.add_argument("branch", help="Branch name")
    wt_create.add_argument("--repo", help="Repository path (default: cwd)")

    wt_list = wt_sub.add_parser("list", help="List worktrees")
    wt_list.add_argument("--repo", help="Repository path (default: cwd)")

    wt_remove = wt_sub.add_parser("remove", help="Remove a worktree")
    wt_remove.add_argument("branch", help="Branch name")
    wt_remove.add_argument("--repo", help="Repository path (default: cwd)")
    wt_remove.add_argument("--force", action="store_true")

    wt_clean = wt_sub.add_parser("clean", help="Remove stale worktrees")
    wt_clean.add_argument("--repo", help="Repository path (default: cwd)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    store = SessionStore()

    commands = {
        "status": cmd_status,
        "register": cmd_register,
        "complete": cmd_complete,
        "prune": cmd_prune,
        "watch": cmd_watch,
        "serve": cmd_serve,
        "worktree": cmd_worktree,
        "wt": cmd_worktree,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args, store)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
