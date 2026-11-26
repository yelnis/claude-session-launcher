[Back to README](../README.md)

# For AI assistants: setting up launch_claude for a user

Read this whole file before you run anything. It is self-contained: you do not need the other documents to set the tool up. It lists the points where guessing from the README, or from how Claude Code itself behaves, gives the wrong result.

Words: an **agent** and a **session** are the same thing here: one Claude Code process in one tmux session, known by an **ID**. The ID is at once the name of the tmux session, of the Claude Code conversation (`--name <id>` or `/rename <id>`, typed by the tool) and of the Remote Control session; other Claude Code sessions send messages to that name. The tool prevents duplicate IDs on one machine only: ask whether the user has sessions on other machines, and choose IDs that do not repeat there. **Registered** means a file `~/.config/launch_claude/agents/<id>.conf` exists. **Remote Control** is the Claude Code feature that makes a running session usable from claude.ai or the mobile app; it needs a claude.ai login (`claude auth login`), not an API key. **ttyd** is a separate program that shows the tmux session as a terminal in a web browser.

## 1. You may be running inside one of these sessions

The user often asks for changes from a Claude Code session that this tool started. Stopping that session ends your own conversation in the middle of the task.

```bash
tmux display-message -p '#{session_name}'   # the session you are in (fails or prints nothing outside tmux)
launch_claude list --running                # what is running
```

- `launch_claude stop` does not stop the session it is run in: `stop --all` stops all the others and says which one it kept, and with the ID of your own session it fails. Do not add `--stop-own-session` to get past this. If the user wants your session stopped or restarted, ask them to do it from another terminal.
- `stop` without an ID stops nothing and lists what is running. `stop --all` stops every other session, and other assistants or other accounts of the user may be working in them. Name the IDs you mean; use `--all` only when the user asked for everything to be stopped.
- Updating the program file (the `curl` command in the README) is safe while sessions run. Do not stop anything for an update.

## 2. What happens if you specify nothing

| Situation | Result |
|---|---|
| `open <id>` or `add <id>`, no ttyd option | tmux only: no browser terminal, no port |
| `--with-ttyd` (or `--port <n>` alone) | ttyd is on for every start. A free port from 7700-7799 is chosen and saved for good |
| ttyd is on, no global settings | ttyd listens on **every network interface, without a password, over plain HTTP** |
| `open <id>`, no conversation option | A **new** conversation, also for an ID that is already registered |
| `open` or `add`, no `--mode` | Saved mode is `new`: after a reboot the agent comes back with an **empty** conversation |
| `open` or `add`, no `--autostart` | The agent is **not** started after a reboot |
| `open --once` | Nothing is registered |
| No global settings | `/remote-control <id>` is typed into every session after start |

When a ttyd is started without a password on an interface other than loopback, `open`, `start` and `ttyd <id>` print a warning, once per run. Pass it on to the user; do not silence it with `ttyd_warning = 0` unless the user says the port is protected another way.

## 3. Words that do not mean what you might assume

| Word | Meaning here |
|---|---|
| `--mode new\|resume\|continue` | The conversation that `start` uses, including after a reboot. Accepted by `add` and `set` only. `open --mode` is an error that names the right options |
| `open --resume`, `open --continue` / `-c` | The same choice for this one start only. They do not change the saved mode |
| `new` | `claude --session-id <uuid> --name <id>`. The uuid is remembered for `resume` |
| `resume` | The conversation this tool last started in `new` mode for this ID. **No picker, no lookup by name.** If its transcript is gone, a new conversation is started and this is reported |
| `continue` | `claude --continue`: the latest conversation in the work directory, whoever started it, then `/rename <id>`. Two agents in the same directory would get the same conversation, so use it for one agent per directory |
| `ttyd <id>` (command) | Opens a browser terminal for an agent that is **running**, until `ttyd <id> --off` or `stop`. Saved settings do not change |
| `ttyd = 0/1` (setting), `--with-ttyd` / `--without-ttyd` | Whether `start` and `open` serve the agent with ttyd every time |
| `stop <id>` | Stops tmux and ttyd. The registration, the port and the conversation stay |
| `forget <id>` | Deletes the registration. Conversations of Claude Code are not deleted |
| `attach <id>` | For the user: puts their terminal into the session. It needs a terminal, so it fails when you run it. To read a session's screen yourself: `tmux capture-pane -p -t <id>` |

## 4. Ask the user before you set anything up

1. Is a browser terminal wanted at all? Remote Control and `tmux attach` work without it. If yes: from where will it be opened (this machine only, a trusted network, anywhere), and is a firewall, VPN or SSH access in place? If you cannot get an answer, do not pass `--with-ttyd`.
2. Should the terminal have a password? It is basic auth over plain HTTP and is visible in the process list to other users of the machine.
3. After a reboot, should each agent return to its previous conversation (`--mode continue` or `resume`) or start empty (`new`)?
4. Is Remote Control wanted, and is Claude Code logged in with a claude.ai account for the config directory in use?
5. Is a `CLAUDE_CONFIG_DIR` other than `~/.claude` used, or more than one account?
6. Do other users of this machine run the tool too? Then each user needs a different port range.
7. Which IDs and work directories? The directories must exist. Each one is marked as trusted for Claude Code (section 8).

## 5. Recipes

Check first:

```bash
command -v python3 tmux ttyd claude && python3 --version   # python 3.8 or newer; ttyd only if a browser terminal is wanted
launch_claude --version
launch_claude list                                         # what exists already; do not register it again
```

