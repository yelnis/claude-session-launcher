# Tests

Run the tests from the repository root:

```bash
uv run --no-project --with pytest pytest                 # current Python
uv run --no-project --python 3.8 --with pytest pytest    # oldest supported Python
```

`tools/check` runs both, together with the syntax check and ruff, and writes every result to `reports/check-report.txt`.

| File | What it uses |
|---|---|
| [`test_launch_claude.py`](test_launch_claude.py) | The tool's functions, with tmux replaced by a fake. Nothing is started. |
| [`test_integration.py`](test_integration.py) | The real `launch_claude` program, a private tmux server, a stub `claude`, and the real `ttyd` where needed. |
| [`test_docs.py`](test_docs.py) | The README files, `docs/` and `examples/`, compared with the code. |

None of the tests starts the real Claude Code, and none touches your own settings, tmux sessions or `~/.claude`: every test gets its own `HOME`, XDG directories and (for the integration tests) its own tmux server.

## Helpers

[`conftest.py`](conftest.py):

- `load_script()` loads `launch_claude` as a module, although it has no `.py` extension.
- `lc` gives a test the module with `HOME` and the XDG directories pointed at a temporary directory, ports always free, a fixed host address (`192.0.2.10`), and `FakeTmux` in place of tmux.
- `FakeTmux` remembers which sessions "run" and records what would have been launched, stopped or served by ttyd.
- `workdir` is a temporary work directory that the test is run from.

`test_launch_claude.py` adds `launcher`: the real `launch_session` and `start_ttyd` run, and only the `tmux` command itself is replaced by a recorder. This is how the exact `claude` and `ttyd` command lines are checked.

`test_integration.py` adds `sandbox`: a temporary home, a stub `claude` (a shell script that prints `? for shortcuts` and logs its arguments and input), and a tmux server of its own under `XDG_RUNTIME_DIR`.

## test_launch_claude.py

### Help and exit codes

| Test | Checks |
|---|---|
| `test_no_arguments_prints_help_and_fails` | No arguments: help is printed, exit status 1, nothing is started |
| `test_help_succeeds` | `help`, `-h`, `--help` print the help with status 0 |
| `test_version` | `--version` prints the version |
| `test_start_without_target_is_an_error` | `start` needs an id or `--autostart` |
| `test_unknown_id_is_an_error` | An unknown word is reported, not started |

### IDs

| Test | Checks |
|---|---|
| `test_reserved_words_are_not_ids` | `all` and the command names are refused as ids |
| `test_invalid_ids` | Ids with spaces, slashes, dots, a leading `-` or `_`, or empty are refused |
| `test_valid_ids` | Letters, digits, `_` and `-` are accepted |
| `test_add_rejects_reserved_word` | `add` refuses a reserved word |

### open

| Test | Checks |
|---|---|
| `test_open_registers_and_starts` | A new id is registered with the current directory and started, tmux only and without a port |
| `test_open_with_ttyd_picks_and_saves_a_port` | `--with-ttyd` turns ttyd on and saves the first free port; `--port` alone implies ttyd |
| `test_open_mode_option_points_to_the_right_options` | `open --mode` fails with a message that names `--resume`, `--continue` and `set <id> --mode`; nothing is registered or started |
| `test_open_options_are_saved` | `--without-ttyd`, `--autostart` and a directory given to `open` are saved; no port is written when ttyd is off |
| `test_open_registered_uses_saved_settings_and_new_conversation` | A registered id opens with its saved directory and port, in a new conversation |
| `test_open_overrides_are_saved_and_reported` | Options given for a registered id replace the saved ones, and the change is printed |
| `test_open_conversation_flags_apply_to_this_launch_only` | `--resume`, `--continue`, `-c` are used for this start only; the saved mode stays |
| `test_open_running_agent_is_skipped` | An id that already runs is not started again |
| `test_open_refuses_unmanaged_tmux_session` | A tmux session of the same name that this tool did not start is left alone |
| `test_open_without_id_is_an_error` | `open` without an id (and without `--once`) fails |
| `test_open_missing_directory_is_an_error` | A work directory that does not exist is refused |
| `test_open_continue_refuses_shared_directory` | `--continue` is refused while another agent runs in the same directory, and nothing is registered |
| `test_port_with_ttyd_off_is_reserved` | `--port` with `--without-ttyd` keeps the port, starts without ttyd, and gives the port to nobody else |
| `test_once_port_needs_ttyd` | `--once --port --without-ttyd` is refused, since nothing would be saved |
| `test_port_of_another_agent_is_refused` | A port already assigned to another agent is refused |
| `test_automatic_ports_skip_reserved_and_busy_ones` | The automatic port skips assigned ports and ports in use |

