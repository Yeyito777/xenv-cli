"""Shared utilities for xenv CLI."""

import os
import re
import signal
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PROJECT_DIR / "runtime"
DEFAULT_SIZE = "1280x800"


# ── Output helpers ───────────────────────────────────────────────

def die(msg):
    print(f"xenv: error: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg):
    print(f"xenv: {msg}", file=sys.stderr)


# ── Instance ─────────────────────────────────────────────────────

class Instance:
    """Runtime state for a named xenv instance."""

    def __init__(self, name):
        self.name = name
        self.dir = RUNTIME_DIR / f"xenv-{name}"
        self.pidfile = self.dir / "xephyr.pid"
        self.wm_pidfile = self.dir / "wm.pid"
        self.watcher_pidfile = self.dir / "watcher.pid"
        self.display_file = self.dir / "display"
        self.screenshot_dir = self.dir / "screenshots"
        self.xephyr_log = self.dir / "xephyr.log"
        self.dwm_dir = self.dir / "dwm"

    @property
    def display(self):
        if self.display_file.exists():
            return self.display_file.read_text().strip()
        return ""

    @property
    def running(self):
        display = self.display
        if not display or not self.pidfile.exists():
            return False
        try:
            pid = int(self.pidfile.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError, PermissionError, FileNotFoundError):
            return False

    @property
    def xephyr_pid(self):
        if self.pidfile.exists():
            try:
                return int(self.pidfile.read_text().strip())
            except (ValueError, FileNotFoundError):
                return None
        return None

    @property
    def wm_pid(self):
        if self.wm_pidfile.exists():
            try:
                return int(self.wm_pidfile.read_text().strip())
            except (ValueError, FileNotFoundError):
                return None
        return None

    def require_running(self):
        if not self.running:
            die(f"instance '{self.name}' is not running. Use 'xenv start {self.name}' first.")


def require_instance_name(args_name=None):
    """Get instance name from argparse positional or XENV_INSTANCE env var."""
    name = args_name or os.environ.get("XENV_INSTANCE", "")
    if not name:
        die("no instance specified. Use -e <name> or set XENV_INSTANCE.")
    return name


# ── Display helpers ──────────────────────────────────────────────

def find_free_display():
    n = 1
    while Path(f"/tmp/.X11-unix/X{n}").exists():
        n += 1
        if n > 99:
            die("no free display found")
    return f":{n}"


def make_env(display):
    """Return a copy of os.environ with DISPLAY overridden."""
    env = os.environ.copy()
    env["DISPLAY"] = display
    return env


# ── Subprocess helpers ───────────────────────────────────────────

def run_quiet(cmd, env=None):
    """Run a command, return stdout string or None on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def kill_pidfile(pidfile):
    """Send SIGTERM to the PID in a pidfile, then remove it."""
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, ValueError, PermissionError, FileNotFoundError):
            pass
        pidfile.unlink(missing_ok=True)


# ── Input helpers ────────────────────────────────────────────────

def get_active_window(display):
    """Get the active window ID on the given display, or None."""
    env = make_env(display)
    wid = run_quiet(["xdotool", "getactivewindow"], env=env)
    if wid:
        return wid
    out = run_quiet(["xdotool", "search", "--onlyvisible", "--name", ""], env=env)
    if out:
        return out.split("\n")[0]
    return None


def send_keys(display, keys):
    """Send keystrokes to the focused window."""
    env = make_env(display)
    wid = get_active_window(display)
    cmd = ["xdotool", "key"]
    if wid:
        cmd += ["--window", wid, "--clearmodifiers", "--"]
    else:
        cmd += ["--"]
    cmd += keys
    subprocess.run(cmd, env=env)


def send_type(display, text):
    """Type text into the focused window."""
    env = make_env(display)
    wid = get_active_window(display)
    cmd = ["xdotool", "type"]
    if wid:
        cmd += ["--window", wid, "--clearmodifiers", "--delay", "12", "--"]
    else:
        cmd += ["--delay", "12", "--"]
    cmd += [text]
    subprocess.run(cmd, env=env)
