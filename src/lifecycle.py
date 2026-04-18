"""Lifecycle commands: start, stop, instances, status."""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from src.helpers import (
    PROJECT_DIR, RUNTIME_DIR, INITIAL_XEPHYR_SIZE, Instance,
    die, info, require_instance_name,
    find_free_display, make_env, run_quiet, kill_pidfile, spawn_persistent,
)


# ── start ────────────────────────────────────────────────────────

def start(argv):
    p = argparse.ArgumentParser(prog="xenv start", description=(
        "Start a named environment (Xephyr + dwm). "
        "Idempotent — if already running, prints the display and exits. "
        "The host dwm will size the window to its AI tag automatically."
    ))
    p.add_argument("name", nargs="?", help="Instance name (e.g. exo, agent-7, test)")
    args = p.parse_args(argv)

    name = args.name or os.environ.get("XENV_INSTANCE", "")
    if not name:
        die("start: instance name required. Usage: xenv start <name>")

    inst = Instance(name)

    if inst.running:
        info(f"'{name}' already running on {inst.display} (PID {inst.xephyr_pid})")
        print(inst.display)
        return

    display = find_free_display()
    inst.dir.mkdir(parents=True, exist_ok=True)
    inst.screenshot_dir.mkdir(parents=True, exist_ok=True)

    host_display = os.environ.get("DISPLAY", ":0")

    # Start Xephyr
    xephyr_env = os.environ.copy()
    xephyr_env["DISPLAY"] = host_display
    xephyr_env["DWM_AI_TAG"] = "1"
    xephyr_env["DWM_AI_TOKEN"] = f"xenv:{name}"
    xephyr_env["DWM_AI_LABEL"] = f"xenv: {name}"
    xephyr_env["DWM_AI_POLICY"] = "autodelete-pristine"
    inst.xephyr_log.write_text("")
    _xephyr_unit, xephyr_pid = spawn_persistent(
        [
            "Xephyr",
            "-br", "-ac", "-noreset",
            "-screen", INITIAL_XEPHYR_SIZE,
            "-resizeable",
            "-xinerama",
            "-name", f"exo-xenv-{name}",
            "-title", f"xenv: {name}",
            display,
        ],
        env=xephyr_env,
        unit_prefix=f"xenv-{name}-xephyr",
        stdout_path=inst.xephyr_log,
        stderr_path=inst.xephyr_log,
    )

    # Wait for display socket
    num = display.lstrip(":")
    deadline = time.time() + 5
    while not Path(f"/tmp/.X11-unix/X{num}").exists():
        if xephyr_pid is not None:
            try:
                os.kill(xephyr_pid, 0)
            except ProcessLookupError:
                die(f"Xephyr failed to start. See {inst.xephyr_log}")
        if time.time() >= deadline:
            if xephyr_pid is not None:
                try:
                    os.kill(xephyr_pid, 9)
                except ProcessLookupError:
                    pass
            die("Xephyr timed out")
        time.sleep(0.1)

    if xephyr_pid is not None:
        inst.pidfile.write_text(str(xephyr_pid))
    inst.display_file.write_text(display)
    inst.host_display_file.write_text(host_display)

    # Start dwm
    inst.dwm_dir.mkdir(exist_ok=True)
    dwm_env = make_env(display)
    dwm_env["DWM_RUNTIME_DIR"] = str(inst.dwm_dir)
    _dwm_unit, dwm_pid = spawn_persistent(
        ["dwm"],
        env=dwm_env,
        unit_prefix=f"xenv-{name}-dwm",
    )
    if dwm_pid is not None:
        inst.wm_pidfile.write_text(str(dwm_pid))

    # Start resize watcher
    watcher_env = make_env(display)
    watcher_env["PYTHONPATH"] = str(PROJECT_DIR)
    _watcher_unit, watcher_pid = spawn_persistent(
        [sys.executable, str(PROJECT_DIR / "src" / "resize_watcher.py")],
        env=watcher_env,
        unit_prefix=f"xenv-{name}-watcher",
    )
    if watcher_pid is not None:
        inst.watcher_pidfile.write_text(str(watcher_pid))

    time.sleep(0.5)
    info(f"'{name}' started on {display} (AI-sized by host dwm, PID {xephyr_pid or '?'})")
    print(display)


