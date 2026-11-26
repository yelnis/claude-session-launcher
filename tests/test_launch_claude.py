"""Unit tests. tmux is faked (see conftest.py); nothing is started."""
import json
import os
import subprocess

from types import SimpleNamespace

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

@pytest.mark.parametrize("word", ["all", "start", "stop", "open", "attach", "add", "set", "forget", "list",
                                  "completion", "up", "down", "o", "a", "help"])
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
    assert agent == {"dir": str(workdir), "ttyd": False, "port": None, "mode": "new", "autostart": False,
                     "claude_config_dir": None}
    assert lc.fake.launched == [("review", str(workdir), None, "new", False)]  # tmux only by default
    assert "Registered [review]" in capsys.readouterr().out


def test_open_with_ttyd_picks_and_saves_a_port(lc, workdir):
    assert lc.main(["open", "--with-ttyd", "web"]) == 0
    assert (lc.load_agent("web")["ttyd"], lc.load_agent("web")["port"]) == (True, 7700)
    assert lc.fake.launched == [("web", str(workdir), 7700, "new", False)]
    assert lc.main(["add", "fixed", "--port", "7705"]) == 0  # --port alone implies ttyd
    assert (lc.load_agent("fixed")["ttyd"], lc.load_agent("fixed")["port"]) == (True, 7705)


def test_open_mode_option_points_to_the_right_options(lc, workdir, capsys):
    assert lc.main(["open", "--mode", "continue", "aa"]) == 1
    err = capsys.readouterr().err
    assert "--resume or --continue" in err and "launch_claude set <id> --mode continue" in err
    assert lc.load_agent("aa") is None and lc.fake.launched == []


