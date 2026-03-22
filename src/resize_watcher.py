"""Resize watcher — monitors Xephyr display and forces dwm relayout on resize.

When Xephyr's host window is resized, it updates the root window and RandR
output, but dwm doesn't always receive the ConfigureNotify it needs to
re-layout. This watcher detects size changes and forces a re-notify.

Started as a detached process by lifecycle.start().
Usage: DISPLAY=:N python3 src/resize_watcher.py
"""

import os
import re
import subprocess
import time

POLL_INTERVAL = float(os.environ.get("XENV_RESIZE_POLL", "0.5"))


def get_size():
    try:
        r = subprocess.run(["xrandr"], capture_output=True, text=True)
        m = re.search(r"current (\d+) x (\d+)", r.stdout)
        if m:
            return f"{m.group(1)}x{m.group(2)}"
    except Exception:
        pass
    return None


def main():
    prev = None
    while True:
        cur = get_size()
        if cur is None:
            break
        if prev is not None and cur != prev:
            subprocess.run(["xrandr", "-s", cur], capture_output=True)
        prev = cur
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
