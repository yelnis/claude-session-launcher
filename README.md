English | [日本語](README.ja.md)

# claude-session-launcher

> **TL;DR** — This script starts several Claude Code sessions at once and makes each of them reachable through `/remote-control`. I wrote it because I wanted my development sessions to come back automatically when Linux reboots (cron `@reboot`). While at it, it also names each session, remembers its work directory, and can return to its previous conversation.

> **AI assistants:** before you run any command of this tool for a user, read [`docs/ai-setup.md`](docs/ai-setup.md) (https://raw.githubusercontent.com/yelnis/claude-session-launcher/main/docs/ai-setup.md).

`launch_claude` starts several named [Claude Code](https://code.claude.com/docs) sessions in tmux and sends `/remote-control` once each session is ready. If you ask for it, it also serves a session as a terminal in the browser with [ttyd](https://github.com/tsl0922/ttyd).

- Give a session an ID (`writer`, `coder`, ...) and it remembers its work directory and conversation mode.
- `open` registers a session and starts it; `start` brings registered sessions back.
- Sessions flagged `autostart` come back after a reboot with one cron line.
- `open --once` gives you a throwaway session: it is not registered, and its tmux session is removed when claude exits.

Words used here: a **session** and an **agent** are the same thing, one Claude Code process in one tmux session, known by its ID. **Remote Control** is the Claude Code feature that lets you use a running session from claude.ai or the mobile app; `/remote-control` is the command that turns it on.

It is a single Python file that uses only the standard library. It is also 100% written by Claude Code (the human wrote the spec and did the complaining).

> **Warning: the browser terminal (ttyd) is off unless you ask for it with `--with-ttyd`. When it is on, it has no authentication by default.** Anyone who can reach the port can operate your terminal. See [Security](#security).

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Use cases](#use-cases)
- [Settings](#settings)
- [Security](#security)
- [More](#more)
- [Not confirmed](#not-confirmed)
- [Development](#development)
- [License](#license)

Other pages:

- [Reference](docs/reference.md): every command and option, conversation modes, autostart, operating notes
- [Compared with other approaches](docs/comparison.md): the official agent view, Remote Control server mode, third-party tools
- [Samples](examples/): settings files for common situations

## Requirements

- `python3` 3.8 or newer (standard library only; nothing to `pip install`). If Python is missing, install it first, e.g. `sudo dnf install python3` or `sudo apt install python3`.
- `tmux`, with a POSIX-like shell (bash, zsh, sh, ...) as its default shell
- `ttyd`, only if you want the browser terminal (`--with-ttyd`)
- Claude Code, logged in. A session that is not logged in stops at the login screen. Remote Control needs a claude.ai login (`claude auth login`), not an API key

Linux is the target. Nothing depends on the kernel version, so it should work wherever the four items above do. It has been used on:

- Ubuntu 24.04 LTS
- Ubuntu 26.04 LTS (on WSL)
- RHEL 9.7

macOS may work but is **untested**.

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
launch_claude open web            # new conversation in tmux, registered as "web"
launch_claude attach web          # the terminal (leave with Ctrl-b d); or use it from claude.ai
launch_claude list                # what is registered and what is running
launch_claude stop web            # stop it; the registration stays
launch_claude start web           # start it again with the saved settings
launch_claude set web --autostart --mode continue   # after a reboot: start it, in its latest conversation
```

Then add one line to your own crontab (`crontab -e`):

```cron
@reboot $HOME/.local/bin/launch_claude start --autostart
```

Cron does not use your interactive shell, so:

- Write the full path of `launch_claude` as shown.
- `tmux` (and `ttyd`) must be found on cron's short `PATH`, usually `/usr/bin:/bin`. If they are elsewhere, put a `PATH=...` line above the `@reboot` line.
- Environment variables from your shell profile (`TTYD_CREDENTIAL`, `REMOTE_CONTROL`, `CLAUDE_CONFIG_DIR`) are not set. Put such values into the [settings file](#settings) instead.
- `claude` itself is typed into the shell that tmux starts. Under cron that is `/bin/sh` as a login shell, which reads `~/.profile` and not `~/.bashrc`. Where `~/.profile` puts the directory of `claude` into `PATH` (Ubuntu does this for `~/.local/bin`), nothing more is needed. Where it does not, or the file does not exist (RHEL keeps `PATH` in `~/.bashrc`), add a `PATH=...` line that contains that directory above the `@reboot` line; the shell inherits it.

### A terminal in the browser

```bash
launch_claude open --with-ttyd web      # a new agent: also serve it with ttyd; prints the URL
launch_claude set web --with-ttyd       # a registered agent: from its next start on
launch_claude ttyd web                  # a running agent: until "ttyd web --off" or "stop"
```

A free port from 7700-7799 is chosen and saved, so the URL stays the same. The terminal is plain HTTP, on every network interface, without a password, until you change that: read [Security](#security) first.

### The first start

- Log in once before the first start (`claude auth login`). The tool cannot do this for you.
- The work directory is marked as trusted for Claude Code, so the trust dialog does not stop the start.
- A start waits up to 60 seconds for the Claude Code prompt, then types `/remote-control <id>`. Claude Code then shows a dialog (Disconnect / Show QR code / Continue); the tool closes it when `Continue` is selected. If it stays open, attach with `tmux attach -t <id>` and choose `Continue`.
- If a start fails, the message shows the last lines of the screen. `launch_claude attach <id>` shows the rest.
- A claude.ai login lasted about 3-4 weeks for the author. After that Remote Control disconnects until you log in again.

## Commands

```
launch_claude                          show help and exit with status 1; starts nothing
launch_claude help | -h | --help       show help
launch_claude --version                show the version
launch_claude open [options] [<id>] [dir]   open a new or registered agent; registers it unless --once
                                       (tmux only unless --with-ttyd)
launch_claude start <id>...            start registered agents
launch_claude start --autostart        start every agent with autostart=1
launch_claude <id>                     shortcut for: start <id>
launch_claude stop [<id>...]           stop agents, keep registrations; no id = everything running
                                       (the session you run it in is kept unless --stop-own-session)
launch_claude attach [<id>]            go to the tmux session of a running agent (leave: Ctrl-b d);
                                       no id = the only one running
launch_claude list [--running|--autostart]
launch_claude ttyd <id> [--port <n>]   open ttyd for a running agent until --off or stop
                                       (saved settings unchanged)
launch_claude ttyd <id> --off          close it again; the agent keeps running
launch_claude add <id> [options]       register only (does not start)
launch_claude set <id> [options]       change saved settings
launch_claude forget <id>              remove the registration
launch_claude completion bash          print a bash completion script
```

IDs match `^[A-Za-z0-9][A-Za-z0-9_-]*$`. These words are reserved and cannot be IDs: `all`, `start`, `stop`, `open`, `attach`, `add`, `set`, `forget`, `list`, `ttyd`, `completion`, `help`.

The ID becomes three names: the tmux session, the Claude Code conversation and the Remote Control session. Claude Code shows that name in claude.ai, and other Claude Code sessions use it to send a message to this one. The tool prevents duplicate IDs on one machine only, so if you use several machines, choose IDs that differ between them.

### Completion in bash

Add this line to `~/.bashrc`:

```bash
eval "$(launch_claude completion bash)"
```

Tab then completes the commands, their options and the IDs that fit: running agents after `attach`, `stop` and `ttyd`, stopped ones after `start` and `open`, all registered ones after `set` and `forget`. For a shorter command, add `alias lc=launch_claude` and `complete -F _launch_claude lc` below that line.

### Options

| Option | Commands | Meaning |
|---|---|---|
| `--dir <path>` | `open`, `add`, `set` | Work directory. For `open` also the second argument; default: the current directory |
| `--with-ttyd` / `--without-ttyd` | `open`, `add`, `set` | Serve the agent in the browser on every start, or tmux only. Default for a new agent: tmux only |
| `--port <n>` | `open`, `add`, `set`, `ttyd` | ttyd port. Alone it implies `--with-ttyd`; with `--without-ttyd` it only reserves the port for a later `ttyd <id>` |
| `--autostart` / `--no-autostart` | `open` (`--autostart` only), `add`, `set` | Whether `start --autostart` starts the agent |
| `--mode new\|resume\|continue` | `add`, `set` | Conversation that `start` uses. Default: `new` |
| `--resume`, `--continue` / `-c` | `open` | The same choice for this one start; the saved mode is not changed |
| `--once` | `open` | Throwaway session: not registered, removed when claude exits |
| `--claude-config-dir <path>` | `open`, `add`, `set` | `CLAUDE_CONFIG_DIR` for this agent, for example a second account |
| `--stop-own-session` | `stop` | Also stop the session the command is run in |

### Conversation modes

| Mode | Conversation |
|---|---|
| `new` (default) | A new, empty one on every start. After a reboot the previous conversation is not shown |
| `resume` | The one this tool last started in `new` mode for this ID. There is no picker and no search by name |
| `continue` | The latest one in the work directory, whoever started it; it is then renamed to the ID. Use it for one agent per directory |

`open` always starts a new conversation unless you pass `--resume` or `--continue`.

Each command is described in the [reference](docs/reference.md).

## Use cases

Ready-made settings for common situations. Each file explains itself in comments.

| I want to ... | Start from |
|---|---|
| see every global setting | [`examples/config.example`](examples/config.example) |
| see every per-agent setting | [`examples/agents/example.conf`](examples/agents/example.conf) |
| share the machine with other users (separate port ranges, a ttyd password) | [`examples/config.shared-machine`](examples/config.shared-machine) |
| put ttyd behind nginx, an SSH port forward or a VPN (the settings are tested; the proxy examples are ideas only) | [`examples/config.reverse-proxy`](examples/config.reverse-proxy) |
| run an agent without ttyd, and open a browser terminal only when needed | [`examples/agents/tmux-only.conf`](examples/agents/tmux-only.conf) |
| use a second Claude account for some agents | [`examples/agents/second-account.conf`](examples/agents/second-account.conf) |

To start from a sample (the reference sample changes nothing until you uncomment a line):

```bash
mkdir -p ~/.config/launch_claude
curl -fsSL https://raw.githubusercontent.com/yelnis/claude-session-launcher/main/examples/config.example \
  -o ~/.config/launch_claude/config
```

## Settings

No settings file is needed. Everything is optional.

| What | Where |
|---|---|
| Program | `~/.local/bin/launch_claude` |
| Global settings | `${XDG_CONFIG_HOME:-~/.config}/launch_claude/config` |
| One file per registered agent | `${XDG_CONFIG_HOME:-~/.config}/launch_claude/agents/<id>.conf` |
| Runtime state (last conversation, last start) | `${XDG_STATE_HOME:-~/.local/state}/launch_claude/` |

Global settings (`config`, section `[launch_claude]`):

| Key | Default | Meaning |
|---|---|---|
| `claude_config_dir` | not set | `CLAUDE_CONFIG_DIR` for all agents |
| `remote_control` | `1` | Send `/remote-control <id>` after start |
| `port_min` | `7700` | First port tried when an agent gets a ttyd port. The port is chosen once and saved |
| `port_max` | `7799` | Last port tried |
| `ttyd_interface` | not set | Where ttyd listens (`lo`, an interface name or an IP address). Not set: every interface, so reachable from the network |
| `ttyd_credential` | not set | `user:password` for ttyd basic auth |
| `ttyd_warning` | `1` | Warn when ttyd is started without a password on an interface other than loopback |

Per-agent settings (`agents/<id>.conf`, section `[agent]`), normally written by `open` / `add` / `set`:

| Key | Default | Meaning |
|---|---|---|
| `dir` | required | Work directory |
| `ttyd` | `0` | `1`: serve with ttyd on every start. `0`: tmux only |
| `port` | not set | ttyd port; kept and reserved also while `ttyd = 0` |
| `mode` | `new` | Conversation used by `start`: `new`, `resume` or `continue` |
| `autostart` | `0` | `1`: started by `start --autostart` |
| `claude_config_dir` | not set | `CLAUDE_CONFIG_DIR` for this agent only |

Details, notes and the exact precedence of each key are in the comments of [`examples/config.example`](examples/config.example) and [`examples/agents/example.conf`](examples/agents/example.conf). A key that is not in these tables is reported as unknown, which catches typos.

Two environment variables override the file: `TTYD_CREDENTIAL` (for `ttyd_credential`) and `REMOTE_CONTROL` (for `remote_control`).

## Security

- ttyd is only started for agents registered with `--with-ttyd` (or `ttyd = 1`) and by the `ttyd <id>` command.
- **When ttyd is started, it has no authentication unless you configure it**, and it listens on every network interface. Anyone who can connect to the port gets your terminal, with your permissions. Keep the ports behind a firewall or on a trusted network, or set `ttyd_interface = lo`. The tool warns when it starts such a ttyd.
- To require a password, set `TTYD_CREDENTIAL=user:password` in the environment, or `ttyd_credential` in `config` (then `chmod 600` the file; a warning is shown otherwise). It is passed to `ttyd -c`, so it is visible in the process list to other users of the same machine, and basic auth over plain HTTP is not encrypted.
- On every start, the work directory is marked as trusted in Claude Code's `.claude.json`, so that the trust dialog does not stop the start. This is automatic and cannot be turned off. Only register directories you trust.
- launch_claude only knows what it passes to ttyd. If you protect the port another way (reverse proxy, SSH port forward, VPN), set `ttyd_interface` so that ttyd listens only where that protection applies (for example `lo` behind a proxy on the same machine); see [`examples/config.reverse-proxy`](examples/config.reverse-proxy).

## More

- [Reference](docs/reference.md): every command and option, conversation modes, autostart, operating notes
- [Compared with other approaches](docs/comparison.md): this tool, the official agent view, Remote Control server mode and third-party tools
- `launch_claude help` prints the full usage

## Not confirmed

- Whether sessions started by this tool are listed by `claude agents`, the agent view of Claude Code (see the [comparison](docs/comparison.md))
- Whether it works on macOS

## Development

Only needed if you change the tool. [uv](https://docs.astral.sh/uv/) is used so that nothing is installed globally.

```bash
tools/check
```

This runs the syntax check, ruff, and the tests on the current and on the oldest supported Python. Every result, with the totals at the end, is written to `reports/check-report.txt` (not committed).

To run only the tests:

```bash
uv run --no-project --with pytest pytest                 # current Python
uv run --no-project --python 3.8 --with pytest pytest    # oldest supported Python
```

What each test checks is listed in [`tests/README.md`](tests/README.md). The integration tests use a private tmux server and a stub `claude`; they are skipped when tmux is not installed.

## License

[MIT](LICENSE)
