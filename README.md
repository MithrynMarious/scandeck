# ScanDeck

Cross-platform agent session monitor and git worktree manager.

Track AI agent sessions (Claude Code, Cursor, Codex, Devin) across repositories.
Manage git worktrees with automatic config file copying. Get a single dashboard
view of what's running, what finished, and what needs attention.

## Install

```bash
pip install scandeck
```

## CLI Usage

```bash
# See all agent sessions
scandeck status

# JSON output for scripting
scandeck status --json

# Register a session manually
scandeck register claude-code /path/to/repo --branch feature/x --summary "Building auth"

# Mark a session complete
scandeck complete abc12345 --summary "Auth module shipped"

# Prune old finished sessions
scandeck prune --hours 48
```

## Worktree Management

```bash
# Create a worktree with config file copying
scandeck worktree create feature/new-thing --repo /path/to/repo

# List all worktrees
scandeck wt list

# Remove a worktree
scandeck wt remove feature/old-thing

# Clean stale worktrees (default: older than 14 days)
scandeck wt clean
```

Worktree creation automatically copies `.env`, `.env.local`, `.claude/`, `.cursor/`,
and `.vscode/` from the main repo. Configure patterns in `~/.scandeck/config.json`.

## MCP Server

Run ScanDeck as an MCP server so AI agents can report their status:

```bash
scandeck serve
```

Agents connect via stdio and can call tools like `session_register`, `session_heartbeat`,
`session_complete`, and `session_list`.

## Configuration

`~/.scandeck/config.json`:

```json
{
  "copy_patterns": [".env", ".env.local", ".claude/", ".cursor/", ".vscode/"],
  "stale_days": 14
}
```

## License

MIT. See [LICENSE](LICENSE).
