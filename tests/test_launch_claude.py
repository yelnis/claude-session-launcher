"""Unit tests. tmux is faked (see conftest.py); nothing is started."""
import json
import os
import subprocess

import pytest

from conftest import load_script


def agent_file(lc, agent_id):
    return lc.agents_dir() / (agent_id + ".conf")


# ---- help ---------------------------------------------------------------

def test_no_arguments_prints_help_and_fails(lc, capsys):
    assert lc.main([]) == 1
    assert "Usage:" in capsys.readouterr().err
    assert lc.fake.launched == []


@pytest.mark.parametrize("arg", ["help", "-h", "--help"])
def test_help_succeeds(lc, capsys, arg):
    assert lc.main([arg]) == 0
    assert "Usage:" in capsys.readouterr().out


def test_version(lc, capsys):
    assert lc.main(["--version"]) == 0
    assert lc.__version__ in capsys.readouterr().out


def test_start_without_target_is_an_error(lc, capsys):
    assert lc.main(["start"]) == 1
    err = capsys.readouterr().err
    assert "start needs a target" in err and "Usage:" in err
    assert lc.fake.launched == []


def test_unknown_id_is_an_error(lc, capsys):
    assert lc.main(["nobody"]) == 1
    assert "not registered" in capsys.readouterr().err


# ---- ids ----------------------------------------------------------------

@pytest.mark.parametrize("word", ["all", "start", "stop", "open", "add", "set", "forget", "list", "help"])
def test_reserved_words_are_not_ids(lc, word):
    assert not lc.is_valid_id(word)


@pytest.mark.parametrize("bad", ["-x", "a b", "a/b", "", "_x", "a.b"])
def test_invalid_ids(lc, bad):
    assert not lc.is_valid_id(bad)


def test_valid_ids(lc):
    assert lc.is_valid_id("writer") and lc.is_valid_id("a-1_B")


def test_add_rejects_reserved_word(lc, workdir, capsys):
    assert lc.main(["add", "list"]) == 1
    assert "invalid ID" in capsys.readouterr().err


# ---- open ---------------------------------------------------------------

def test_open_registers_and_starts(lc, workdir, capsys):
    assert lc.main(["open", "review"]) == 0
    agent = lc.load_agent("review")
    assert agent == {"dir": str(workdir), "ttyd": True, "port": 7700, "mode": "new", "autostart": False}
    assert lc.fake.launched == [("review", str(workdir), 7700, "new", False)]
    assert "Registered [review]" in capsys.readouterr().out


