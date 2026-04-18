"""Shared utilities for xenv CLI."""

import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PROJECT_DIR / "runtime"
INITIAL_XEPHYR_SIZE = "1280x800"


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


def _sanitize_unit_fragment(value):
    cleaned = re.sub(r"[^A-Za-z0-9:_-]+", "-", value).strip("-")
    return cleaned or "job"


def spawn_persistent(cmd, *, env=None, cwd=None, unit_prefix="xenv", stdout_path=None, stderr_path=None, wait_for_pid=True):
    """Spawn a long-lived process under the user systemd manager when available.

    Falls back to a detached subprocess when systemd-run is unavailable.
    Returns (unit_name | None, pid | None).
    """
    env_map = dict(env or os.environ)
    cmd_list = [str(part) for part in cmd]
    cwd_str = str(cwd) if cwd is not None else None

    systemd_run = shutil.which("systemd-run")
    systemctl = shutil.which("systemctl")
    if systemd_run and systemctl:
        unit = f"exo-{_sanitize_unit_fragment(unit_prefix)}-{uuid.uuid4().hex[:8]}"
        script = f"exec {shlex.join(cmd_list)}"

        if stdout_path and stderr_path and Path(stdout_path) == Path(stderr_path):
            target = shlex.quote(str(stdout_path))
            script += f" >> {target} 2>&1"
        else:
            if stdout_path:
                script += f" >> {shlex.quote(str(stdout_path))}"
            else:
                script += " >/dev/null"
            if stderr_path:
                script += f" 2>> {shlex.quote(str(stderr_path))}"
            else:
                script += " 2>/dev/null"

        run_cmd = [
            systemd_run,
            "--user",
            "--quiet",
            "--collect",
            "-p",
            "ExitType=cgroup",
            "--unit",
            unit,
        ]
        if cwd_str is not None:
            run_cmd.extend(["--working-directory", cwd_str])
        for key, value in sorted(env_map.items()):
            if "\x00" in key or "\x00" in value:
                continue
            run_cmd.extend(["--setenv", f"{key}={value}"])
        run_cmd.extend(["bash", "-lc", script])

        result = subprocess.run(run_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "systemd-run failed").strip())

        pid = None
        if wait_for_pid:
            deadline = time.time() + 5
            while time.time() < deadline:
                show = subprocess.run(
                    [systemctl, "--user", "show", "--property", "MainPID", "--value", unit],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                raw = show.stdout.strip()
                if raw and raw != "0":
                    try:
                        pid = int(raw)
                        break
                    except ValueError:
                        pass
                time.sleep(0.1)
        return unit, pid

    if stdout_path is not None:
        stdout_handle = open(stdout_path, "ab")
    else:
        stdout_handle = subprocess.DEVNULL

    if stderr_path is not None and stdout_path is not None and Path(stderr_path) == Path(stdout_path):
        stderr_handle = stdout_handle
    elif stderr_path is not None:
        stderr_handle = open(stderr_path, "ab")
    else:
        stderr_handle = subprocess.DEVNULL
    try:
        proc = subprocess.Popen(
            cmd_list,
            cwd=cwd_str,
            env=env_map,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
    finally:
        if stdout_path is not None:
            stdout_handle.close()
        if stderr_path is not None and stderr_handle is not stdout_handle:
            stderr_handle.close()
    return None, proc.pid


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