def test_open_options_are_saved(lc, workdir, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    assert lc.main(["open", "--without-ttyd", "--autostart", "aa", str(other)]) == 0
    agent = lc.load_agent("aa")
    assert agent["dir"] == str(other) and not agent["ttyd"] and agent["port"] is None
    assert agent["autostart"] is True
    assert "port" not in agent_file(lc, "aa").read_text()


def test_open_registered_uses_saved_settings_and_new_conversation(lc, workdir, tmp_path, monkeypatch):
    assert lc.main(["add", "aa", "--port", "7750", "--mode", "continue"]) == 0
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert lc.main(["open", "aa"]) == 0
    # saved dir/port win over the current directory; open defaults to a new conversation
    assert lc.fake.launched == [("aa", str(workdir), 7750, "new", False)]
    assert lc.load_agent("aa")["mode"] == "continue"


def test_open_overrides_are_saved_and_reported(lc, workdir, tmp_path, capsys):
    lc.main(["add", "aa", "--port", "7750"])
    other = tmp_path / "other"
    other.mkdir()
    capsys.readouterr()
    assert lc.main(["open", "aa", "--dir", str(other), "--port", "7751", "--autostart"]) == 0
    agent = lc.load_agent("aa")
    assert (agent["dir"], agent["port"], agent["autostart"]) == (str(other), 7751, True)
    assert "Saved settings for [aa]" in capsys.readouterr().out


@pytest.mark.parametrize("flag,mode", [("--resume", "resume"), ("--continue", "continue"),
                                       ("-c", "continue")])
def test_open_conversation_flags_apply_to_this_launch_only(lc, workdir, flag, mode):
    assert lc.main(["open", flag, "aa"]) == 0
    assert lc.fake.launched[0][3] == mode
    assert lc.load_agent("aa")["mode"] == "new"


def test_open_running_agent_is_skipped(lc, workdir, capsys):
    lc.main(["open", "aa"])
    capsys.readouterr()
    assert lc.main(["open", "aa"]) == 0
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
    assert lc.main(["open", "aa", str(workdir / "nope")]) == 1
    assert "not found" in capsys.readouterr().err
    assert lc.load_agent("aa") is None


def test_open_continue_refuses_shared_directory(lc, workdir, capsys):
    lc.fake.run("other", directory=str(workdir))
    assert lc.main(["open", "--continue", "aa"]) == 1
    assert "already running in" in capsys.readouterr().err
    assert lc.load_agent("aa") is None


def test_port_with_ttyd_off_is_reserved(lc, workdir, capsys):
    assert lc.main(["open", "--port", "7701", "--without-ttyd", "aa"]) == 0
    agent = lc.load_agent("aa")
    assert (agent["ttyd"], agent["port"]) == (False, 7701)
    assert "ttyd=off (port 7701 reserved)" in capsys.readouterr().out
    assert lc.fake.launched == [("aa", str(workdir), None, "new", False)]  # started without ttyd
    # the reserved port is not handed to anyone else
    assert lc.main(["add", "b", "--port", "7701"]) == 1
    lc.main(["add", "c", "--with-ttyd"])
    assert lc.load_agent("c")["port"] == 7700


def test_once_port_needs_ttyd(lc, workdir, capsys):
    assert lc.main(["open", "--once", "--port", "7701", "--without-ttyd"]) == 1
    assert "--once saves nothing" in capsys.readouterr().err


def test_port_of_another_agent_is_refused(lc, workdir, capsys):
    lc.main(["add", "aa", "--port", "7750"])
    assert lc.main(["add", "b", "--port", "7750"]) == 1
    assert "already assigned to [aa]" in capsys.readouterr().err


def test_automatic_ports_skip_reserved_and_busy_ones(lc, workdir, monkeypatch):
    lc.main(["add", "aa", "--with-ttyd"])
    monkeypatch.setattr(lc, "port_is_free", lambda port: port != 7701)
    lc.main(["add", "b", "--with-ttyd"])
    assert (lc.load_agent("aa")["port"], lc.load_agent("b")["port"]) == (7700, 7702)


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
    lc.main(["add", "aa"])
    assert lc.main(["open", "--once", "aa"]) == 1
    assert "registered agent" in capsys.readouterr().err


# ---- add / set / forget / stop ------------------------------------------

def test_add_does_not_start(lc, workdir):
    assert lc.main(["add", "coder", "--port", "7683", "--mode", "continue", "--autostart"]) == 0
    assert lc.fake.launched == []
    assert lc.load_agent("coder") == {"dir": str(workdir), "ttyd": True, "port": 7683,
                                      "mode": "continue", "autostart": True, "claude_config_dir": None}


def test_add_twice_is_an_error(lc, workdir, capsys):
    lc.main(["add", "aa"])
    assert lc.main(["add", "aa"]) == 1
    assert "already registered" in capsys.readouterr().err


def test_set_changes_settings(lc, workdir):
    lc.main(["add", "aa", "--with-ttyd"])
    assert lc.main(["set", "aa", "--autostart", "--mode", "resume", "--without-ttyd"]) == 0
    agent = lc.load_agent("aa")
    # turning ttyd off keeps the port, so turning it on again gives the same URL
    assert (agent["autostart"], agent["mode"], agent["ttyd"], agent["port"]) == (True, "resume", False, 7700)
    assert lc.main(["set", "aa", "--no-autostart", "--with-ttyd"]) == 0
    agent = lc.load_agent("aa")
    assert (agent["autostart"], agent["ttyd"], agent["port"]) == (False, True, 7700)


def test_set_port_alone_implies_ttyd_but_not_with_without_ttyd(lc, workdir):
    lc.main(["add", "aa", "--without-ttyd"])
    assert lc.load_agent("aa")["port"] is None
    lc.main(["set", "aa", "--port", "7710", "--without-ttyd"])
    assert (lc.load_agent("aa")["ttyd"], lc.load_agent("aa")["port"]) == (False, 7710)
    lc.main(["set", "aa", "--port", "7711"])
    assert (lc.load_agent("aa")["ttyd"], lc.load_agent("aa")["port"]) == (True, 7711)


def test_set_unknown_agent_is_an_error(lc, capsys):
    assert lc.main(["set", "nobody", "--autostart"]) == 1
    assert "not registered" in capsys.readouterr().err


def test_stop_keeps_registration(lc, workdir):
    lc.main(["open", "aa"])
    assert lc.main(["stop", "aa"]) == 0
    assert lc.fake.killed == ["ttyd-aa", "aa"]
    assert lc.load_agent("aa") is not None
    assert not lc.session_exists("aa")


def test_stop_without_arguments_stops_nothing_and_lists_what_runs(lc, workdir, monkeypatch, capsys):
    assert lc.main(["stop"]) == 0  # nothing runs: nothing to ask for
    assert "Nothing is running." in capsys.readouterr().out
    lc.main(["open", "aa"])
    lc.main(["open", "b"])
    monkeypatch.setattr(lc, "current_session", lambda: "b")
    assert lc.main(["stop"]) == 1
    assert "add --all to stop everything that is running: aa\n" in capsys.readouterr().err
    assert lc.main(["stop", "--all", "aa"]) == 1
    assert lc.fake.killed == []


def test_stop_all_stops_everything_including_once(lc, workdir):
    lc.main(["open", "aa"])
    lc.main(["open", "--once", "tmp1"])
    lc.main(["add", "idle"])
    assert lc.main(["stop", "--all"]) == 0
    assert lc.fake.managed == {}
    assert "idle" not in lc.fake.killed
    assert lc.registered_ids() == ["aa", "idle"]


def test_stop_all_keeps_own_session(lc, workdir, monkeypatch, capsys):
    for name in ("aa", "b", "c"):
        lc.main(["open", name])
    monkeypatch.setattr(lc, "current_session", lambda: "aa")
    assert lc.main(["stop", "--all"]) == 0
    assert [k for k in lc.fake.killed if not k.startswith("ttyd-")] == ["b", "c"]
    assert lc.session_exists("aa")
    assert "[aa] is the session this command runs in; not stopped" in capsys.readouterr().out
    assert lc.main(["stop"]) == 0  # only the own session is left: nothing to name
    assert "Nothing else is running." in capsys.readouterr().out


def test_stop_own_session_by_id_is_an_error_and_stops_nothing(lc, workdir, monkeypatch, capsys):
    for name in ("aa", "b"):
        lc.main(["open", name])
    monkeypatch.setattr(lc, "current_session", lambda: "aa")
    assert lc.main(["stop", "b", "aa"]) == 1
    assert "--stop-own-session" in capsys.readouterr().err
    assert lc.fake.killed == []


def test_stop_own_session_when_asked_stops_it_last(lc, workdir, monkeypatch):
    for name in ("aa", "b", "c"):
        lc.main(["open", name])
    monkeypatch.setattr(lc, "current_session", lambda: "aa")
    assert lc.main(["down", "--all", "--stop-own-session"]) == 0  # "down" is the short name
    assert [k for k in lc.fake.killed if not k.startswith("ttyd-")] == ["b", "c", "aa"]
    lc.main(["open", "aa"])
    assert lc.main(["stop", "--stop-own-session", "aa"]) == 0
    assert not lc.session_exists("aa")


def test_stop_from_a_session_of_another_tool_stops_everything(lc, workdir, monkeypatch):
    lc.main(["open", "aa"])
    monkeypatch.setattr(lc, "current_session", lambda: "somebody-else")
    assert lc.main(["stop", "--all"]) == 0
    assert not lc.session_exists("aa")


def test_stop_leaves_a_tmux_session_that_only_shares_the_name(lc, workdir, capsys):
    lc.main(["add", "work"])
    lc.fake.unmanaged.add("work")  # the user's own "tmux new -s work"
    lc.main(["open", "aa"])
    assert lc.main(["stop", "--all"]) == 0
    assert lc.main(["stop", "work"]) == 0
    assert "launch_claude did not start it; not stopped" in capsys.readouterr().err
    assert lc.fake.killed == ["ttyd-aa", "aa"] and lc.session_exists("work")


def test_stop_unknown_is_an_error(lc, capsys):
    assert lc.main(["stop", "nobody"]) == 1
    assert "neither registered nor a running session" in capsys.readouterr().err


def test_forget_removes_registration_and_state(lc, workdir):
    lc.main(["open", "aa"])
    lc.save_state("aa", last_session="x")
    lc.main(["stop", "aa"])
    assert lc.main(["forget", "aa"]) == 0
    assert lc.load_agent("aa") is None
    assert not lc.state_path("aa").exists()


def test_forget_running_agent_asks_to_stop(lc, workdir, capsys):
    lc.main(["open", "aa"])
    assert lc.main(["forget", "aa"]) == 1
    assert "launch_claude stop aa" in capsys.readouterr().err
    assert lc.load_agent("aa") is not None


# ---- start --------------------------------------------------------------

def test_start_autostart_only_starts_flagged_agents(lc, workdir):
    lc.main(["add", "aa", "--autostart", "--mode", "continue", "--with-ttyd"])
    lc.main(["add", "b"])
    lc.main(["add", "c", "--autostart", "--without-ttyd"])
    assert lc.main(["start", "--autostart"]) == 0
    assert lc.fake.launched == [("aa", str(workdir), 7700, "continue", False),
                                ("c", str(workdir), None, "new", False)]


def test_start_skips_running_agents(lc, workdir, capsys):
    lc.main(["add", "aa", "--autostart"])
    lc.main(["add", "b", "--autostart"])
    lc.fake.run("aa", directory=str(workdir), port=7700)
    assert lc.main(["start", "--autostart"]) == 0
    assert [call[0] for call in lc.fake.launched] == ["b"]
    assert "[aa] is already running" in capsys.readouterr().out


def test_start_ids_and_shortcut(lc, workdir):
    for name in ("aa", "b", "c"):
        lc.main(["add", name])
    assert lc.main(["start", "aa", "b"]) == 0
    assert lc.main(["c"]) == 0
    assert [call[0] for call in lc.fake.launched] == ["aa", "b", "c"]


def test_start_skips_missing_directory(lc, workdir, tmp_path, capsys):
    gone = tmp_path / "gone"
    gone.mkdir()
    lc.main(["add", "aa", "--dir", str(gone), "--autostart"])
    lc.main(["add", "b", "--autostart"])
    gone.rmdir()
    assert lc.main(["start", "--autostart"]) == 1
    assert [call[0] for call in lc.fake.launched] == ["b"]  # no fallback to $HOME
    assert "not found; skipped" in capsys.readouterr().err


def test_start_autostart_with_nothing_flagged(lc, workdir, capsys):
    lc.main(["add", "aa"])
    assert lc.main(["start", "--autostart"]) == 0
    assert lc.fake.launched == []


def test_command_wins_over_id_of_the_same_name(lc, workdir, capsys):
    # A hand-made registration named like a command must not shadow the command.
    lc.save_agent("list", {"dir": str(workdir), "ttyd": False, "port": None, "mode": "new",
                           "autostart": False, "claude_config_dir": None})
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
    lc.main(["add", "aa", "--autostart"])
    lc.main(["add", "b"])
    lc.main(["start", "b"])
    lc.fake.run("once-1", directory=str(workdir), kind="once")
    capsys.readouterr()

    lc.main(["list", "--running"])
    table, _ = rows(capsys)
    assert sorted(table) == ["b", "once-1"]

    lc.main(["list", "--autostart"])
    table, _ = rows(capsys)
    assert sorted(table) == ["aa"]


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
                        "remote_control": True, "ttyd_credential": None, "ttyd_interface": None,
                        "ttyd_warning": True}


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
                                     "mode": "new", "autostart": False, "claude_config_dir": None}


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
            name = args[args.index("-s") + 1]
            if module.ttyd_binds or not name.startswith("ttyd-"):
                alive.add(name)
        elif args[0] == "kill-session":
            alive.discard(args[-1].lstrip("="))
        elif args[0] == "has-session":
            code = 0 if args[-1].lstrip("=") in alive else 1
        return subprocess.CompletedProcess(args, code, stdout="", stderr="")

    module.calls = calls
    monkeypatch.setattr(module, "tmux", fake_tmux)
    monkeypatch.setattr(module, "require", lambda command: None)
    module.ttyd_binds = True
    monkeypatch.setattr(module, "port_is_free", lambda port: not any(n.startswith("ttyd-") for n in alive))
    monkeypatch.setattr(module, "wait_for_ready", lambda target, timeout=None: (True, "", ""))
    monkeypatch.setattr(module, "close_remote_control_dialog", lambda target: False)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    return module


