"""Observation commands: screenshot, windows, display."""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime

from src.helpers import (
    Instance, die, require_instance_name,
    make_env, run_quiet,
)


# ── screenshot ───────────────────────────────────────────────────

def screenshot(argv):
    p = argparse.ArgumentParser(prog="xenv screenshot", description=(
        "Capture the nested display as a PNG."
    ))
    p.add_argument("--output", "-o", help="Save to specific path (default: timestamped in runtime dir)")
    args = p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    display = inst.display
    env = make_env(display)
    output = args.output

    if not output:
        inst.screenshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = str(inst.screenshot_dir / f"screenshot-{ts}.png")

    # Try maim first, fall back to import
    r = subprocess.run(["maim", output], capture_output=True, env=env)
    if r.returncode != 0:
        r = subprocess.run(["import", "-window", "root", output], capture_output=True, env=env)
        if r.returncode != 0:
            die("screenshot failed")

    try:
        size_kb = os.path.getsize(output) // 1024
    except OSError:
        size_kb = 0
    print(f"{output}  ({size_kb}KB)")


# ── windows ──────────────────────────────────────────────────────

def windows(argv):
    p = argparse.ArgumentParser(prog="xenv windows", description=(
        "List visible windows with IDs, geometry, and titles."
    ))
    p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    display = inst.display
    env = make_env(display)

    out = run_quiet(["xdotool", "search", "--onlyvisible", "--name", ""], env=env)
    wids = out.split("\n") if out else []

    lines = []
    for wid in wids:
        wname = run_quiet(["xdotool", "getwindowname", wid], env=env) or "(unnamed)"
        if wname in ("dwm", "dwm-6.6") or not wname:
            continue

        geom_out = run_quiet(["xdotool", "getwindowgeometry", wid], env=env) or ""
        pos_m = re.search(r"Position: (\S+)", geom_out)
        geo_m = re.search(r"Geometry: (\S+)", geom_out)
        pos = pos_m.group(1) if pos_m else "?"
        geo = geo_m.group(1) if geo_m else "?"

        lines.append(f"{wid}  {geo}  {pos}  {wname}")

    if lines:
        print("\n".join(lines))
    else:
        print("(no client windows)")


# ── display ──────────────────────────────────────────────────────

def display(argv):
    p = argparse.ArgumentParser(prog="xenv display", description=(
        "Print the DISPLAY value of the instance."
    ))
    p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()
    print(inst.display)
