#!/bin/bash
# Local app-level watchdog: if the backend's own /health endpoint doesn't
# respond OK, restart the service. This catches ordinary crashes (gunicorn
# worker died, unhandled exception took the process down) - it does NOT
# catch the OS/network-level failure from 2026-09-29 (the box was reachable
# on localhost the whole time in that scenario, just unreachable externally)
# - that class of failure is covered separately by the external Cloud Run +
# Scheduler health check, which probes from outside the VM.

LOG_TAG="health-watchdog"
URL="http://localhost:5001/health"

if ! curl -fsS --max-time 10 "$URL" > /dev/null 2>&1; then
    logger -t "$LOG_TAG" "Health check failed, restarting because-future-backend.service"
    systemctl restart because-future-backend.service
else
    logger -t "$LOG_TAG" "Health check OK"
fi
