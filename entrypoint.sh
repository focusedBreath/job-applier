#!/bin/sh
set -e

# Start Xvfb in background
Xvfb :99 -screen 0 1280x900x24 -ac &
XVFB_PID=$!
export DISPLAY=:99

# Wait for Xvfb to be ready
sleep 1

echo "Xvfb started (pid $XVFB_PID), DISPLAY=$DISPLAY"

exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8080
