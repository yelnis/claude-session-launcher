"""Shared fixtures. The script has no .py extension, so it is loaded by path."""
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "launch_claude"
sys.dont_write_bytecode = True


def load_script():
    loader = importlib.machinery.SourceFileLoader("launch_claude", str(SCRIPT))
    spec = importlib.util.spec_from_loader("launch_claude", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeTmux:
    """Stands in for tmux: remembers which sessions 'run' and what was launched."""

    def __init__(self):
        self.managed = {}      # name -> {kind, dir, port, started}
        self.unmanaged = set()  # tmux sessions not started by the tool
        self.launched = []     # (id, dir, port, mode, once)
        self.killed = []
        self.ttyd_started = []  # (id, port)

    def session_exists(self, name):
        return name in self.managed or name in self.unmanaged

    def managed_sessions(self):
        return {k: dict(v) for k, v in self.managed.items()}

    def launch_session(self, settings, agent_id, directory, port, mode, once=False):
        self.launched.append((agent_id, directory, port, mode, once))
        self.managed[agent_id] = {"kind": "once" if once else "agent", "dir": directory,
                                  "port": port, "started": "2026-01-02T03:04:05"}
        if port:
            self.unmanaged.add("ttyd-" + agent_id)
        return True

    def kill_session(self, name):
        self.killed.append(name)
        self.managed.pop(name, None)
        self.unmanaged.discard(name)
        if name.startswith("ttyd-") and name[5:] in self.managed:
            self.managed[name[5:]]["port"] = None

    def start_ttyd(self, settings, agent_id, port):
        self.ttyd_started.append((agent_id, port))
        self.unmanaged.add("ttyd-" + agent_id)
        self.managed[agent_id]["port"] = port

    def tmux(self, *args):
        """No real tmux call may leave the tests."""
        if args[0] == "set-option" and args[-2] == "@launch_claude_port" and not args[-1]:
            name = args[2].strip("=:")
            if name in self.managed:
                self.managed[name]["port"] = None

    def run(self, agent_id, directory="/somewhere", port=None, kind="agent"):
        self.managed[agent_id] = {"kind": kind, "dir": directory, "port": port,
                                  "started": "2026-01-02T03:04:05"}


@pytest.fixture
def lc(monkeypatch, tmp_path):
    """The script as a module, with config/state under tmp_path and tmux faked."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    for name in ("TMUX", "TMUX_PANE", "CLAUDE_CONFIG_DIR", "REMOTE_CONTROL", "TTYD_CREDENTIAL"):
        monkeypatch.delenv(name, raising=False)
    module = load_script()
    fake = FakeTmux()
    module.fake = fake
    for name in ("session_exists", "managed_sessions", "launch_session", "kill_session", "start_ttyd",
                 "tmux"):
        monkeypatch.setattr(module, name, getattr(fake, name))
    monkeypatch.setattr(module, "current_session", lambda: "")
    monkeypatch.setattr(module, "port_is_free", lambda port: True)
    monkeypatch.setattr(module, "host_ip", lambda: "192.0.2.10")
    return module


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    path = tmp_path / "work"
    path.mkdir()
    monkeypatch.chdir(path)
    return path