def typed(module):
    return [args[-1] for args in module.calls if args[0] == "send-keys" and "-l" in args]


def test_new_conversation_uses_session_id_and_name(launcher, workdir):
    assert launcher.main(["open", "--without-ttyd", "aa"]) == 0
    session_id = launcher.load_state("aa")["last_session"]
    assert typed(launcher) == ["claude --session-id %s --name aa" % session_id, "/remote-control aa"]
    assert launcher.load_state("aa")["last_started"]


def test_resume_falls_back_to_new_without_transcript(launcher, workdir, capsys):
    launcher.main(["add", "aa", "--without-ttyd"])
    launcher.save_state("aa", last_session="11111111-2222-3333-4444-555555555555")
    assert launcher.main(["open", "--resume", "aa"]) == 0
    command = typed(launcher)[0]
    assert "--resume" not in command and "--session-id" in command and "--name aa" in command
    assert "no conversation to resume" in capsys.readouterr().out
    assert launcher.load_state("aa")["last_session"] != "11111111-2222-3333-4444-555555555555"


def test_resume_uses_uuid_when_transcript_exists(launcher, workdir, tmp_path):
    session_id = "11111111-2222-3333-4444-555555555555"
    project = tmp_path / "home" / ".claude" / "projects" / "-some-project"
    project.mkdir(parents=True)
    (project / (session_id + ".jsonl")).write_text("{}\n")
    launcher.main(["add", "aa", "--without-ttyd", "--mode", "resume"])
    launcher.save_state("aa", last_session=session_id)
    assert launcher.main(["start", "aa"]) == 0
    assert typed(launcher)[0] == "claude --resume " + session_id
    assert launcher.load_state("aa")["last_session"] == session_id


