#!/bin/sh
set -e

# Clean up stale Xvfb lock files
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# Start Xvfb in background
Xvfb :99 -screen 0 1280x900x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
export DISPLAY=:99

# Wait until Xvfb is accepting connections
echo "Waiting for Xvfb..."
for i in $(seq 1 20); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb ready on :99"
        break
    fi
    sleep 0.5
done

exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8080
