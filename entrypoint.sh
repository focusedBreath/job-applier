#!/bin/sh
set -e

# Clean up stale Xvfb lock files
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# Start Xvfb
Xvfb :99 -screen 0 1280x900x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
export DISPLAY=:99

# Wait for Xvfb to be ready
echo "Waiting for Xvfb..."
for i in $(seq 1 20); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb ready on :99"
        break
    fi
    sleep 0.5
done

# Start x11vnc — serves the Xvfb display over VNC (no password for local dev)
x11vnc -display :99 -nopw -listen localhost -xkb -forever -shared -bg -o /tmp/x11vnc.log
echo "x11vnc started"

# Start noVNC — wraps VNC in a WebSocket so you can view it at http://localhost:6080
websockify --web=/usr/share/novnc/ --wrap-mode=ignore 0.0.0.0:6080 localhost:5900 &
echo "noVNC started on port 6080"

# Start the app
exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8080