def test_open_options_are_saved(lc, workdir, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    assert lc.main(["open", "--without-ttyd", "--autostart", "a", str(other)]) == 0
    agent = lc.load_agent("a")
    assert agent["dir"] == str(other) and not agent["ttyd"] and agent["port"] is None
    assert agent["autostart"] is True
    assert "port" not in agent_file(lc, "a").read_text()


def test_open_registered_uses_saved_settings_and_new_conversation(lc, workdir, tmp_path, monkeypatch):
    assert lc.main(["add", "a", "--port", "7750", "--mode", "continue"]) == 0
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert lc.main(["open", "a"]) == 0
    # saved dir/port win over the current directory; open defaults to a new conversation
    assert lc.fake.launched == [("a", str(workdir), 7750, "new", False)]
    assert lc.load_agent("a")["mode"] == "continue"


def test_open_overrides_are_saved_and_reported(lc, workdir, tmp_path, capsys):
    lc.main(["add", "a", "--port", "7750"])
    other = tmp_path / "other"
    other.mkdir()
    capsys.readouterr()
    assert lc.main(["open", "a", "--dir", str(other), "--port", "7751", "--autostart"]) == 0
    agent = lc.load_agent("a")
    assert (agent["dir"], agent["port"], agent["autostart"]) == (str(other), 7751, True)
    assert "Saved settings for [a]" in capsys.readouterr().out


@pytest.mark.parametrize("flag,mode", [("--resume", "resume"), ("--continue", "continue"),
                                       ("-c", "continue")])
def test_open_conversation_flags_apply_to_this_launch_only(lc, workdir, flag, mode):
    assert lc.main(["open", flag, "a"]) == 0
    assert lc.fake.launched[0][3] == mode
    assert lc.load_agent("a")["mode"] == "new"


def test_open_running_agent_is_skipped(lc, workdir, capsys):
    lc.main(["open", "a"])
    capsys.readouterr()
    assert lc.main(["open", "a"]) == 0
    assert "already running" in capsys.readouterr().out
    assert len(lc.fake.launched) == 1


def test_open_refuses_unmanaged_tmux_session(lc, workdir, capsys):
    lc.fake.unmanaged.add("mine")
    assert lc.main(["open", "mine"]) == 1
    assert "already exists" in capsys.readouterr().err
    assert lc.load_agent("mine") is None


def test_open_without_id_is_an_error(lc, workdir, capsys):
    assert lc.main(["open"]) == 1
    assert "needs an <id>" in capsys.readouterr().err


def test_open_missing_directory_is_an_error(lc, workdir, capsys):
    assert lc.main(["open", "a", str(workdir / "nope")]) == 1
    assert "not found" in capsys.readouterr().err
    assert lc.load_agent("a") is None


def test_open_continue_refuses_shared_directory(lc, workdir, capsys):
    lc.fake.run("other", directory=str(workdir))
    assert lc.main(["open", "--continue", "a"]) == 1
    assert "already running in" in capsys.readouterr().err
    assert lc.load_agent("a") is None


def test_port_and_without_ttyd_conflict(lc, workdir, capsys):
    assert lc.main(["open", "--port", "7701", "--without-ttyd", "a"]) == 1
    assert "--port cannot be used" in capsys.readouterr().err


def test_port_of_another_agent_is_refused(lc, workdir, capsys):
    lc.main(["add", "a", "--port", "7750"])
    assert lc.main(["add", "b", "--port", "7750"]) == 1
    assert "already assigned to [a]" in capsys.readouterr().err


def test_automatic_ports_skip_reserved_and_busy_ones(lc, workdir, monkeypatch):
    lc.main(["add", "a"])
    monkeypatch.setattr(lc, "port_is_free", lambda port: port != 7701)
    lc.main(["add", "b"])
    assert (lc.load_agent("a")["port"], lc.load_agent("b")["port"]) == (7700, 7702)


# ---- open --once --------------------------------------------------------

def test_once_is_not_registered(lc, workdir):
    assert lc.main(["open", "--once"]) == 0
    assert lc.registered_ids() == []
    agent_id, directory, port, mode, once = lc.fake.launched[0]
    assert agent_id.startswith("once-") and directory == str(workdir)
    assert (port, mode, once) == (None, "new", True)


def test_once_with_id_and_ttyd(lc, workdir):
    assert lc.main(["open", "--once", "--with-ttyd", "tmp1"]) == 0
    assert lc.registered_ids() == []
    assert lc.fake.launched == [("tmp1", str(workdir), 7700, "new", True)]


@pytest.mark.parametrize("flag", ["--resume", "--continue", "--autostart"])
def test_once_cannot_be_combined(lc, workdir, capsys, flag):
    assert lc.main(["open", "--once", flag]) == 1
    assert "--once cannot be combined with " + flag in capsys.readouterr().err
    assert lc.fake.launched == []


def test_once_refuses_registered_id(lc, workdir, capsys):
    lc.main(["add", "a"])
    assert lc.main(["open", "--once", "a"]) == 1
    assert "registered agent" in capsys.readouterr().err


# ---- add / set / forget / stop ------------------------------------------

def test_add_does_not_start(lc, workdir):
    assert lc.main(["add", "coder", "--port", "7683", "--mode", "continue", "--autostart"]) == 0
    assert lc.fake.launched == []
    assert lc.load_agent("coder") == {"dir": str(workdir), "ttyd": True, "port": 7683,
                                      "mode": "continue", "autostart": True}


def test_add_twice_is_an_error(lc, workdir, capsys):
    lc.main(["add", "a"])
    assert lc.main(["add", "a"]) == 1
    assert "already registered" in capsys.readouterr().err


def test_set_changes_settings(lc, workdir):
    lc.main(["add", "a"])
    assert lc.main(["set", "a", "--autostart", "--mode", "resume", "--without-ttyd"]) == 0
    agent = lc.load_agent("a")
    assert (agent["autostart"], agent["mode"], agent["ttyd"], agent["port"]) == (True, "resume", False, None)
    assert lc.main(["set", "a", "--no-autostart", "--with-ttyd"]) == 0
    agent = lc.load_agent("a")
    assert (agent["autostart"], agent["ttyd"], agent["port"]) == (False, True, 7700)


def test_set_unknown_agent_is_an_error(lc, capsys):
    assert lc.main(["set", "nobody", "--autostart"]) == 1
    assert "not registered" in capsys.readouterr().err


def test_stop_keeps_registration(lc, workdir):
    lc.main(["open", "a"])
    assert lc.main(["stop", "a"]) == 0
    assert lc.fake.killed == ["ttyd-a", "a"]
    assert lc.load_agent("a") is not None
    assert not lc.session_exists("a")


def test_stop_without_arguments_stops_everything_including_once(lc, workdir):
    lc.main(["open", "a"])
    lc.main(["open", "--once", "tmp1"])
    lc.main(["add", "idle"])
    assert lc.main(["stop"]) == 0
    assert lc.fake.managed == {}
    assert "idle" not in lc.fake.killed
    assert lc.registered_ids() == ["a", "idle"]


def test_stop_handles_own_session_last(lc, workdir, monkeypatch):
    for name in ("a", "b", "c"):
        lc.main(["open", name])
    monkeypatch.setattr(lc, "current_session", lambda: "a")
    lc.main(["stop"])
    assert [k for k in lc.fake.killed if not k.startswith("ttyd-")] == ["b", "c", "a"]


def test_stop_unknown_is_an_error(lc, capsys):
    assert lc.main(["stop", "nobody"]) == 1
    assert "neither registered nor a running session" in capsys.readouterr().err


def test_forget_removes_registration_and_state(lc, workdir):
    lc.main(["open", "a"])
    lc.save_state("a", last_session="x")
    lc.main(["stop", "a"])
    assert lc.main(["forget", "a"]) == 0
    assert lc.load_agent("a") is None
    assert not lc.state_path("a").exists()


def test_forget_running_agent_asks_to_stop(lc, workdir, capsys):
    lc.main(["open", "a"])
    assert lc.main(["forget", "a"]) == 1
    assert "launch_claude stop a" in capsys.readouterr().err
    assert lc.load_agent("a") is not None


# ---- start --------------------------------------------------------------

def test_start_autostart_only_starts_flagged_agents(lc, workdir):
    lc.main(["add", "a", "--autostart", "--mode", "continue"])
    lc.main(["add", "b"])
    lc.main(["add", "c", "--autostart", "--without-ttyd"])
    assert lc.main(["start", "--autostart"]) == 0
    assert lc.fake.launched == [("a", str(workdir), 7700, "continue", False),
                                ("c", str(workdir), None, "new", False)]


def test_start_skips_running_agents(lc, workdir, capsys):
    lc.main(["add", "a", "--autostart"])
    lc.main(["add", "b", "--autostart"])
    lc.fake.run("a", directory=str(workdir), port=7700)
    assert lc.main(["start", "--autostart"]) == 0
    assert [call[0] for call in lc.fake.launched] == ["b"]
    assert "[a] is already running" in capsys.readouterr().out


def test_start_ids_and_shortcut(lc, workdir):
    for name in ("a", "b", "c"):
        lc.main(["add", name])
    assert lc.main(["start", "a", "b"]) == 0
    assert lc.main(["c"]) == 0
    assert [call[0] for call in lc.fake.launched] == ["a", "b", "c"]


def test_start_skips_missing_directory(lc, workdir, tmp_path, capsys):
    gone = tmp_path / "gone"
    gone.mkdir()
    lc.main(["add", "a", "--dir", str(gone), "--autostart"])
    lc.main(["add", "b", "--autostart"])
    gone.rmdir()
    assert lc.main(["start", "--autostart"]) == 1
    assert [call[0] for call in lc.fake.launched] == ["b"]  # no fallback to $HOME
    assert "not found; skipped" in capsys.readouterr().err


def test_start_autostart_with_nothing_flagged(lc, workdir, capsys):
    lc.main(["add", "a"])
    assert lc.main(["start", "--autostart"]) == 0
    assert lc.fake.launched == []


def test_command_wins_over_id_of_the_same_name(lc, workdir, capsys):
    # A hand-made registration named like a command must not shadow the command.
    lc.save_agent("list", {"dir": str(workdir), "ttyd": False, "port": None, "mode": "new",
                           "autostart": False})
    assert lc.main(["list"]) == 0
    assert lc.fake.launched == []


# ---- list ---------------------------------------------------------------

def rows(capsys):
    lines = capsys.readouterr().out.splitlines()
    return {line.split()[0]: line for line in lines[1:] if line and not line.startswith("(")}, lines


def test_list_shows_registered_and_once(lc, workdir, tmp_path, monkeypatch, capsys):
    home_dir = tmp_path / "home" / "docs"
    home_dir.mkdir()
    gone = tmp_path / "gone"
    gone.mkdir()
    lc.main(["add", "writer", "--dir", str(home_dir), "--port", "7682", "--mode", "continue", "--autostart"])
    lc.main(["add", "coder", "--port", "7683", "--autostart"])
    lc.main(["add", "review", "--dir", str(gone), "--without-ttyd"])
    gone.rmdir()
    lc.main(["start", "writer"])
    lc.save_state("writer", last_started="2026-01-02T03:04:05")
    lc.fake.run("once-1", directory=str(workdir), kind="once")
    capsys.readouterr()

    assert lc.main(["list"]) == 0
    table, lines = rows(capsys)
    assert lines[0].split() == ["ID", "STATUS", "ACCESS", "DIR", "MODE", "AUTO", "LAST"]
    assert table["writer"].split() == ["writer", "running", "http://192.0.2.10:7682", "~/docs",
                                       "continue", "*", "01/02", "03:04"]
    assert table["coder"].split()[:6] == ["coder", "stopped", "-", str(workdir), "new", "*"]
    assert "(!)" in table["review"] and "stopped" in table["review"]
    assert "tmux only (once)" in table["once-1"] and "running" in table["once-1"]
    assert "(!) directory not found" in lines


def test_list_filters(lc, workdir, capsys):
    lc.main(["add", "a", "--autostart"])
    lc.main(["add", "b"])
    lc.main(["start", "b"])
    lc.fake.run("once-1", directory=str(workdir), kind="once")
    capsys.readouterr()

    lc.main(["list", "--running"])
    table, _ = rows(capsys)
    assert sorted(table) == ["b", "once-1"]

    lc.main(["list", "--autostart"])
    table, _ = rows(capsys)
    assert sorted(table) == ["a"]


def test_list_empty(lc, capsys):
    assert lc.main(["list"]) == 0
    assert "No agents." in capsys.readouterr().out


# ---- config files -------------------------------------------------------

def test_ini_round_trip_keeps_percent_signs(lc, tmp_path):
    path = tmp_path / "x" / "file.conf"
    lc.write_ini(path, "agent", {"dir": "/data/100%/%(home)s", "port": 7700, "skip": None})
    assert lc.read_ini(path, "agent") == {"dir": "/data/100%/%(home)s", "port": "7700"}
    assert [p.name for p in path.parent.iterdir()] == ["file.conf"]  # no temp file left


def test_settings_defaults_without_files(lc):
    settings = lc.load_settings()
    assert settings == {"claude_config_dir": None, "port_min": 7700, "port_max": 7799,
                        "remote_control": True, "ttyd_credential": None}


def test_settings_from_file_and_environment(lc, monkeypatch, capsys):
    path = lc.config_dir() / "config"
    path.parent.mkdir(parents=True)
    path.write_text("# my settings\n[launch_claude]\nclaude_config_dir = ~/.claude-alt\n"
                    "port_min = 8000\nport_max = 8009\nremote_control = 0\n"
                    "ttyd_credential = me:pa%ss\n")
    os.chmod(str(path), 0o644)
    settings = lc.load_settings()
    assert settings["claude_config_dir"] == os.path.expanduser("~/.claude-alt")
    assert (settings["port_min"], settings["port_max"]) == (8000, 8009)
    assert settings["remote_control"] is False
    assert settings["ttyd_credential"] == "me:pa%ss"
    assert "chmod 600" in capsys.readouterr().err

    os.chmod(str(path), 0o600)
    monkeypatch.setenv("REMOTE_CONTROL", "1")
    monkeypatch.setenv("TTYD_CREDENTIAL", "env:secret")
    settings = lc.load_settings()
    assert settings["remote_control"] is True and settings["ttyd_credential"] == "env:secret"
    assert capsys.readouterr().err == ""


def test_hand_written_agent_file(lc, tmp_path):
    lc.agents_dir().mkdir(parents=True)
    agent_file(lc, "hand").write_text("# comment\n[agent]\ndir = ~/proj\nttyd = 1\nport = 7711\n")
    assert lc.load_agent("hand") == {"dir": os.path.expanduser("~/proj"), "ttyd": True, "port": 7711,
                                     "mode": "new", "autostart": False}


# ---- launching (real launch_session, tmux command faked) ----------------

@pytest.fixture
def launcher(monkeypatch, tmp_path, workdir):
    """A freshly loaded module whose tmux() only records its calls."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".claude").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    for name in ("TMUX", "TMUX_PANE", "CLAUDE_CONFIG_DIR", "REMOTE_CONTROL", "TTYD_CREDENTIAL"):
        monkeypatch.delenv(name, raising=False)
    module = load_script()
    calls = []

    alive = set()

    def fake_tmux(*args):
        calls.append(args)
        code = 0
        if args[0] == "new-session":
            alive.add(args[args.index("-s") + 1])
        elif args[0] == "kill-session":
            alive.discard(args[-1].lstrip("="))
        elif args[0] == "has-session":
            code = 0 if args[-1].lstrip("=") in alive else 1
        return subprocess.CompletedProcess(args, code, stdout="", stderr="")

    module.calls = calls
    monkeypatch.setattr(module, "tmux", fake_tmux)
    monkeypatch.setattr(module, "require", lambda command: None)
    monkeypatch.setattr(module, "port_is_free", lambda port: True)
    monkeypatch.setattr(module, "wait_for_ready", lambda target, timeout=None: (True, "", ""))
    monkeypatch.setattr(module, "close_remote_control_dialog", lambda target: False)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    return module


def typed(module):
    return [args[-1] for args in module.calls if args[0] == "send-keys" and "-l" in args]


def test_new_conversation_uses_session_id_and_name(launcher, workdir):
    assert launcher.main(["open", "--without-ttyd", "a"]) == 0
    session_id = launcher.load_state("a")["last_session"]
    assert typed(launcher) == ["claude --session-id %s --name a" % session_id, "/remote-control a"]
    assert launcher.load_state("a")["last_started"]


def test_resume_falls_back_to_new_without_transcript(launcher, workdir, capsys):
    launcher.main(["add", "a", "--without-ttyd"])
    launcher.save_state("a", last_session="11111111-2222-3333-4444-555555555555")
    assert launcher.main(["open", "--resume", "a"]) == 0
    command = typed(launcher)[0]
    assert "--resume" not in command and "--session-id" in command and "--name a" in command
    assert "no conversation to resume" in capsys.readouterr().out
    assert launcher.load_state("a")["last_session"] != "11111111-2222-3333-4444-555555555555"


def test_resume_uses_uuid_when_transcript_exists(launcher, workdir, tmp_path):
    session_id = "11111111-2222-3333-4444-555555555555"
    project = tmp_path / "home" / ".claude" / "projects" / "-some-project"
    project.mkdir(parents=True)
    (project / (session_id + ".jsonl")).write_text("{}\n")
    launcher.main(["add", "a", "--without-ttyd", "--mode", "resume"])
    launcher.save_state("a", last_session=session_id)
    assert launcher.main(["start", "a"]) == 0
    assert typed(launcher)[0] == "claude --resume " + session_id
    assert launcher.load_state("a")["last_session"] == session_id


def test_continue_renames_and_respects_remote_control_off(launcher, workdir, monkeypatch):
    monkeypatch.setenv("REMOTE_CONTROL", "0")
    assert launcher.main(["open", "--continue", "--without-ttyd", "a"]) == 0
    assert typed(launcher) == ["claude --continue || claude --name a", "/rename a"]


def test_claude_config_dir_is_quoted_and_once_cleans_up(launcher, workdir):
    path = launcher.config_dir() / "config"
    path.parent.mkdir(parents=True)
    path.write_text("[launch_claude]\nclaude_config_dir = /opt/my claude\nremote_control = 0\n")
    assert launcher.main(["open", "--once", "tmp1"]) == 0
    command = typed(launcher)[0]
    assert command.startswith("CLAUDE_CONFIG_DIR='/opt/my claude' claude --session-id ")
    assert command.endswith("launch_claude stop tmp1 >/dev/null 2>&1")
    assert os.path.realpath(launcher.__file__) in command
    assert launcher.registered_ids() == []
    assert not launcher.state_path("tmp1").exists()


def test_ttyd_is_started_with_credential(launcher, workdir, monkeypatch):
    monkeypatch.setenv("TTYD_CREDENTIAL", "me:secret")
    assert launcher.main(["open", "--port", "7701", "a"]) == 0
    ttyd = [args for args in launcher.calls if args[0] == "new-session" and "ttyd-a" in args][0]
    assert ttyd[ttyd.index("ttyd"):ttyd.index("ttyd") + 6] == ("ttyd", "-p", "7701", "-W", "-c", "me:secret")


def test_pretrust_writes_claude_json(launcher, workdir, tmp_path):
    claude_json = tmp_path / "home" / ".claude.json"
    claude_json.write_text('{"other": 1, "projects": {"/x": {"keep": true}}}')
    os.chmod(str(claude_json), 0o600)
    launcher.main(["open", "--without-ttyd", "a"])
    data = json.loads(claude_json.read_text())
    assert data["other"] == 1 and data["projects"]["/x"] == {"keep": True}
    assert data["projects"][str(workdir)]["hasTrustDialogAccepted"] is True
    assert (claude_json.stat().st_mode & 0o777) == 0o600


def test_missing_tmux_is_reported(lc, monkeypatch, capsys):
    monkeypatch.setattr(lc.shutil, "which", lambda command: None)
    with pytest.raises(lc.Error, match="'tmux' was not found"):
        lc.require("tmux")
    with pytest.raises(lc.Error, match="--without-ttyd"):
        lc.require("ttyd")


def test_remote_control_dialog_is_closed_only_on_continue(lc, monkeypatch):
    dialog = "  Remote Control\n  This session is available\n    Disconnect this session\n  \u276f Continue\n"
    other = "  Remote Control\n  \u276f Disconnect this session\n    Continue\n"
    sent = []
    monkeypatch.setattr(lc, "tmux", lambda *args: sent.append(args))
    monkeypatch.setattr(lc.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(lc, "DIALOG_TIMEOUT", 0.2)

    monkeypatch.setattr(lc, "capture_pane", lambda target: dialog)
    assert lc.close_remote_control_dialog("=a:") is True
    assert sent == [("send-keys", "-t", "=a:", "Enter")]

    sent.clear()
    monkeypatch.setattr(lc, "capture_pane", lambda target: other)
    assert lc.close_remote_control_dialog("=a:") is False
    assert sent == []