def test_continue_renames_and_respects_remote_control_off(launcher, workdir, monkeypatch):
    monkeypatch.setenv("REMOTE_CONTROL", "0")
    assert launcher.main(["open", "--continue", "--without-ttyd", "aa"]) == 0
    assert typed(launcher) == ["claude --continue || claude --name aa", "/rename aa"]


def test_claude_config_dir_is_quoted_and_once_cleans_up(launcher, workdir):
    path = launcher.config_dir() / "config"
    path.parent.mkdir(parents=True)
    path.write_text("[launch_claude]\nclaude_config_dir = /opt/my claude\nremote_control = 0\n")
    assert launcher.main(["open", "--once", "tmp1"]) == 0
    command = typed(launcher)[0]
    assert command.startswith("CLAUDE_CONFIG_DIR='/opt/my claude' claude --session-id ")
    assert command.endswith("launch_claude stop --stop-own-session tmp1 >/dev/null 2>&1")
    assert os.path.realpath(launcher.__file__) in command
    assert launcher.registered_ids() == []
    assert not launcher.state_path("tmp1").exists()


def test_ttyd_is_started_with_credential(launcher, workdir, monkeypatch):
    monkeypatch.setenv("TTYD_CREDENTIAL", "me:secret")
    assert launcher.main(["open", "--port", "7701", "aa"]) == 0
    ttyd = [args for args in launcher.calls if args[0] == "new-session" and "ttyd-aa" in args][0]
    assert ttyd[ttyd.index("ttyd"):ttyd.index("ttyd") + 6] == ("ttyd", "-p", "7701", "-W", "-c", "me:secret")


def test_pretrust_writes_claude_json(launcher, workdir, tmp_path):
    claude_json = tmp_path / "home" / ".claude.json"
    claude_json.write_text('{"other": 1, "projects": {"/x": {"keep": true}}}')
    os.chmod(str(claude_json), 0o600)
    launcher.main(["open", "--without-ttyd", "aa"])
    data = json.loads(claude_json.read_text())
    assert data["other"] == 1 and data["projects"]["/x"] == {"keep": True}
    assert data["projects"][str(workdir)]["hasTrustDialogAccepted"] is True
    assert (claude_json.stat().st_mode & 0o777) == 0o600


def test_missing_tmux_is_reported(lc, monkeypatch, capsys):
    monkeypatch.setattr(lc.shutil, "which", lambda command: None)
    with pytest.raises(lc.Error, match="'tmux' was not found"):
        lc.require("tmux")
    with pytest.raises(lc.Error, match="only needed for sessions served in the browser.*crontab"):
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


