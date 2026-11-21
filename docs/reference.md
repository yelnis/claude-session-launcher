English | [日本語](reference.ja.md) · [Back to README](../README.md)

# Reference

Details of each command. For the purpose and a quick start, see the [README](../README.md); for every setting, see the commented samples in [`examples/`](../examples).

## open

```bash
launch_claude open review                  # register "review" in the current directory and start it
launch_claude open review ~/work/repo      # ... in another directory
launch_claude open --resume review         # resume the last conversation of "review"
launch_claude open -c review               # continue the latest conversation in the directory, rename it to "review"
launch_claude open --without-ttyd review   # tmux only, no port
launch_claude open --without-ttyd --port 7710 review   # tmux only, but keep port 7710 for later
launch_claude open --port 7710 review      # choose the ttyd port
launch_claude open --once                  # throwaway session
launch_claude open --once --with-ttyd tmp  # throwaway session with ttyd and an ID
```

| Option | Meaning |
|---|---|
| `--resume` | Resume the last conversation of this agent. Applies to this launch only |
| `--continue`, `-c` | Continue the latest conversation in the work directory and rename it to `<id>`. Refused if another agent is running in the same directory |
| `--once` | Always a new conversation, never registered. Without `<id>` the ID is `once-HHMMSS`. No ttyd by default. tmux and ttyd are cleaned up when claude exits. Cannot be combined with `--resume`, `--continue` or `--autostart` |
| `--with-ttyd` / `--without-ttyd` (`--no-ttyd`) | Serve with ttyd, or tmux only. `--without-ttyd` keeps a saved or given port, so the same URL is available later |
| `--port <n>` | ttyd port. Implies ttyd unless `--without-ttyd` is given. Default: the first free port in `port_min`–`port_max` |
| `--dir <path>` | Work directory (same as the second positional argument). Default: the current directory |
| `--claude-config-dir <path>` | `CLAUDE_CONFIG_DIR` for this agent, for example a second account. `default` removes it. See [`examples/agents/second-account.conf`](../examples/agents/second-account.conf) |
| `--autostart` | Set `autostart=1` |

- A new ID is registered with the directory, ttyd setting and port. The port is saved so that the URL stays the same.
- A registered ID uses its saved settings. If you pass `--dir`, `--port`, `--with-ttyd`/`--without-ttyd`, `--claude-config-dir` or `--autostart`, the new value is saved and reported.
- `open` starts a **new conversation** unless you pass `--resume` or `--continue`. These two flags affect this launch only; what `start` does is set with `--mode` (see below).
- If the agent is already running, `open` reports it and does nothing.

## add / set

```bash
launch_claude add coder --dir ~/work/repo --port 7683 --mode continue --autostart
launch_claude set coder --no-autostart
launch_claude set coder --mode resume
```

Options: `--dir <path>`, `--port <n>`, `--with-ttyd` / `--without-ttyd`, `--claude-config-dir <path>`, `--mode new|resume|continue`, `--autostart` / `--no-autostart`.

## start

- You must name the targets: IDs or `--autostart`. `start` alone is an error.
- Agents that are already running are skipped.
- If the saved directory no longer exists, the agent is skipped with a warning (there is no fallback to `$HOME`).
- The saved ttyd port must be free; ports held by other programs are never killed. On a machine shared with other users, give each user a different `port_min`–`port_max` range ([`examples/config.shared-machine`](../examples/config.shared-machine)).

## ttyd

Opens a ttyd for an agent that is already running, without restarting claude, and closes it again.

```bash
launch_claude ttyd review              # open; prints the URL
launch_claude ttyd review --port 7720  # open on this port
launch_claude ttyd review --off        # close; the agent keeps running
```

- The port is `--port`, else the port saved for the agent, else the first free port in the range.
- This is temporary: the saved setting is not changed, so the next `start` follows `ttyd = 0/1` as before. To always serve an agent, use `set <id> --with-ttyd`.
- It stays open until you close it or stop the agent. If ttyd is started without a password of its own (`TTYD_CREDENTIAL` / `ttyd_credential`) on a non-loopback interface, a warning is shown. The tool cannot see a proxy, VPN or firewall in front of the port; if you have one, turn the warning off with `ttyd_warning = 0`.
- Works for `--once` sessions too.

A ttyd is only reported as open when this tool's own ttyd is listening on the port. If the port is taken by another program or user, you get an error instead of a URL.

## stop / forget

- `stop <id>...` stops tmux and ttyd for those agents. `stop` alone stops everything this tool started, including `--once` sessions. Registrations are kept.
- `forget <id>` deletes the registration and its state. Stop the agent first.

## list

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

After a reboot only the tmux session is started and no port is used. `/remote-control` is still sent, since it does not depend on ttyd. To see the terminal, use `tmux attach -t myproj`, or open a ttyd for a while with `launch_claude ttyd myproj`. A saved port is kept while ttyd is off, so switching back with `--with-ttyd` gives the same URL.


## Notes

- A login lasted about 3–4 weeks in the author's environment. When it expires, Remote Control disconnects with `OAuth token unavailable`.
  - Run `claude auth login` again with the same `CLAUDE_CONFIG_DIR`.
  - If a running session does not pick up the new credentials, `stop` and `start` it.
- If copying from the screen is difficult, use tmux copy mode or `tmux capture-pane -p -J`.
- After `/remote-control`, Claude Code opens a dialog (Disconnect / Show QR code / Continue). This tool closes it by pressing Enter, only when `Continue` is the selected item. If the dialog is still open, attach with `tmux attach -t <id>` and choose `Continue`.
- A session counts as ready when `? for shortcuts` or `shift+tab to cycle` appears on the screen (up to 60 seconds). If the wait fails, the warning includes the last 10 lines of the screen; check whether these texts still match your Claude Code version.
- The command is typed into the default shell of tmux and uses `VAR=value command` and `||`, so a POSIX-like shell (bash, zsh, ...) is expected.
