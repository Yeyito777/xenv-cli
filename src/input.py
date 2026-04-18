"""Input commands: click, type_text, key, move, scroll, drag, focus."""

import argparse
import subprocess
import sys

from src.helpers import (
    Instance, die, require_instance_name,
    make_env, run_quiet, send_keys, send_type,
)


# ── click ────────────────────────────────────────────────────────

def click(argv):
    p = argparse.ArgumentParser(prog="xenv click", description=(
        "Click at pixel coordinates in the nested display."
    ))
    p.add_argument("x", type=int, help="X coordinate")
    p.add_argument("y", type=int, help="Y coordinate")
    p.add_argument("--button", "-b", type=int, default=1,
                    help="Mouse button (1=left, 2=middle, 3=right; default: 1)")
    p.add_argument("--double", "-d", action="store_true", help="Double-click")
    args = p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    env = make_env(inst.display)
    repeat = 2 if args.double else 1

    subprocess.run([
        "xdotool", "mousemove", "--sync", str(args.x), str(args.y),
        "click", "--repeat", str(repeat), str(args.button),
    ], env=env)

    label = "double-click" if args.double else "click"
    print(f"{label} ({args.x}, {args.y}) button={args.button}")


# ── type_text (type) ─────────────────────────────────────────────

def type_text(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""\
Usage: xenv type -e <name> <text>

Type text into the focused window via synthetic keystrokes.
For special keys use 'xenv key' instead.

Examples:
  xenv type -e exo "echo hello world"
  xenv type -e exo "https://example.com" """)
        sys.exit(0 if argv else 1)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    text = " ".join(argv)
    send_type(inst.display, text)
    print(f"typed {len(text)} chars")


# ── key ──────────────────────────────────────────────────────────

def key(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""\
Usage: xenv key -e <name> <key> [key2 ...]

Send keystrokes to the focused window (xdotool format).

Key names:   Return, Tab, Escape, BackSpace, Delete, space,
             Up, Down, Left, Right, Home, End, Page_Up, Page_Down
Modifiers:   ctrl+x, alt+x, shift+x, super+x

Examples:
  xenv key -e exo Return
  xenv key -e exo ctrl+l
  xenv key -e exo super+Return       # dwm: spawn terminal
  xenv key -e exo Escape Tab Return  # sequence""")
        sys.exit(0 if argv else 1)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    send_keys(inst.display, argv)
    print(f"sent: {' '.join(argv)}")


# ── move ─────────────────────────────────────────────────────────

def move(argv):
    p = argparse.ArgumentParser(prog="xenv move", description=(
        "Move the mouse cursor to pixel coordinates."
    ))
    p.add_argument("x", type=int, help="X coordinate")
    p.add_argument("y", type=int, help="Y coordinate")
    args = p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    env = make_env(inst.display)
    subprocess.run(["xdotool", "mousemove", "--sync", str(args.x), str(args.y)], env=env)
    print(f"moved to ({args.x}, {args.y})")


# ── scroll ───────────────────────────────────────────────────────

SCROLL_BUTTONS = {"up": 4, "down": 5, "left": 6, "right": 7}


def scroll(argv):
    p = argparse.ArgumentParser(prog="xenv scroll", description=(
        "Scroll the mouse wheel."
    ))
    p.add_argument("direction", choices=SCROLL_BUTTONS.keys(),
                    help="Scroll direction")
    p.add_argument("clicks", nargs="?", type=int, default=3,
                    help="Number of clicks (default: 3)")
    args = p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    button = SCROLL_BUTTONS[args.direction]
    env = make_env(inst.display)
    subprocess.run([
        "xdotool", "click", "--repeat", str(args.clicks),
        "--delay", "50", str(button),
    ], env=env)
    print(f"scrolled {args.direction} ({args.clicks} clicks)")


# ── drag ─────────────────────────────────────────────────────────

def drag(argv):
    p = argparse.ArgumentParser(prog="xenv drag", description=(
        "Click-and-drag from (x1,y1) to (x2,y2)."
    ))
    p.add_argument("x1", type=int)
    p.add_argument("y1", type=int)
    p.add_argument("x2", type=int)
    p.add_argument("y2", type=int)
    args = p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    env = make_env(inst.display)
    subprocess.run([
        "xdotool",
        "mousemove", "--sync", str(args.x1), str(args.y1),
        "mousedown", "1",
        "mousemove", "--sync", str(args.x2), str(args.y2),
        "mouseup", "1",
    ], env=env)
    print(f"dragged ({args.x1},{args.y1}) → ({args.x2},{args.y2})")


# ── focus ────────────────────────────────────────────────────────

def focus(argv):
    p = argparse.ArgumentParser(prog="xenv focus", description=(
        "Focus a window by numeric ID or name search."
    ))
    p.add_argument("target", help="Window ID (numeric) or name substring")
    args = p.parse_args(argv)

    name = require_instance_name()
    inst = Instance(name)
    inst.require_running()

    display = inst.display
    env = make_env(display)
    target = args.target

    if target.isdigit():
        wid = target
    else:
        out = run_quiet(
            ["xdotool", "search", "--onlyvisible", "--name", target],
            env=env,
        )
        if not out:
            die(f"focus: no window matching '{target}'")
        wid = out.split("\n")[0]

    subprocess.run(["xdotool", "windowactivate", "--sync", wid], env=env)
    wname = run_quiet(["xdotool", "getwindowname", wid], env=env) or ""
    suffix = f" ({wname})" if wname else ""
    print(f"focused {wid}{suffix}")