def port_option_values(module):
    return [args[-1] for args in module.calls
            if args[0] == "set-option" and args[-2] == "@launch_claude_port"]


def test_ttyd_that_cannot_bind_is_reported_and_session_keeps_running(launcher, workdir, capsys):
    launcher.ttyd_binds = False  # ttyd exits at once, e.g. someone else took the port
    launcher.TTYD_TIMEOUT = 0.3
    assert launcher.main(["open", "--port", "7701", "aa"]) == 0
    out, err = capsys.readouterr()
    assert "ttyd did not start on port 7701" in err and "runs without ttyd" in err
    assert "http://" not in out and "tmux attach -t aa" in out  # no URL for a port that is not ours
    port_options = port_option_values(launcher)
    assert set(port_options) == {""}


def test_started_ttyd_records_its_port(launcher, workdir):
    assert launcher.main(["open", "--port", "7701", "aa"]) == 0
    port_options = port_option_values(launcher)
    assert port_options[-1] == "7701"


# ---- ttyd command -------------------------------------------------------

def test_ttyd_opens_on_saved_port_without_changing_settings(lc, workdir, capsys):
    lc.main(["open", "--port", "7701", "--without-ttyd", "aa"])
    capsys.readouterr()
    assert lc.main(["ttyd", "aa"]) == 0
    out, err = capsys.readouterr()
    assert lc.fake.ttyd_started == [("aa", 7701)]
    assert "Opened ttyd for [aa]: http://192.0.2.10:7701" in out and "ttyd aa --off" in out
    assert "without a password of its own" in err and "ttyd_warning = 0" in err
    assert lc.load_agent("aa")["ttyd"] is False  # temporary: the saved setting stays off

    lc.main(["list"])
    assert "http://192.0.2.10:7701" in capsys.readouterr().out

    assert lc.main(["ttyd", "aa"]) == 0  # second call does nothing
    assert "already open" in capsys.readouterr().out
    assert len(lc.fake.ttyd_started) == 1

    assert lc.main(["ttyd", "aa", "--off"]) == 0
    assert "Closed ttyd for [aa]" in capsys.readouterr().out
    assert "ttyd-aa" in lc.fake.killed and lc.session_exists("aa")
    lc.main(["list"])
    assert "tmux only" in capsys.readouterr().out


def test_ttyd_port_option_and_automatic_port(lc, workdir, capsys):
    lc.main(["open", "--without-ttyd", "aa"])
    lc.main(["open", "--once", "tmp1"])
    assert lc.main(["ttyd", "aa", "--port", "7720"]) == 0
    assert lc.main(["ttyd", "tmp1"]) == 0  # unregistered --once session, no saved port
    assert lc.fake.ttyd_started == [("aa", 7720), ("tmp1", 7700)]
    assert lc.load_agent("aa")["port"] is None


def test_open_ttyd_warning_is_shown_once_and_only_when_open(lc, capsys):
    base = {"ttyd_warning": True, "ttyd_credential": "", "ttyd_interface": ""}
    for quiet in (dict(base, ttyd_warning=False), dict(base, ttyd_credential="me:secret"),
                  dict(base, ttyd_interface="lo")):
        lc.warn_open_ttyd(quiet)
    assert capsys.readouterr().err == ""
    lc.warn_open_ttyd(dict(base, ttyd_interface="eth0"))
    assert "on eth0 without a password of its own" in capsys.readouterr().err
    lc.warn_open_ttyd(base)  # the same run: not repeated for every agent
    assert capsys.readouterr().err == ""


def test_ttyd_no_warning_with_credential(lc, workdir, monkeypatch, capsys):
    monkeypatch.setenv("TTYD_CREDENTIAL", "me:secret")
    lc.main(["open", "--without-ttyd", "aa"])
    capsys.readouterr()
    assert lc.main(["ttyd", "aa"]) == 0
    assert capsys.readouterr().err == ""


def test_ttyd_warning_can_be_turned_off(lc, workdir, capsys):
    path = lc.config_dir() / "config"
    path.parent.mkdir(parents=True)
    path.write_text("[launch_claude]\nttyd_warning = 0\n")
    lc.main(["open", "--without-ttyd", "aa"])
    capsys.readouterr()
    assert lc.main(["ttyd", "aa"]) == 0
    assert capsys.readouterr().err == ""


def test_ttyd_errors(lc, workdir, capsys):
    lc.main(["add", "aa", "--without-ttyd"])
    lc.main(["add", "b", "--port", "7750"])
    assert lc.main(["ttyd", "aa"]) == 1
    assert "is not running" in capsys.readouterr().err
    assert lc.main(["ttyd", "nobody"]) == 1
    assert "neither registered nor a running session" in capsys.readouterr().err
    lc.fake.run("aa", directory=str(workdir))
    assert lc.main(["ttyd", "aa", "--port", "7750"]) == 1
    assert "already assigned to [b]" in capsys.readouterr().err
    assert lc.main(["ttyd", "aa", "--off", "--port", "7701"]) == 1
    assert lc.main(["ttyd", "aa", "--off"]) == 0
    assert "ttyd is not open" in capsys.readouterr().out
    assert lc.fake.ttyd_started == []