Agents that come back after a reboot with their previous conversation:

```bash
launch_claude add writer --dir ~/docs --mode continue --autostart
launch_claude add coder  --dir ~/src  --mode continue --autostart
launch_claude list --autostart       # both listed, AUTO column "*"
launch_claude start writer coder     # start now; prints "ready" for each
launch_claude attach writer          # for the user, in a terminal (leave: Ctrl-b d)
```

`open --autostart writer ~/docs` followed by `set writer --mode continue` gives the same registration, but starts at once with a new conversation.

The same with a browser terminal for each (only after question 1 is answered): add `--with-ttyd` to the `add` lines. `start` then prints the URL of each.

A browser terminal for a while, for an agent registered without one:

```bash
launch_claude ttyd writer            # prints the URL; the first free port is used
launch_claude ttyd writer --off
```

To know that URL in advance, register the agent with `--without-ttyd --port 7710`: the port is then kept for it.

Global settings, in `~/.config/launch_claude/config` (create the directory; then `chmod 600` the file if it holds a password):

```ini
[launch_claude]
ttyd_interface = lo
ttyd_credential = user:change-me
```

Changes to this file and to saved settings apply the next time an agent is started. They do not change a ttyd that is already running.

After a reboot, or to check at any time:

```bash
launch_claude list
```

`STATUS` is `running` or `stopped`. `ACCESS` is the URL, `tmux only`, or `-` when stopped.

## 6. Starting from cron

```cron
@reboot $HOME/.local/bin/launch_claude start --autostart
```

This goes into the user's own crontab (`crontab -e`), not `/etc/crontab`.

- Cron does not read the shell profile. `TTYD_CREDENTIAL`, `REMOTE_CONTROL` and `CLAUDE_CONFIG_DIR` set there do not exist at boot. Put the values into the `config` file (`ttyd_credential`, `remote_control`, `claude_config_dir`). A password that exists only in the shell profile means **no password after a reboot**.
- Cron's `PATH` is short, typically `/usr/bin:/bin`. `tmux` and `ttyd` must be found there: check with `env -i PATH=/usr/bin:/bin sh -c 'command -v tmux ttyd'`. If they live elsewhere, add a `PATH=...` line above the `@reboot` line.
- `claude` is not started by cron directly: its command line is typed into the shell that tmux opens. Under cron that shell is `/bin/sh` as a login shell, which reads `~/.profile` and not `~/.bashrc`. Check with `env -i HOME="$HOME" PATH=/usr/bin:/bin sh -lc 'command -v claude'`. If this prints nothing (usual on RHEL, where `PATH` is set in `~/.bashrc` and there is no `~/.profile`), add a `PATH=...` line with the directory of `claude` above the `@reboot` line: the shell inherits cron's `PATH`. Do not edit the user's shell files for this.
- You cannot fully test this without a reboot. Say so to the user instead of claiming that it works. After the reboot, `launch_claude list` shows the result.

## 7. The first start, and when a start does not finish

A start waits up to 60 seconds for the Claude Code input prompt, then types `/remote-control <id>` and prints `ready`.

| What you see | Meaning and what to do |
|---|---|
| `did not reach the input prompt (...)`, followed by screen lines | Claude Code did not come up. The screen lines say why: usually not logged in, or a dialog. The tmux session may still exist: `tmux attach -t <id>` |
| A dialog "Disconnect / Show QR code / Continue" stays open | The tool presses Enter only when `Continue` is selected. Otherwise attach and choose `Continue` |
| A login screen | Run `claude auth login` with the same `CLAUDE_CONFIG_DIR` in a normal terminal, then `stop` and `start` the agent |
| `OAuth token unavailable` after some weeks | The login expired (about 3-4 weeks in the author's use). Same fix |
| `no conversation to resume; starting a new one` | Mode `resume` found no saved conversation. Not an error |
| `ttyd did not start on port N` | Another program or user holds the port. The agent runs without ttyd. Choose another port: `set <id> --port <n>` |
| `directory ... not found; skipped` | The saved work directory is gone. Fix it with `set <id> --dir <path>` |
| `unknown key ... (ignored)` | A misspelled key in a settings file. Report it to the user; do not guess the intended key |

## 8. What the tool does without asking

- On every start it marks the work directory as trusted in Claude Code's `.claude.json`, so that the trust dialog does not block the start. There is no setting to turn this off. Only register directories the user trusts.
- It types into the session: the `claude` command, `/rename <id>` (mode `continue`), `/remote-control <id>` (unless `remote_control = 0`), and Enter for the dialogs above.
- It never kills a program that holds a port, and never touches tmux sessions it did not start.

## 9. What the tool cannot know

- Whether a reverse proxy, VPN or firewall protects a ttyd port. It only knows whether it passed a password to ttyd. Do not tell the user a terminal is protected because no warning appeared.
- Whether Claude Code is logged in, before a start is tried.
- Ports of other users on the same machine. Collisions are avoided only by giving each user another `port_min`-`port_max` range.
- Tested systems: Ubuntu 24.04 LTS, Ubuntu 26.04 LTS on WSL, RHEL 9.7. Others, including macOS, are untested. The nginx example in `examples/config.reverse-proxy` is an untested idea.

## 10. More detail

`launch_claude help` prints every command and option. Every settings key is explained in [`examples/config.example`](../examples/config.example) and [`examples/agents/example.conf`](../examples/agents/example.conf); each command in [`reference.md`](reference.md).
