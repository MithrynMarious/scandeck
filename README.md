# ScanDeck

Cross-platform agent session monitor and git worktree manager.

Track AI agent sessions (Claude Code, Cursor, Codex, Devin) across repositories.
Manage git worktrees with automatic config file copying. Get a single dashboard
view of what's running, what finished, and what needs attention.

## Install

```bash
pip install scandeck
```

Requires Python 3.10+. No external dependencies.

## Quick Start

```bash
# See all agent sessions (auto-detects Claude Code)
scandeck status

# Watch for session state changes with desktop notifications
scandeck watch

# Register a session manually
scandeck register claude-code /path/to/repo --branch feature/x

# Create a worktree with config file copying
scandeck wt create feature/new-thing
```

## CLI Reference

### Session monitoring

```bash
scandeck status                    # Show all sessions
scandeck status --json             # JSON output for scripting
scandeck status --filter running   # Filter by status
scandeck register <tool> <repo>    # Register a session manually
scandeck complete <id> --summary   # Mark a session finished
scandeck prune --hours 48          # Remove old finished sessions
scandeck watch                     # Live monitor with notifications
scandeck watch --no-desktop        # CLI output only (no toasts)
```

### Worktree management

```bash
scandeck wt create <branch>        # Create worktree + copy configs
scandeck wt list                   # List all worktrees
scandeck wt remove <branch>        # Remove a worktree
scandeck wt clean                  # Remove stale worktrees (14d default)
```

Worktree creation automatically copies `.env`, `.env.local`, `.claude/`, `.cursor/`,
and `.vscode/` from the main repo into the new worktree.

## MCP Server Setup

ScanDeck runs as an MCP server so AI agents can report their session status.
Any agent that supports MCP can connect and use ScanDeck's tools.

### Claude Code

Add to your project's `.mcp.json` or global MCP config:

```json
{
  "mcpServers": {
    "scandeck": {
      "command": "scandeck",
      "args": ["serve"]
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "scandeck": {
      "command": "scandeck",
      "args": ["serve"]
    }
  }
}
```

### Other MCP-compatible agents

Any agent that supports stdio MCP servers can connect the same way.
Point it at `scandeck serve` as a stdio command.

### Available MCP tools

| Tool | Description |
|------|-------------|
| `session_register` | Register a new session (returns session ID) |
| `session_heartbeat` | Keep a session alive (prevents stuck detection) |
| `session_complete` | Mark a session as finished |
| `session_list` | List all sessions (optional status filter) |
| `worktree_list` | List git worktrees for a repo |
| `worktree_create` | Create a worktree with config copying |

## Configuration

`~/.scandeck/config.json`:

```json
{
  "copy_patterns": [".env", ".env.local", ".claude/", ".cursor/", ".vscode/"],
  "stale_days": 14
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `copy_patterns` | See above | Files/dirs copied into new worktrees |
| `stale_days` | 14 | Days before `wt clean` removes a worktree |

## Session detection

ScanDeck auto-detects Claude Code sessions by scanning `~/.claude/projects/`
for active session lock files. It also scans git history for commits with
`Co-Authored-By` markers from Claude, Cursor, Codex, and Devin.

Sessions transition through four states:

- **running**: Active session detected or registered
- **finished**: Session completed (lock file gone or manually marked)
- **stuck**: No activity for 30 minutes (configurable via `--stuck-timeout`)
- **needs_attention**: Flagged for human review

## Development

```bash
git clone https://github.com/MithrynMarious/scandeck.git
cd scandeck
pip install -e .
python -m pytest tests/ -v
```

## License

MIT. See [LICENSE](LICENSE).