def test_ttyd_is_reserved(lc):
    assert not lc.is_valid_id("ttyd")


# ---- ttyd_interface -----------------------------------------------------

def write_config(module, text):
    path = module.config_dir() / "config"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[launch_claude]\n" + text)


@pytest.mark.parametrize("value,expected", [("lo", "lo"), ("localhost", "lo"), ("127.0.0.1", "127.0.0.1"),
                                            ("eth0", "eth0"), ("192.0.2.7", "192.0.2.7"), ("", None)])
def test_interface_values(lc, value, expected):
    write_config(lc, "ttyd_interface = %s\n" % value)
    assert lc.load_settings()["ttyd_interface"] == expected


def test_interface_socket_path_is_refused(lc, workdir, capsys):
    write_config(lc, "ttyd_interface = /run/ttyd.sock\n")
    assert lc.main(["list"]) == 1
    assert "UNIX socket paths are not supported" in capsys.readouterr().err


def test_loopback_interface_gives_localhost_urls_and_no_warning(lc, workdir, capsys):
    write_config(lc, "ttyd_interface = lo\n")
    lc.main(["open", "--without-ttyd", "aa"])
    capsys.readouterr()
    assert lc.main(["ttyd", "aa"]) == 0
    out, err = capsys.readouterr()
    assert "http://localhost:7700" in out
    assert err == ""  # only reachable from this machine: nothing to warn about
    lc.main(["list"])
    assert "http://localhost:7700" in capsys.readouterr().out


def test_url_host_for_addresses_and_interface_names(lc, monkeypatch):
    assert lc.url_host({"ttyd_interface": None}) == "192.0.2.10"
    assert lc.url_host({"ttyd_interface": "192.0.2.7"}) == "192.0.2.7"
    monkeypatch.setattr(lc, "interface_ip", lambda name: {"vpn0": "198.51.100.4"}.get(name))
    assert lc.url_host({"ttyd_interface": "vpn0"}) == "198.51.100.4"
    assert lc.url_host({"ttyd_interface": "nosuch0"}) == "192.0.2.10"  # falls back to the usual address


def test_interface_is_passed_to_ttyd(launcher, workdir):
    write_config(launcher, "ttyd_interface = lo\nremote_control = 0\n")
    assert launcher.main(["open", "--port", "7701", "aa"]) == 0
    ttyd = [args for args in launcher.calls if args[0] == "new-session" and "ttyd-aa" in args][0]
    start = ttyd.index("ttyd")
    assert ttyd[start:start + 6] == ("ttyd", "-p", "7701", "-W", "-i", "lo")


# ---- per-agent claude_config_dir ----------------------------------------

def test_agent_config_dir_is_saved_changed_and_removed(lc, workdir, tmp_path, capsys):
    work = tmp_path / "claude-work"
    work.mkdir()
    assert lc.main(["add", "aa", "--claude-config-dir", str(work)]) == 0
    assert lc.load_agent("aa")["claude_config_dir"] == str(work)
    assert "claude_config_dir=" + str(work) in capsys.readouterr().out
    assert "claude_config_dir = " + str(work) in agent_file(lc, "aa").read_text()

    assert lc.main(["set", "aa", "--claude-config-dir", "default"]) == 0
    assert lc.load_agent("aa")["claude_config_dir"] is None
    assert "claude_config_dir" not in agent_file(lc, "aa").read_text()


def test_missing_config_dir_only_warns(lc, workdir, tmp_path, capsys):
    assert lc.main(["add", "aa", "--claude-config-dir", str(tmp_path / "nope")]) == 0
    assert "claude auth login" in capsys.readouterr().err
    assert lc.load_agent("aa")["claude_config_dir"] == str(tmp_path / "nope")


def test_agent_config_dir_wins_over_global_one(launcher, workdir, tmp_path):
    other = tmp_path / "claude-other"
    (other / "projects" / "-p").mkdir(parents=True)
    session_id = "11111111-2222-3333-4444-555555555555"
    (other / "projects" / "-p" / (session_id + ".jsonl")).write_text("{}\n")
    write_config(launcher, "claude_config_dir = /opt/global-claude\nremote_control = 0\n")
    launcher.main(["add", "aa", "--without-ttyd", "--mode", "resume", "--claude-config-dir", str(other)])
    launcher.main(["add", "b", "--without-ttyd"])
    launcher.save_state("aa", last_session=session_id)

    assert launcher.main(["start", "aa", "b"]) == 0
    first, second = typed(launcher)
    # the transcript is looked up in, and claude is started with, the agent's own directory
    assert first == "CLAUDE_CONFIG_DIR=%s claude --resume %s" % (other, session_id)
    assert second.startswith("CLAUDE_CONFIG_DIR=/opt/global-claude claude --session-id ")
    # ... and the work directory is marked as trusted there
    assert str(workdir) in json.loads((other / ".claude.json").read_text())["projects"]


