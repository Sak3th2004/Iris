#!/bin/bash
set -euo pipefail
export XDG_RUNTIME_DIR=/tmp/iris-runtime
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp &
for i in {1..40}; do xdpyinfo >/dev/null 2>&1 && break; sleep .1; done
dbus-run-session -- xfce4-session >/tmp/iris-desktop.log 2>&1 &
# View-only is enforced at the server, not just in the browser viewer.
# Composite the actual X pointer into frames; noVNC does not implement CursorPosUpdates.
x11vnc -display :99 -rfbport 5900 -forever -shared -viewonly -nopw -noclipboard -cursor arrow -nocursorshape -nocursorpos -wait 16 -defer 16 -quiet >/tmp/iris-vnc.log 2>&1 &
exec python /worker/run.py