### open --once

| Test | Checks |
|---|---|
| `test_once_is_not_registered` | A throwaway session gets a generated id and leaves no registration |
| `test_once_with_id_and_ttyd` | `--once` accepts an id and `--with-ttyd` |
| `test_once_cannot_be_combined` | `--once` with `--resume`, `--continue` or `--autostart` is refused |
| `test_once_refuses_registered_id` | `--once` refuses an id that is registered |

### add, set, forget, stop

| Test | Checks |
|---|---|
| `test_add_does_not_start` | `add` registers and starts nothing |
| `test_add_twice_is_an_error` | `add` refuses an id that exists |
| `test_set_changes_settings` | `set` changes autostart, mode and ttyd; turning ttyd off keeps the port, so turning it on again gives the same URL |
| `test_set_port_alone_implies_ttyd_but_not_with_without_ttyd` | `set --port` turns ttyd on; with `--without-ttyd` only the port is saved |
| `test_set_unknown_agent_is_an_error` | `set` on an unknown id fails |
| `test_stop_keeps_registration` | `stop <id>` stops the session and keeps the registration |
| `test_stop_without_arguments_stops_everything_including_once` | `stop` alone stops every running session, throwaway ones included; registrations stay |
| `test_stop_without_arguments_keeps_own_session` | Run from inside a managed session, `stop` alone stops the others, keeps that session and says so; a second run says nothing else is running |
| `test_stop_own_session_by_id_is_an_error_and_stops_nothing` | Naming the session the command runs in is an error, and the other named sessions are not stopped either |
| `test_stop_own_session_when_asked_stops_it_last` | With `--stop-own-session` the own session is stopped too, after the others; also when it is named |
| `test_stop_from_a_session_of_another_tool_stops_everything` | Inside a tmux session that this tool did not start, `stop` alone stops everything as before |
| `test_stop_unknown_is_an_error` | `stop` on an unknown id fails |
| `test_forget_removes_registration_and_state` | `forget` removes the registration and the state file |
| `test_forget_running_agent_asks_to_stop` | `forget` refuses a running agent |

### start

| Test | Checks |
|---|---|
| `test_start_autostart_only_starts_flagged_agents` | `start --autostart` starts only agents with `autostart = 1`, in their saved mode |
| `test_start_skips_running_agents` | Running agents are skipped with a message |
| `test_start_ids_and_shortcut` | `start a b` and the shortcut `launch_claude a` |
| `test_start_skips_missing_directory` | An agent whose directory is gone is skipped (no fallback to the home directory); the others still start, and the exit status is 1 |
| `test_start_autostart_with_nothing_flagged` | `start --autostart` with nothing flagged starts nothing and succeeds |
| `test_command_wins_over_id_of_the_same_name` | A hand-made registration named like a command does not shadow the command |

### list

| Test | Checks |
|---|---|
| `test_list_shows_registered_and_once` | Columns for registered, running and throwaway sessions: status, URL or `tmux`, directory (`(!)` if missing), mode, autostart, last start |
| `test_list_filters` | `--running` and `--autostart` |
| `test_list_empty` | The message when nothing is registered |

### Settings files

| Test | Checks |
|---|---|
| `test_ini_round_trip_keeps_percent_signs` | `%` in a value survives writing and reading; empty values are left out; no temporary file stays behind |
| `test_settings_defaults_without_files` | The defaults when no file exists |
| `test_settings_from_file_and_environment` | Values from `config`; the warning when a file with a password is readable by others; `REMOTE_CONTROL` and `TTYD_CREDENTIAL` in the environment win over the file |
| `test_hand_written_agent_file` | A hand-written agent file with comments, `~` and missing keys is read with defaults |

### Starting a session (real code, tmux command recorded)