def test_once_accepts_config_dir(launcher, workdir, tmp_path):
    other = tmp_path / "claude-other"
    other.mkdir()
    assert launcher.main(["open", "--once", "--claude-config-dir", str(other), "tmp1"]) == 0
    assert typed(launcher)[0].startswith("CLAUDE_CONFIG_DIR=%s claude --session-id " % other)


# ---- unknown keys -------------------------------------------------------

def test_unknown_keys_are_reported(lc, workdir, capsys):
    write_config(lc, "ttyd_warnning = 0\nport_min = 7700\n")
    lc.agents_dir().mkdir(parents=True, exist_ok=True)
    agent_file(lc, "aa").write_text("[agent]\ndir = %s\nautostrat = 1\n" % workdir)
    assert lc.main(["list"]) == 0
    err = capsys.readouterr().err
    assert "unknown key ttyd_warnning (ignored)" in err
    assert "unknown key autostrat (ignored)" in err
    assert lc.load_agent("aa")["autostart"] is False


def test_saved_files_contain_only_known_keys(lc, workdir, tmp_path, capsys):
    lc.main(["add", "aa", "--port", "7701", "--claude-config-dir", str(tmp_path)])
    capsys.readouterr()
    assert set(lc.read_ini(agent_file(lc, "aa"), "agent")) <= set(lc.AGENT_KEYS)
    lc.main(["list"])
    assert capsys.readouterr().err == ""


# ---- failures that are hard to reach ------------------------------------

def test_start_goes_on_after_a_broken_agent(lc, workdir, monkeypatch, capsys):
    for name in ("aa", "b", "c"):
        lc.main(["add", name, "--autostart"])
    real = lc.start_registered

    def broken_b(settings, agent_id, mode=None):
        if agent_id == "b":
            raise lc.Error("[b] cannot start")
        return real(settings, agent_id, mode)

    monkeypatch.setattr(lc, "start_registered", broken_b)
    assert lc.main(["start", "--autostart"]) == 1
    assert [entry[0] for entry in lc.fake.launched] == ["aa", "c"]
    assert "Error: [b] cannot start" in capsys.readouterr().err


def watch_screens(lc, monkeypatch, screens, commands=("claude",)):
    """Let wait_for_ready see these screens and foreground commands, one per poll; no real waiting."""
    sent = []
    screens, commands = list(screens), list(commands)
    def following(items):
        return lambda target: items.pop(0) if len(items) > 1 else items[0]

    monkeypatch.setattr(lc, "capture_pane", following(screens))
    monkeypatch.setattr(lc, "pane_command", following(commands))
    monkeypatch.setattr(lc, "tmux", lambda *args: sent.append(args))
    monkeypatch.setattr(lc.time, "sleep", lambda seconds: None)
    return sent


def test_wait_for_ready_answers_the_trust_dialog(lc, monkeypatch):
    sent = watch_screens(lc, monkeypatch, ["Do you trust this folder?", "> \n? for shortcuts"])
    assert lc.wait_for_ready("=a:")[:2] == (True, "")
    assert sent == [("send-keys", "-t", "=a:", "Enter")]


def test_wait_for_ready_gives_up_when_the_screen_stops_changing(lc, monkeypatch):
    watch_screens(lc, monkeypatch, ["Select login method:"])
    monkeypatch.setattr(lc, "STALL_TIMEOUT", 0)
    ready, reason, screen = lc.wait_for_ready("=a:")
    assert (ready, reason) == (False, "the screen has not changed for 0 seconds")
    assert screen == "Select login method:"


def test_wait_for_ready_notices_that_claude_exited(lc, monkeypatch):
    watch_screens(lc, monkeypatch, ["starting", "claude: command not found"], commands=["claude", "bash"])
    assert lc.wait_for_ready("=a:")[:2] == (False, "claude exited")


def test_wait_for_ready_times_out(lc, monkeypatch):
    watch_screens(lc, monkeypatch, [""])
    assert lc.wait_for_ready("=a:", timeout=0)[:2] == (False, "timed out after 0 seconds")


def test_interface_ip_of_the_loopback_interface(lc):
    assert lc.interface_ip("lo") == "127.0.0.1"
    assert lc.interface_ip("no-such-if0") is None


def test_failed_write_leaves_no_temporary_file(lc, tmp_path, monkeypatch):
    def refuse(source, target):
        raise OSError("disk full")

    monkeypatch.setattr(lc.os, "replace", refuse)
    with pytest.raises(OSError):
        lc.write_ini(tmp_path / "conf" / "aa.conf", "agent", {"dir": "/x"})
    assert list((tmp_path / "conf").iterdir()) == []


def test_pretrust_failure_leaves_no_temporary_file(launcher, workdir, tmp_path, monkeypatch):
    def refuse(source, target):
        raise OSError("disk full")

    monkeypatch.setattr(launcher.os, "replace", refuse)
    before = sorted(path.name for path in (tmp_path / "home").iterdir())
    assert launcher.pretrust_dir(launcher.load_settings(), str(workdir)) is False
    assert sorted(path.name for path in (tmp_path / "home").iterdir()) == before


# ---- attach -------------------------------------------------------------