# ── stop ─────────────────────────────────────────────────────────

def stop(argv):
    p = argparse.ArgumentParser(prog="xenv stop", description=(
        "Stop a named environment gracefully."
    ))
    p.add_argument("name", nargs="?", help="Instance name")
    args = p.parse_args(argv)

    name = require_instance_name(args.name)
    inst = Instance(name)

    if not inst.running:
        info(f"'{name}' is not running")
        return

    display = inst.display
    env = make_env(display)

    # Close client windows
    out = run_quiet(["xdotool", "search", "--onlyvisible", "--name", ""], env=env)
    if out:
        for wid in out.split("\n"):
            subprocess.run(
                ["xdotool", "windowclose", wid],
                capture_output=True, env=env,
            )
    time.sleep(0.2)

    kill_pidfile(inst.grab_hotkey_pidfile)
    kill_pidfile(inst.watcher_pidfile)
    kill_pidfile(inst.wm_pidfile)
    kill_pidfile(inst.pidfile)
    inst.display_file.unlink(missing_ok=True)
    inst.host_display_file.unlink(missing_ok=True)

    info(f"'{name}' stopped (was on {display})")


# ── instances ────────────────────────────────────────────────────

def instances(argv):
    p = argparse.ArgumentParser(prog="xenv instances", description=(
        "List all running xenv instances."
    ))
    p.parse_args(argv)

    found = False
    if RUNTIME_DIR.exists():
        for idir in sorted(RUNTIME_DIR.glob("xenv-*")):
            if not idir.is_dir():
                continue
            name = idir.name.removeprefix("xenv-")
            inst = Instance(name)
            if not inst.running:
                continue

            display = inst.display
            pid = inst.xephyr_pid or "?"
            env = make_env(display)

            geom = "?"
            out = run_quiet(["xrandr"], env=env)
            if out:
                m = re.search(r"current (\d+ x \d+)", out)
                if m:
                    geom = m.group(1)

            wcount = 0
            wout = run_quiet(["xdotool", "search", "--onlyvisible", "--name", ""], env=env)
            if wout:
                wcount = len(wout.split("\n"))
            clients = max(wcount - 2, 0)

            print(f"{name:<16} {display}  {geom}  PID {str(pid):<8}  {clients} windows")
            found = True

    if not found:
        print("(no running instances)")


# ── status ───────────────────────────────────────────────────────

def status(argv):
    p = argparse.ArgumentParser(prog="xenv status", description=(
        "Show details about a named environment."
    ))
    p.add_argument("name", nargs="?", help="Instance name")
    args = p.parse_args(argv)

    name = require_instance_name(args.name)
    inst = Instance(name)

    if not inst.running:
        print("stopped")
        sys.exit(1)

    display = inst.display
    env = make_env(display)

    geom = "?"
    out = run_quiet(["xrandr"], env=env)
    if out:
        m = re.search(r"current (\d+ x \d+)", out)
        if m:
            geom = m.group(1)

    wcount = 0
    wout = run_quiet(["xdotool", "search", "--onlyvisible", "--name", ""], env=env)
    if wout:
        wcount = len(wout.split("\n"))
    clients = max(wcount - 2, 0)

    print("running")
    print(f"  instance:   {name}")
    print(f"  display:    {display}")
    print(f"  geometry:   {geom}")
    print(f"  xephyr_pid: {inst.xephyr_pid or '?'}")
    print(f"  dwm_pid:    {inst.wm_pid or '?'}")
    print(f"  windows:    {clients}")
    print(f"  runtime:    {inst.dir}")