| Test | Checks |
|---|---|
| `test_new_conversation_uses_session_id_and_name` | New: `claude --session-id <uuid> --name <id>`, the uuid is saved, `/remote-control <id>` is sent |
| `test_resume_falls_back_to_new_without_transcript` | Resume without a saved conversation file starts a new conversation and says so |
| `test_resume_uses_uuid_when_transcript_exists` | Resume with a saved conversation file runs `claude --resume <uuid>` |
| `test_continue_renames_and_respects_remote_control_off` | Continue runs `claude --continue`, sends `/rename <id>`, and sends no `/remote-control` when it is turned off |
| `test_claude_config_dir_is_quoted_and_once_cleans_up` | A config directory with a space is quoted; a throwaway session's command ends with its own cleanup |
| `test_ttyd_is_started_with_credential` | The password is passed to `ttyd -c` |
| `test_pretrust_writes_claude_json` | The work directory is marked as trusted in `.claude.json`; what is already there, and the file's permissions, are kept |
| `test_missing_tmux_is_reported` | A missing `tmux` or `ttyd` gives a clear error (for ttyd, saying it is only needed for the browser terminal), with a hint at cron's short `PATH` |
| `test_remote_control_dialog_is_closed_only_on_continue` | The Remote Control dialog is answered with Enter only while "Continue" is selected |
| `test_ttyd_that_cannot_bind_is_reported_and_session_keeps_running` | If ttyd does not come up on the port, that is reported, no URL is shown, and the agent keeps running |
| `test_started_ttyd_records_its_port` | A ttyd that is listening is recorded on the session, so `list` can show it |

### ttyd command

| Test | Checks |
|---|---|
| `test_ttyd_opens_on_saved_port_without_changing_settings` | `ttyd <id>` opens on the saved port, warns about the missing password, changes no saved setting, and `--off` closes it |
| `test_ttyd_port_option_and_automatic_port` | `--port`, and a free port when none is saved |
| `test_open_ttyd_warning_is_shown_once_and_only_when_open` | The warning used by `open`, `start` and `ttyd`: silent with `ttyd_warning = 0`, a password or a loopback interface; names the interface; shown once per run |
| `test_ttyd_no_warning_with_credential` | No warning when a password is set |
| `test_ttyd_warning_can_be_turned_off` | `ttyd_warning = 0` silences the warning |
| `test_ttyd_errors` | Not running, unknown id, a port of another agent, `--off` with `--port`, `--off` when nothing is open |
| `test_ttyd_is_reserved` | `ttyd` cannot be an id |

### ttyd_interface

| Test | Checks |
|---|---|
| `test_interface_values` | `lo`, `localhost` (turned into `lo`), addresses, interface names, and an empty value (not set) |
| `test_interface_socket_path_is_refused` | A UNIX socket path is refused |
| `test_loopback_interface_gives_localhost_urls_and_no_warning` | With a loopback interface the URL says `localhost` and no warning is shown |
| `test_url_host_for_addresses_and_interface_names` | The URL host for an address, an interface name, and an unknown interface (falls back to the usual address) |
| `test_interface_is_passed_to_ttyd` | The value is passed to `ttyd -i` |

### Per-agent claude_config_dir

| Test | Checks |
|---|---|
| `test_agent_config_dir_is_saved_changed_and_removed` | `--claude-config-dir` saves, changes and (`default`) removes the setting |
| `test_missing_config_dir_only_warns` | A directory that does not exist yet gives a warning, not an error |
| `test_agent_config_dir_wins_over_global_one` | The agent's own directory is used for the command, the trust record and the lookup of saved conversations; agents without one use the global directory |
| `test_once_accepts_config_dir` | `open --once --claude-config-dir` |

### Unknown keys

| Test | Checks |
|---|---|
| `test_unknown_keys_are_reported` | A misspelled key in `config` or an agent file is reported, with the file name |
| `test_saved_files_contain_only_known_keys` | Files written by the tool give no such warning |

### Failures that are hard to reach

| Test | Checks |
|---|---|
| `test_start_goes_on_after_a_broken_agent` | When one agent raises an error, `start --autostart` reports it, starts the others and exits with status 1 |
| `test_wait_for_ready_answers_the_trust_dialog` | A trust question on the screen is answered with Enter, and the wait goes on until the prompt appears |
| `test_wait_for_ready_gives_up_when_the_screen_stops_changing` | A screen that stays the same (for example a login screen) ends the wait early, with that screen returned |
| `test_wait_for_ready_notices_that_claude_exited` | When the shell is in the foreground again, the wait ends with "claude exited" |
| `test_wait_for_ready_times_out` | The wait ends with "timed out" when the time is over |
| `test_interface_ip_of_the_loopback_interface` | The address of `lo` is found on the real system; an unknown interface gives none |
| `test_failed_write_leaves_no_temporary_file` | When a settings file cannot be replaced, the error is passed on and no temporary file is left |
| `test_pretrust_failure_leaves_no_temporary_file` | When `.claude.json` cannot be replaced, marking a directory as trusted reports failure and leaves no temporary file |

