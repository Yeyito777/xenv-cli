# xenv

Nested X11 environments — a full dwm desktop inside Xephyr,
with programmatic control over apps, input, and screenshots.

## Setup

System dependencies:
- `xorg-server-xephyr` — nested X server
- `dwm` — window manager (custom build with `DWM_RUNTIME_DIR`)
- `xdotool` — input injection
- `maim` — screenshots
- `st` — terminal (optional, for launching shells)

```bash
git clone https://github.com/Yeyito777/xenv-cli.git ~/Workspace/Exocortex/external-tools/xenv-cli
cd ~/Workspace/Exocortex/external-tools/xenv-cli
python3 -m venv .venv
```

No Python packages required — only the standard library is used.

## Usage

```
xenv -h                           # full help
xenv start exo                    # start a named environment
xenv run -e exo st                # launch a terminal
xenv type -e exo "ls -la"        # type text
xenv key -e exo Return            # press Enter
xenv screenshot -e exo            # capture the display
xenv stop exo                     # tear it down
```

Run `xenv <command> --help` for per-command help.

## Architecture

Each instance is a named Xephyr + dwm pair. Runtime state (PIDs, display
number, screenshots) is stored in `runtime/xenv-<name>/` within the tool
directory.

The host dwm is patched to support `DWM_RUNTIME_DIR`. When set, dwm writes
logs and state there instead of the default location. The nested dwm uses
its own directory — host state is never touched.