@pytest.fixture
def attached(lc, monkeypatch):
    """Records which session 'attach' would enter instead of entering it."""
    entered = []
    monkeypatch.setattr(lc.shutil, "which", lambda command: "/usr/bin/" + command)
    monkeypatch.setattr(lc, "attach_session", lambda name: entered.append(name) or 0)
    return entered


def test_attach_enters_the_named_session(lc, workdir, attached):
    lc.main(["open", "aa"])
    lc.main(["open", "b"])
    assert lc.main(["attach", "b"]) == 0
    assert attached == ["b"]


def test_attach_without_id_needs_exactly_one_running_session(lc, workdir, attached, capsys):
    assert lc.main(["attach"]) == 1
    assert "nothing is running" in capsys.readouterr().err
    lc.main(["open", "aa"])
    assert lc.main(["attach"]) == 0 and attached == ["aa"]
    lc.fake.run("once-1", kind="once")
    assert lc.main(["attach"]) == 1
    assert "which one? Running: aa, once-1" in capsys.readouterr().err
    assert attached == ["aa"]


def test_attach_does_not_start_anything(lc, workdir, attached, capsys):
    lc.main(["add", "idle"])
    assert lc.main(["attach", "idle"]) == 1
    assert "Start it with: launch_claude start idle" in capsys.readouterr().err
    assert lc.main(["attach", "nobody"]) == 1
    assert "neither registered nor a running session" in capsys.readouterr().err
    assert attached == [] and lc.fake.launched == []


def test_attach_to_the_own_session_does_nothing(lc, workdir, attached, monkeypatch, capsys):
    lc.main(["open", "aa"])
    monkeypatch.setattr(lc, "current_session", lambda: "aa")
    assert lc.main(["attach", "aa"]) == 0
    assert "[aa] is the session you are in." in capsys.readouterr().out
    assert attached == []


def test_attach_session_needs_a_terminal_and_does_not_nest_tmux(lc, monkeypatch):
    calls = []
    monkeypatch.setattr(lc.os, "execvp", lambda program, argv: calls.append(argv))
    monkeypatch.setattr(lc, "tmux", lambda *args: calls.append(list(args)) or SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(lc.sys.stdin, "isatty", lambda: False)
    with pytest.raises(lc.Error, match="attach needs a terminal"):
        lc.attach_session("aa")
    assert calls == []
    monkeypatch.setattr(lc.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(lc.sys.stdout, "isatty", lambda: True)
    lc.attach_session("aa")  # outside tmux: our process becomes "tmux attach"
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1,0")
    assert lc.attach_session("aa") == 0  # inside tmux: the client is switched
    assert calls == [["tmux", "attach-session", "-t", "=aa"], ["switch-client", "-t", "=aa"]]


# ---- completion ---------------------------------------------------------

def test_completion_prints_a_bash_script_for_every_command(lc, capsys):
    assert lc.main(["completion", "bash"]) == 0
    script = capsys.readouterr().out
    assert "complete -F _launch_claude launch_claude" in script
    assert " ".join(lc.COMMANDS) + " up down help --version" in script
    assert "new resume continue" in script
    for command in lc.COMMANDS:
        assert "%s) options=" % command in script
    assert set(lc.COMPLETION) == set(lc.COMMANDS)


def test_completion_offers_only_options_that_the_help_lists(lc):
    for command, (options, _) in lc.COMPLETION.items():
        for option in options:
            assert option in lc.USAGE, (command, option)
            # and the command really accepts it: an unknown option would be "unrecognized arguments"
    assert lc.main(["stop", "--stop-own-session", "--bogus"]) == 1


def test_completion_ids_by_state(lc, workdir, capsys):
    lc.main(["add", "idle"])
    lc.main(["open", "busy"])
    lc.fake.run("once-1", kind="once")
    capsys.readouterr()
    for kind, expected in (("running", "busy\nonce-1\n"), ("stopped", "idle\n"),
                           ("registered", "busy\nidle\n")):
        assert lc.main(["completion", "ids", kind]) == 0
        assert capsys.readouterr() == (expected, "")


def test_completion_ids_stay_silent_when_something_is_wrong(lc, monkeypatch, capsys):
    def broken(sessions=None):
        raise OSError("no tmux here")
    monkeypatch.setattr(lc, "running_ids", broken)
    assert lc.main(["completion", "ids", "running"]) == 0
    assert capsys.readouterr() == ("", "")


def test_completion_for_another_shell_is_an_error(lc, capsys):
    assert lc.main(["completion", "zsh"]) == 1
    assert "only bash is supported" in capsys.readouterr().err
    assert lc.main(["add", "completion"]) == 1 and lc.main(["add", "attach"]) == 1  # reserved words


# ---- short names --------------------------------------------------------

def test_short_names_run_their_commands(lc, workdir, attached, capsys):
    assert lc.main(["o", "a1"]) == 0 and lc.load_agent("a1") is not None
    assert lc.main(["a", "a1"]) == 0 and attached == ["a1"]
    assert lc.main(["down", "a1"]) == 0 and not lc.session_exists("a1")
    assert lc.main(["up", "a1"]) == 0 and lc.session_exists("a1")
    for name, command in lc.ALIASES.items():
        assert command in lc.COMMANDS and name in lc.RESERVED
        assert "%s = %s" % (name, command) in lc.USAGE
