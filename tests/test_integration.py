"""Integration tests: the real script and a real (private) tmux server, with a stub 'claude'."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "launch_claude"

pytestmark = pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is not installed")

STUB = """#!/bin/sh
echo "ARGS: $*" >> "$HOME/claude.log"
echo "stub claude"
echo "? for shortcuts"
while read -r line; do
  echo "INPUT: $line" >> "$HOME/claude.log"
  [ "$line" = "/exit" ] && exit 0
done
"""


class Sandbox:
    def __init__(self, root, socket_dir):
        self.home = root / "home"
        self.work = root / "work"
        bin_dir = root / "bin"
        for path in (self.home, self.work, bin_dir):
            path.mkdir()
        stub = bin_dir / "claude"
        stub.write_text(STUB)
        stub.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("TMUX", "TMUX_PANE", "CLAUDE_CONFIG_DIR", "REMOTE_CONTROL",
                                 "TTYD_CREDENTIAL")}
        self.env.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_STATE_HOME": str(self.home / ".local" / "state"),
            "TMUX_TMPDIR": socket_dir,  # private tmux server; must be a short path
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "SHELL": "/bin/sh",
        })

    def run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT)] + list(args), cwd=str(self.work),
                              env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=120)

    def tmux(self, *args):
        return subprocess.run(["tmux"] + list(args), env=self.env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)

    def sessions(self):
        return self.tmux("list-sessions", "-F", "#{session_name}").stdout.split()

    def log(self):
        path = self.home / "claude.log"
        return path.read_text() if path.exists() else ""

    def wait(self, condition, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return True
            time.sleep(0.2)
        return False


@pytest.fixture
def sandbox(tmp_path):
    # Unix socket paths are limited to ~100 bytes, so do not put the socket under tmp_path.
    base = os.environ.get("XDG_RUNTIME_DIR")
    socket_dir = tempfile.mkdtemp(prefix="lc-", dir=base if base and os.path.isdir(base) else "/tmp")
    box = Sandbox(tmp_path, socket_dir)
    try:
        yield box
    finally:
        box.tmux("kill-server")
        shutil.rmtree(socket_dir, ignore_errors=True)


def test_open_list_stop(sandbox):
    result = sandbox.run("open", "--without-ttyd", "alpha")
    assert result.returncode == 0, result.stderr
    assert "ready" in result.stdout
    assert sandbox.sessions() == ["alpha"]
    assert sandbox.wait(lambda: "INPUT: /remote-control alpha" in sandbox.log())
    assert "--session-id" in sandbox.log() and "--name alpha" in sandbox.log()

    listing = sandbox.run("list").stdout
    assert any(line.split()[:4] == ["alpha", "running", "tmux", "only"] for line in listing.splitlines())

    again = sandbox.run("start", "alpha")
    assert again.returncode == 0 and "already running" in again.stdout

    assert sandbox.run("stop", "alpha").returncode == 0
    assert sandbox.sessions() == []
    listing = sandbox.run("list").stdout
    assert any(line.split()[:2] == ["alpha", "stopped"] for line in listing.splitlines())


def test_once_is_listed_stopped_and_cleans_up_after_exit(sandbox):
    assert sandbox.run("open", "--once", "tmp1").returncode == 0
    assert sandbox.run("open", "--once", "tmp2").returncode == 0
    listing = sandbox.run("list", "--running").stdout
    assert "tmp1" in listing and "tmux only (once)" in listing
    assert not (sandbox.home / ".config" / "launch_claude" / "agents").exists()

    # claude exits -> the session removes itself
    sandbox.tmux("send-keys", "-t", "=tmp1:", "/exit", "Enter")
    assert sandbox.wait(lambda: "tmp1" not in sandbox.sessions())

    # stop without arguments also finds the unregistered --once session
    assert "tmp2" in sandbox.sessions()
    assert sandbox.run("stop").returncode == 0
    assert sandbox.sessions() == []


def test_claude_exiting_immediately_is_detected_quickly(sandbox):
    stub = Path(sandbox.env["PATH"].split(os.pathsep)[0]) / "claude"
    # "exec" so that tmux sees a non-shell program, as it does with the real claude binary.
    stub.write_text("#!/bin/sh\necho 'No conversation found'\nexec sleep 2\n")
    started = time.time()
    result = sandbox.run("open", "--without-ttyd", "broken")
    assert time.time() - started < 15  # far less than the 60 second timeout
    assert "did not reach the input prompt (claude exited)" in result.stderr
    assert "No conversation found" in result.stderr  # screen tail for diagnosis


@pytest.mark.skipif(shutil.which("ttyd") is None, reason="ttyd is not installed")
def test_ttyd_session_is_started_and_stopped(sandbox):
    result = sandbox.run("open", "web")
    assert result.returncode == 0, result.stderr
    assert "http://" in result.stdout
    assert sorted(sandbox.sessions()) == ["ttyd-web", "web"]
    assert sandbox.run("stop", "web").returncode == 0
    assert sandbox.sessions() == []


@pytest.mark.skipif(shutil.which("ttyd") is None, reason="ttyd is not installed")
def test_ttyd_can_be_opened_and_closed_on_a_running_session(sandbox):
    assert sandbox.run("open", "--without-ttyd", "quiet").returncode == 0
    assert sandbox.sessions() == ["quiet"]

    opened = sandbox.run("ttyd", "quiet")
    assert opened.returncode == 0, opened.stderr
    assert "Opened ttyd for [quiet]: http://" in opened.stdout
    assert "without a password of its own" in opened.stderr
    assert sorted(sandbox.sessions()) == ["quiet", "ttyd-quiet"]
    assert "http://" in sandbox.run("list").stdout

    closed = sandbox.run("ttyd", "quiet", "--off")
    assert closed.returncode == 0 and "Closed ttyd" in closed.stdout
    assert sandbox.sessions() == ["quiet"]  # claude keeps running
    assert "tmux only" in sandbox.run("list").stdout
    conf = (sandbox.home / ".config" / "launch_claude" / "agents" / "quiet.conf").read_text()
    assert "ttyd = 0" in conf  # the saved setting was not changed
