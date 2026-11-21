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
- `tmux`
- `ttyd` (not needed if you only use tmux sessions: `--without-ttyd`)
- Claude Code, logged in with `claude auth login` if you use Remote Control

Linux is the target. Nothing depends on the kernel or shell version, so it should work wherever the four items above do. It has been used on:

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
launch_claude ttyd <id> [--port <n>]   open ttyd for a running agent, for now only
launch_claude ttyd <id> --off          close it again; the agent keeps running
launch_claude add <id> [options]       register only (does not start)
launch_claude set <id> [options]       change saved settings
launch_claude forget <id>              remove the registration
```

IDs match `^[A-Za-z0-9][A-Za-z0-9_-]*$`. These words are reserved and cannot be IDs: `all`, `start`, `stop`, `open`, `add`, `set`, `forget`, `list`, `ttyd`, `help`.

Each command is described in the [reference](docs/reference.md).

## Use cases

Ready-made settings for common situations. Each file explains itself in comments.

| I want to ... | Start from |
|---|---|
| see every global setting | [`examples/config.example`](examples/config.example) |
| see every per-agent setting | [`examples/agents/example.conf`](examples/agents/example.conf) |
| share the machine with other users (separate port ranges, a ttyd password) | [`examples/config.shared-machine`](examples/config.shared-machine) |
| put ttyd behind nginx, an SSH port forward or a VPN | [`examples/config.reverse-proxy`](examples/config.reverse-proxy) |
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
| `port_min` | `7700` | First port tried for a new agent |
| `port_max` | `7799` | Last port tried for a new agent |
| `ttyd_interface` | not set | Where ttyd listens (`lo`, an interface name or an IP address); all interfaces if not set |
| `ttyd_credential` | not set | `user:password` for ttyd basic auth |
| `ttyd_warning` | `1` | Warn when `ttyd <id>` opens ttyd without a password |

Per-agent settings (`agents/<id>.conf`, section `[agent]`), normally written by `open` / `add` / `set`:

| Key | Default | Meaning |
|---|---|---|
| `dir` | — | Work directory |
| `ttyd` | `0` | `1`: serve with ttyd. `0`: tmux only |
| `port` | not set | ttyd port; kept and reserved also while `ttyd = 0` |
| `mode` | `new` | Conversation used by `start`: `new`, `resume` or `continue` |
| `autostart` | `0` | `1`: started by `start --autostart` |
| `claude_config_dir` | not set | `CLAUDE_CONFIG_DIR` for this agent only |

Details, notes and the exact precedence of each key are in the comments of [`examples/config.example`](examples/config.example) and [`examples/agents/example.conf`](examples/agents/example.conf). A key that is not in these tables is reported as unknown, which catches typos.

## Security

- **ttyd is started without authentication unless you configure it.** Anyone who can connect to the port gets your terminal, with your permissions. Keep the ports behind a firewall or on a trusted network.
- To require a password, set `TTYD_CREDENTIAL=user:password` in the environment, or `ttyd_credential` in `config` (then `chmod 600` the file; a warning is shown otherwise). It is passed to `ttyd -c`, so it is visible in the process list to other users of the same machine, and basic auth over plain HTTP is not encrypted.
- To make an agent trusted without a prompt, the directory is marked as trusted in Claude Code's `.claude.json`. Only open directories you trust.
- launch_claude only knows what it passes to ttyd. If you protect the port another way (reverse proxy, SSH port forward, VPN), make ttyd listen on that path only with `ttyd_interface`; see [`examples/config.reverse-proxy`](examples/config.reverse-proxy).

## More

- [Reference](docs/reference.md): every command and option, conversation modes, autostart, operating notes
- [Compared with other approaches](docs/comparison.md): this tool, the official agent view, Remote Control server mode and third-party tools
- `launch_claude help` prints the full usage

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

## License

[MIT](LICENSE)
