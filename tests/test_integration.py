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

    def run(self, *args, **extra_env):
        return subprocess.run([sys.executable, str(SCRIPT)] + list(args), cwd=str(self.work),
                              env=dict(self.env, **extra_env), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=120)

    def tmux(self, *args):
        return subprocess.run(["tmux"] + list(args), env=self.env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)

    def inside(self, session):
        """Environment variables that tmux gives to a process in this session."""
        show = self.tmux("display-message", "-p", "-t", "=%s:" % session,
                         "#{socket_path},#{pid},0 #{pane_id}")
        tmux_value, pane = show.stdout.split()
        return {"TMUX": tmux_value, "TMUX_PANE": pane}

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


def test_stop_keeps_the_session_it_is_run_in(sandbox):
    for name in ("alpha", "beta"):
        assert sandbox.run("open", "--without-ttyd", name).returncode == 0
    inside = sandbox.inside("alpha")

    named = sandbox.run("stop", "alpha", **inside)
    assert named.returncode == 1 and "--stop-own-session" in named.stderr
    assert sorted(sandbox.sessions()) == ["alpha", "beta"]

    everything = sandbox.run("stop", **inside)
    assert everything.returncode == 0
    assert "[alpha] is the session this command runs in; not stopped" in everything.stdout
    assert sandbox.sessions() == ["alpha"]

    assert sandbox.run("stop", "--stop-own-session", **inside).returncode == 0
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
    result = sandbox.run("open", "--with-ttyd", "web")
    assert result.returncode == 0, result.stderr
    assert "http://" in result.stdout
    assert "on every network interface without a password of its own" in result.stderr
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


@pytest.mark.skipif(shutil.which("ttyd") is None, reason="ttyd is not installed")
def test_ttyd_on_loopback_only(sandbox):
    config = sandbox.home / ".config" / "launch_claude" / "config"
    config.parent.mkdir(parents=True)
    config.write_text("[launch_claude]\nttyd_interface = lo\n")
    result = sandbox.run("open", "--with-ttyd", "local")
    assert result.returncode == 0, result.stderr
    assert "without a password" not in result.stderr  # loopback only: no warning
    assert "http://localhost:" in result.stdout  # started, verified as listening, shown as localhost
    assert sorted(sandbox.sessions()) == ["local", "ttyd-local"]
    assert "http://localhost:" in sandbox.run("list").stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")
def test_bash_completion_with_real_sessions(sandbox, tmp_path):
    assert sandbox.run("open", "alpha").returncode == 0
    assert sandbox.run("add", "beta", "--dir", str(sandbox.work)).returncode == 0
    (sandbox.work / "sub dir").mkdir()
    script = tmp_path / "try.bash"
    script.write_text(r'''
launch_claude() { "$PYTHON" "$SCRIPT" "$@"; }
eval "$(launch_claude completion bash)"
try() { COMP_WORDS=("$@"); COMP_CWORD=$(( $# - 1 )); _launch_claude; (IFS=,; echo "${COMPREPLY[*]}"); }
try launch_claude at
try launch_claude attach ""
try launch_claude stop ""
try launch_claude start ""
try launch_claude b
try launch_claude set ""
try launch_claude set beta --mo
try launch_claude set beta --mode re
try launch_claude stop -
try launch_claude add new --dir su
try launch_claude open gamma s
try launch_claude list ""
''')
    result = subprocess.run(["bash", str(script)], cwd=str(sandbox.work), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=120,
                            env=dict(sandbox.env, PYTHON=sys.executable, SCRIPT=str(SCRIPT)))
    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "attach",            # a command from its first letters
        "alpha",             # attach: running
        "alpha",             # stop: running
        "beta",              # start: registered and stopped
        "beta",              # the shortcut "launch_claude <id>"
        "alpha,beta",        # set: everything registered
        "--mode",
        "resume",
        "--stop-own-session",
        "sub dir",           # --dir: directories
        "sub dir",           # open <id> <dir>
        "",                  # list takes no id
    ]
