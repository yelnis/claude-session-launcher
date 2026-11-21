English | [日本語](README.ja.md)

# claude-session-launcher

> **TL;DR** — This script starts several Claude Code sessions at once and makes each of them reachable through `/remote-control`. I wrote it because I wanted my development sessions to come back automatically when Linux reboots (cron `@reboot`). While at it, it also names each session and remembers its work directory and last conversation.

`launch_claude` starts several named [Claude Code](https://code.claude.com/docs) sessions in tmux, optionally serves each one in the browser with [ttyd](https://github.com/tsl0922/ttyd), and sends `/remote-control` once the session is ready.

- Give a session an ID (`writer`, `coder`, ...) and it remembers its work directory, port and conversation mode.
- `open` registers a session automatically; `start` brings registered sessions back.
- Sessions flagged `autostart` come back after a reboot with one cron line.
- `open --once` gives you a throwaway session that cleans up after itself.

It is a single Python file that uses only the standard library. It is also 100% written by Claude Code (the human wrote the spec and did the complaining).

> **Warning: ttyd has no authentication by default.** Anyone who can reach the port can operate your terminal. See [Security](#security).

## Requirements

- `python3` 3.8 or newer (standard library only; nothing to `pip install`). If Python is missing, install it first, e.g. `sudo dnf install python3` or `sudo apt install python3`.
- `tmux`
- `ttyd` (not needed if you only use tmux sessions: `--without-ttyd`)
- Claude Code, logged in with `claude auth login` if you use Remote Control

Linux is the main target. macOS may work but is **untested**.

## Install

```bash
mkdir -p ~/.local/bin
curl -fsSL https://raw.githubusercontent.com/yelnis/claude-session-launcher/main/launch_claude \
  -o ~/.local/bin/launch_claude && chmod +x ~/.local/bin/launch_claude
```

- To update, run the same command again.
- For a fixed version, replace `main` in the URL with a tag.
- `~/.local/bin` must be in your `PATH`. If it is not, add this to your shell profile:

  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```

## Quick start

```bash
cd ~/projects/site
launch_claude open web            # new conversation, registered as "web", served by ttyd
launch_claude list                # see the URL
launch_claude stop web            # stop it; the registration stays
launch_claude start web           # start it again with the saved directory and port
launch_claude set web --autostart --mode continue   # bring it back after a reboot
```

Then add one line to your crontab (`crontab -e`):

```cron
@reboot $HOME/.local/bin/launch_claude start --autostart
```

Cron runs with a minimal `PATH`, so write the full path as shown.

## Commands

```
launch_claude                          show help and exit with status 1; starts nothing
launch_claude help | -h | --help       show help
launch_claude --version                show the version
launch_claude open [options] [<id>] [dir]   open a new or registered agent; registers it unless --once
launch_claude start <id>...            start registered agents
launch_claude start --autostart        start every agent with autostart=1
launch_claude <id>                     shortcut for: start <id>
launch_claude stop [<id>...]           stop agents, keep registrations; no id = everything running
launch_claude list [--running|--autostart]
launch_claude add <id> [options]       register only (does not start)
launch_claude set <id> [options]       change saved settings
launch_claude forget <id>              remove the registration
```

IDs match `^[A-Za-z0-9][A-Za-z0-9_-]*$`. These words are reserved and cannot be IDs: `all`, `start`, `stop`, `open`, `add`, `set`, `forget`, `list`, `help`.

### open

```bash
launch_claude open review                  # register "review" in the current directory and start it
launch_claude open review ~/work/repo      # ... in another directory
launch_claude open --resume review         # resume the last conversation of "review"
launch_claude open -c review               # continue the latest conversation in the directory, rename it to "review"
launch_claude open --without-ttyd review   # tmux only, no port
launch_claude open --port 7710 review      # choose the ttyd port
launch_claude open --once                  # throwaway session
launch_claude open --once --with-ttyd tmp  # throwaway session with ttyd and an ID
```

| Option | Meaning |
|---|---|
| `--resume` | Resume the last conversation of this agent. Applies to this launch only |
| `--continue`, `-c` | Continue the latest conversation in the work directory and rename it to `<id>`. Refused if another agent is running in the same directory |
| `--once` | Always a new conversation, never registered. Without `<id>` the ID is `once-HHMMSS`. No ttyd by default. tmux and ttyd are cleaned up when claude exits. Cannot be combined with `--resume`, `--continue` or `--autostart` |
| `--with-ttyd` / `--without-ttyd` (`--no-ttyd`) | Serve with ttyd, or tmux only |
| `--port <n>` | ttyd port (implies ttyd). Default: the first free port in `port_min`–`port_max` |
| `--dir <path>` | Work directory (same as the second positional argument). Default: the current directory |
| `--autostart` | Set `autostart=1` |

- A new ID is registered with the directory, ttyd setting and port. The port is saved so that the URL stays the same.
- A registered ID uses its saved settings. If you pass `--dir`, `--port`, `--with-ttyd`/`--without-ttyd` or `--autostart`, the new value is saved and reported.
- `open` starts a **new conversation** unless you pass `--resume` or `--continue`. These two flags affect this launch only; what `start` does is set with `--mode` (see below).
- If the agent is already running, `open` reports it and does nothing.

### add / set

```bash
launch_claude add coder --dir ~/work/repo --port 7683 --mode continue --autostart
launch_claude set coder --no-autostart
launch_claude set coder --mode resume
```

Options: `--dir <path>`, `--port <n>`, `--with-ttyd` / `--without-ttyd`, `--mode new|resume|continue`, `--autostart` / `--no-autostart`.

### start

- You must name the targets: IDs or `--autostart`. `start` alone is an error.
- Agents that are already running are skipped.
- If the saved directory no longer exists, the agent is skipped with a warning (there is no fallback to `$HOME`).
- The saved ttyd port must be free; ports held by other programs are never killed.

### stop / forget

- `stop <id>...` stops tmux and ttyd for those agents. `stop` alone stops everything this tool started, including `--once` sessions. Registrations are kept.
- `forget <id>` deletes the registration and its state. Stop the agent first.

### list

```
ID       STATUS   ACCESS                   DIR      MODE      AUTO  LAST
coder    stopped  -                        ~/repo   continue  *     11/16 18:30
review   stopped  -                        ~/repo   new       -     11/15 10:12
writer   running  http://192.0.2.10:7682   ~/docs   continue  *     11/17 09:00
once-1   running  tmux only (once)         ~/tmp    -         -     11/17 14:00
```

Registered agents and running `--once` sessions appear in one table. `--running` shows only running sessions, `--autostart` only agents with `autostart=1`. A directory that no longer exists is marked `(!)`.

## Conversation modes

| Mode | What is started |
|---|---|
| `new` (default) | A new conversation named after the ID (`claude --session-id <uuid> --name <id>`). The UUID is remembered |
| `resume` | The remembered conversation (`claude --resume <uuid>`), if its transcript still exists. Otherwise a new conversation is started and this is reported |
| `continue` | The latest conversation in the work directory (`claude --continue`), then `/rename <id>`. A new one if there is none |

`resume` refers to the conversation this tool last started in `new` mode for that ID. Conversations are never resumed by name.

## Autostart

There are no profiles and no `all`. "Start this after a reboot" is expressed by one flag per agent:

```bash
launch_claude set writer --autostart      # include
launch_claude set writer --no-autostart   # exclude
launch_claude list --autostart            # what will start
launch_claude start --autostart           # start them now (this is what cron runs)
```

For an ad-hoc combination, list the IDs: `launch_claude start writer coder`. An agent registered by `open` has `autostart=0` unless you pass `--autostart`.

ttyd and autostart are independent settings, so an agent without ttyd (tmux only) can be autostarted too.

```bash
launch_claude open --without-ttyd --autostart myproj   # a new agent
launch_claude set myproj --without-ttyd --autostart    # a registered agent
```

After a reboot only the tmux session is started and no port is used. `/remote-control` is still sent, since it does not depend on ttyd. To see the terminal, use `tmux attach -t myproj`. Note that `--without-ttyd` drops the saved port; if you switch back to ttyd later and want the same URL, pass `--port <n>`.

## Files

| What | Where |
|---|---|
| Program | `~/.local/bin/launch_claude` |
| Settings and registrations (yours to edit) | `${XDG_CONFIG_HOME:-~/.config}/launch_claude/config` and `agents/<id>.conf` |
| Runtime state (last conversation UUID, last start time) | `${XDG_STATE_HOME:-~/.local/state}/launch_claude/<id>.state` |

Everything works without any of these files. Both kinds of settings file are INI files; see [`examples/config.example`](examples/config.example) and [`examples/agents/example.conf`](examples/agents/example.conf).

`config` keys (section `[launch_claude]`):

| Key | Default | Meaning |
|---|---|---|
| `claude_config_dir` | not set | Value for `CLAUDE_CONFIG_DIR`. If it is not set here, the variable from your environment is used; if that is empty too, Claude Code's default applies |
| `port_min`, `port_max` | `7700`, `7799` | Port range for automatically chosen ttyd ports |
| `remote_control` | `1` | Send `/remote-control <id>` after start. Environment variable `REMOTE_CONTROL=0` overrides it |
| `ttyd_credential` | not set | `user:password` for ttyd basic auth. Environment variable `TTYD_CREDENTIAL` overrides it |

`agents/<id>.conf` keys (section `[agent]`): `dir`, `ttyd` (1/0), `port`, `mode` (`new`/`resume`/`continue`), `autostart` (1/0).

## Security

- **ttyd is started without authentication unless you configure it.** Anyone who can connect to the port gets your terminal, with your permissions. Keep the ports behind a firewall or on a trusted network.
- To require a password, set `TTYD_CREDENTIAL=user:password` in the environment, or `ttyd_credential` in `config` (then `chmod 600` the file; a warning is shown otherwise). It is passed to `ttyd -c`, so it is visible in the process list to other users of the same machine, and basic auth over plain HTTP is not encrypted.
- To make an agent trusted without a prompt, the directory is marked as trusted in Claude Code's `.claude.json`. Only open directories you trust.

## Help text

```
Usage:
  launch_claude open [options] [<id>] [dir]
                                         open a new or registered agent; registers it unless --once
  launch_claude start <id>...            start registered agents
  launch_claude start --autostart        start every agent with autostart=1 (use this from cron @reboot)
  launch_claude <id>                     shortcut for: start <id>
  launch_claude stop [<id>...]           stop agents, keep registrations; no id = everything running
  launch_claude list [--running|--autostart]
  launch_claude add <id> [options]       register only (does not start)
  launch_claude set <id> [options]       change saved settings
  launch_claude forget <id>              remove the registration
  launch_claude help | -h | --help       show this help
  launch_claude --version                show the version

open options:
  --resume           resume the last conversation of this agent (this launch only)
  --continue, -c     continue the latest conversation in the directory and rename it to <id>
  --once             throwaway: always a new conversation, not registered, auto id (once-HHMMSS)
                     if <id> is omitted, no ttyd by default, cleaned up when claude exits
  --with-ttyd        serve the session with ttyd
  --without-ttyd     tmux only, no port (alias: --no-ttyd)
  --port <n>         ttyd port (implies ttyd; default: first free port in the configured range)
  --dir <path>       work directory (same as the 2nd positional argument; default: current dir)
  --autostart        mark the agent for 'start --autostart'

add / set options:
  --dir <path>  --port <n>  --with-ttyd | --without-ttyd
  --mode new|resume|continue             conversation used by 'start' (default: new)
  --autostart | --no-autostart

Files:
  settings   ${XDG_CONFIG_HOME:-~/.config}/launch_claude/config
  agents     ${XDG_CONFIG_HOME:-~/.config}/launch_claude/agents/<id>.conf
  state      ${XDG_STATE_HOME:-~/.local/state}/launch_claude/

Environment:
  REMOTE_CONTROL=0       do not send /remote-control after start
  TTYD_CREDENTIAL=u:p    protect ttyd with basic auth (ttyd -c)
```

## Compared with other approaches

This is what could be confirmed as of November 2026. Some official features are research previews and may change.

### A. This tool (tmux + ttyd + `/remote-control`)

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
- When the login expires, Remote Control disconnects (see [Notes](#notes))
- Copy and paste through tmux / ttyd has quirks

### B. The official agent view (`claude --bg` / `claude agents`)

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

### C. Remote Control server mode (`claude remote-control`)

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

### D. Third-party tools (Claude Squad, CCManager, ccdeck, claude-tmux, ...)

**Pros**
- A management UI for several sessions already exists
- Some rebuild tmux sessions after a reboot and restore conversations with `claude -r` (ccdeck)
- Nothing to maintain yourself

**Cons**
- Most assume "new task, new worktree, new session", which fits poorly with existing clones and fixed roles
- None was found that covers browser access through ttyd, automatic `/remote-control` and unattended start from cron `@reboot` together
- One more external dependency

### Which one to use

| Goal | Good fit |
|---|---|
| Fixed roles and work directories that come back after a reboot | A (this tool) |
| One screen showing the state of parallel sessions | B (agent view). Using it together with A is untested |
| Any number of sessions from the browser or a phone | C (server mode) |
| A quick new session with its own worktree per task | B or D |

## Notes

- A login lasted about 3–4 weeks in the author's environment. When it expires, Remote Control disconnects with `OAuth token unavailable`.
  - Run `claude auth login` again with the same `CLAUDE_CONFIG_DIR`.
  - If a running session does not pick up the new credentials, `stop` and `start` it.
- If copying from the screen is difficult, use tmux copy mode or `tmux capture-pane -p -J`.
- After `/remote-control`, Claude Code opens a dialog (Disconnect / Show QR code / Continue). This tool closes it by pressing Enter, only when `Continue` is the selected item. If the dialog is still open, attach with `tmux attach -t <id>` and choose `Continue`.
- A session counts as ready when `? for shortcuts` or `shift+tab to cycle` appears on the screen (up to 60 seconds). If the wait fails, the warning includes the last 10 lines of the screen; check whether these texts still match your Claude Code version.
- The command is typed into the default shell of tmux and uses `VAR=value command` and `||`, so a POSIX-like shell (bash, zsh, ...) is expected.

## Not confirmed

- Whether sessions started by this tool are listed by `claude agents`
- Whether it works on macOS

## Development

Only needed if you change the tool. [uv](https://docs.astral.sh/uv/) is used so that nothing is installed globally.

```bash
python3 -m py_compile launch_claude
uvx ruff check --isolated --target-version py38 --line-length 110 --select E,F,W,B launch_claude tests
uv run --no-project --with pytest pytest                 # current Python
uv run --no-project --python 3.8 --with pytest pytest    # oldest supported Python
```

The integration tests use a private tmux server and a stub `claude`; they are skipped when tmux is not installed.

## References

- [Manage multiple agents with agent view](https://code.claude.com/docs/en/agent-view)
- [Continue local sessions from any device with Remote Control](https://code.claude.com/docs/en/remote-control)

## License

[MIT](LICENSE)
