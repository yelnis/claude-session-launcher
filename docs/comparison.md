English | [日本語](comparison.ja.md) · [Back to README](../README.md)

# Compared with other approaches

This is what could be confirmed as of November 2026. Some official features are research previews and may change.

## A. This tool (tmux + ttyd + `/remote-control`)

**Pros**
- IDs, ports and work directories are fixed, so the same layout comes back after a reboot
- Sessions run in your existing clones and worktrees
- ttyd gives you the real terminal in the browser, so interactive steps (trust dialog, `/login`) work
- Starts unattended from cron `@reboot`
- Small enough to change yourself

**Cons**
- You maintain it yourself
- You must take care of ttyd authentication, the firewall and ports
- Readiness is detected from text on the screen, so a Claude Code UI change can break it
- When the login expires, Remote Control disconnects (see [Notes](reference.md#notes))
- Copy and paste through tmux / ttyd has quirks

## B. The official agent view (`claude --bg` / `claude agents`)

A single screen that lists and controls background sessions (research preview).

**Pros**
- Runs several sessions in parallel without tmux or ttyd
- States (running / waiting for input / done / failed / stopped) are shown with colors and icons
- `claude attach` / `logs` / `stop` / `respawn`
- `claude agents --json` is readable from scripts
- Moves to a separate git worktree before editing, so parallel sessions rarely touch the same files

**Cons**
- Research preview; the UI and shortcuts may change
- Running sessions stop when the machine shuts down and do not start again by themselves (attaching or replying resumes the saved conversation)
- A session that is done or waiting and not attached for about an hour is stopped (the conversation is kept; pinning keeps it alive)
- Automatic worktree isolation is a different idea from "one role per existing clone"
- Each session uses your subscription quota separately
- Does not start in a directory whose trust dialog has not been accepted
- **Unconfirmed:** whether sessions started by this tool appear in that list

## C. Remote Control server mode (`claude remote-control`)

One process waits for connections from claude.ai/code or the mobile app and creates a session for each.

**Pros**
- One process serves several sessions (32 by default)
- `--spawn worktree` gives each session its own worktree
- No ttyd ports to manage; works from a phone
- Within about 4 hours after stopping, `--continue` / `--session-id` brings it back

**Cons**
- The terminal only waits for connections; it is not for local interaction
- Not suited to fixed role names and work directories (the choice is `same-dir` or `worktree`)
- The process exits after about 10 minutes without network
- Long-lived tokens from `claude setup-token` or `CLAUDE_CODE_OAUTH_TOKEN` cannot establish Remote Control; `claude auth login` is required
- Not available with API key authentication, Bedrock / Vertex / Foundry, or `ANTHROPIC_BASE_URL` pointing to another host

## D. Third-party tools (Claude Squad, CCManager, ccdeck, claude-tmux, ...)

**Pros**
- A management UI for several sessions already exists
- Some rebuild tmux sessions after a reboot and restore conversations with `claude -r` (ccdeck)
- Nothing to maintain yourself

**Cons**
- Most assume "new task, new worktree, new session", which fits poorly with existing clones and fixed roles
- None was found that covers browser access through ttyd, automatic `/remote-control` and unattended start from cron `@reboot` together
- One more external dependency

## Which one to use

| Goal | Good fit |
|---|---|
| Fixed roles and work directories that come back after a reboot | A (this tool) |
| One screen showing the state of parallel sessions | B (agent view). Using it together with A is untested |
| Any number of sessions from the browser or a phone | C (server mode) |
| A quick new session with its own worktree per task | B or D |

## References

- [Manage multiple agents with agent view](https://code.claude.com/docs/en/agent-view)
- [Continue local sessions from any device with Remote Control](https://code.claude.com/docs/en/remote-control)