### attach

| Test | Checks |
|---|---|
| `test_attach_enters_the_named_session` | `attach <id>` enters the session of that running agent |
| `test_attach_without_id_needs_exactly_one_running_session` | Without an id: an error when nothing runs, the session when one runs, a list when several run |
| `test_attach_does_not_start_anything` | A stopped agent gives an error that names `start`; an unknown id is an error; nothing is started |
| `test_attach_to_the_own_session_does_nothing` | Naming the session the command runs in only says so |
| `test_attach_session_needs_a_terminal_and_does_not_nest_tmux` | Without a terminal it is an error; outside tmux the process becomes `tmux attach-session`; inside tmux the client is switched |

### completion

| Test | Checks |
|---|---|
| `test_completion_prints_a_bash_script_for_every_command` | The script registers itself for `launch_claude` and has an entry for every command |
| `test_completion_offers_only_options_that_the_help_lists` | Every option the completion offers is in the help text |
| `test_completion_ids_by_state` | `completion ids running`, `stopped` and `registered` print the right IDs, one per line |
| `test_completion_ids_stay_silent_when_something_is_wrong` | A failure while listing IDs prints nothing, so the shell prompt is not disturbed |
| `test_completion_for_another_shell_is_an_error` | Only bash is supported; `attach` and `completion` cannot be IDs |

## test_integration.py

Skipped when `tmux` is not installed; the ttyd tests also when `ttyd` is not installed.

| Test | Checks |
|---|---|
| `test_open_list_stop` | `open` starts a real tmux session, the stub gets the expected arguments and `/remote-control`, `list` shows it, `start` says it already runs, `stop` ends it |
| `test_stop_keeps_the_session_it_is_run_in` | With the environment tmux gives to a process inside a session: `stop <own id>` fails and stops nothing, `stop` alone keeps that session, `stop --stop-own-session` stops it |
| `test_once_is_listed_stopped_and_cleans_up_after_exit` | A throwaway session is listed and leaves no registration; it disappears by itself when claude exits; `stop` alone also finds one |
| `test_claude_exiting_immediately_is_detected_quickly` | When claude exits at once, the tool gives up in seconds and shows the last screen lines |
| `test_ttyd_session_is_started_and_stopped` | `open --with-ttyd` starts a real ttyd next to the session, prints a URL and warns that it is open without a password; `stop` ends both |
| `test_ttyd_can_be_opened_and_closed_on_a_running_session` | `ttyd <id>` and `ttyd <id> --off` on a running session; the agent keeps running and its saved setting stays off |
| `test_ttyd_on_loopback_only` | With `ttyd_interface = lo` a real ttyd starts without the warning, and `open` and `list` show a `localhost` URL |
| `test_bash_completion_with_real_sessions` | In a real bash with real sessions: commands, running, stopped and registered IDs, options, `--mode` values and directories are completed |

## test_docs.py

| Test | Checks |
|---|---|
| `test_readme_tables_list_every_setting` | The settings tables in both READMEs list exactly the keys the code knows |
| `test_config_samples_use_known_keys` | Every `examples/config.*` uses only known keys |
| `test_agent_samples_use_known_keys` | Every `examples/agents/*.conf` uses only known keys |
| `test_reference_samples_document_every_key` | `config.example` and `agents/example.conf` mention every key |
| `test_reference_config_sample_changes_nothing_as_is` | `config.example` has every key commented out |
| `test_relative_links_point_to_existing_files` | Relative links in the READMEs and `docs/` point to files that exist |
| `test_readme_contents_list_every_section` | The contents list in both READMEs matches the headings |
| `test_readme_lists_the_reserved_words` | The reserved words named in both READMEs are exactly the ones the code refuses as ids |
| `test_help_lists_every_command` | The help text names every command |
| `test_test_list_names_every_test` | The tables in this file name exactly the tests that exist |

## Not covered

- The real Claude Code: its start-up screen, the trust dialog, `/remote-control` and `/rename`. These were checked by hand.
- A browser connecting to ttyd.
- Systems other than the one the tests run on.
