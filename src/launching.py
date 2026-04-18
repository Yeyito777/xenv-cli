"""Launching commands: run, execute (exec)."""

import os
import subprocess
import sys

from src.helpers import Instance, die, make_env, require_instance_name, spawn_persistent


# ── run ──────────────────────────────────────────────────────────

def run(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""\
Usage: xenv run -e <name> <command> [args...]

Launch a command inside the environment (backgrounded, detached).

Examples:
  xenv run -e exo st
  xenv run -e exo firefox
  XENV_INSTANCE=exo xenv run st""")
        sys.exit(0 if argv else 1)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    env = make_env(inst.display)
    _unit, pid = spawn_persistent(
        argv,
        env=env,
        unit_prefix=f"xenv-{name}-run",
    )
    if pid is not None:
        print(f"launched: {' '.join(argv)} (PID {pid})")
    else:
        print(f"launched: {' '.join(argv)}")


# ── execute (exec) ───────────────────────────────────────────────

def execute(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""\
Usage: xenv exec -e <name> <command> [args...]

Execute a command inside the environment (foreground, blocking).

Examples:
  xenv exec -e exo xdotool getdisplaygeometry
  xenv exec -e exo xrandr""")
        sys.exit(0 if argv else 1)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    env = make_env(inst.display)
    result = subprocess.run(argv, env=env)
    sys.exit(result.returncode)
