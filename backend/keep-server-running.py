#!/usr/bin/env python3
"""
Flask Server Monitor - Python Version
Keeps the Flask server running with automatic restarts
Includes health checks and better error handling
"""

import subprocess
import time
import signal
import sys
import os
from datetime import datetime
from pathlib import Path

# Configuration
APP_DIR = Path(__file__).parent.absolute()
APP_FILE = "app.py"
PYTHON_CMD = "python"  # or "python3"
LOG_FILE = APP_DIR / "flask_server.log"
PID_FILE = APP_DIR / "flask_server.pid"
MAX_RESTARTS = 10
RESTART_DELAY = 5
HEALTH_CHECK_INTERVAL = 30  # seconds

# State
flask_process = None
restart_count = 0
running = True


def log(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def cleanup(signum=None, frame=None):
    """Cleanup on exit"""
    global running, flask_process
    
    log("Received shutdown signal. Cleaning up...", "WARNING")
    running = False
    
    if flask_process and flask_process.poll() is None:
        log(f"Stopping Flask server (PID: {flask_process.pid})...")
        flask_process.terminate()
        try:
            flask_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log("Force killing Flask server...", "WARNING")
            flask_process.kill()
    
    if PID_FILE.exists():
        PID_FILE.unlink()
    
    log("Cleanup complete. Exiting.", "INFO")
    sys.exit(0)


def check_health():
    """Check if Flask server is responding"""
    try:
        import requests
        response = requests.get("http://localhost:5000/api/message", timeout=5)
        return response.status_code == 200
    except Exception as e:
        log(f"Health check failed: {e}", "WARNING")
        return False


def start_flask_server():
    """Start the Flask server"""
    global flask_process
    
    log("=" * 50)
    log(f"Starting Flask Server (Attempt {restart_count + 1})")
    log("=" * 50)
    
    # Ensure we're in the app directory
    os.chdir(APP_DIR)
    
    # Check if app.py exists
    if not (APP_DIR / APP_FILE).exists():
        log(f"Flask app not found: {APP_DIR / APP_FILE}", "ERROR")
        sys.exit(1)
    
    # Open log file
    log_handle = open(LOG_FILE, "a")
    log_handle.write(f"\n{'='*50}\n")
    log_handle.write(f"Starting at {datetime.now()}\n")
    log_handle.write(f"{'='*50}\n")
    log_handle.flush()
    
    # Start Flask server
    flask_process = subprocess.Popen(
        [PYTHON_CMD, APP_FILE],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        cwd=APP_DIR
    )
    
    # Save PID
    PID_FILE.write_text(str(flask_process.pid))
    
    log(f"✓ Flask server started with PID: {flask_process.pid}")
    log(f"✓ Logs: tail -f {LOG_FILE}")
    
    return flask_process


def monitor_loop():
    """Main monitoring loop"""
    global restart_count, running, flask_process
    
    last_health_check = time.time()
    
    while running and restart_count < MAX_RESTARTS:
        # Start server if not running
        if flask_process is None or flask_process.poll() is not None:
            if flask_process is not None:
                exit_code = flask_process.poll()
                if exit_code == 0:
                    log(f"⚠ Flask server exited normally (exit code: {exit_code})", "WARNING")
                else:
                    log(f"✗ Flask server crashed (exit code: {exit_code})", "ERROR")
                
                restart_count += 1
                
                if restart_count >= MAX_RESTARTS:
                    log(f"✗ Maximum restart attempts ({MAX_RESTARTS}) reached.", "ERROR")
                    log(f"✗ Please check the logs: {LOG_FILE}", "ERROR")
                    sys.exit(1)
                
                log(f"⏳ Waiting {RESTART_DELAY} seconds before restart...", "WARNING")
                time.sleep(RESTART_DELAY)
            
            flask_process = start_flask_server()
        
        # Periodic health check
        current_time = time.time()
        if current_time - last_health_check >= HEALTH_CHECK_INTERVAL:
            if check_health():
                log("✓ Health check passed", "INFO")
                restart_count = 0  # Reset counter on successful health check
            else:
                log("✗ Health check failed - server may be unresponsive", "WARNING")
            last_health_check = current_time
        
        # Short sleep to avoid CPU spinning
        time.sleep(1)


def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    log("=" * 50)
    log("Flask Auto-Restart Monitor (Python)")
    log("=" * 50)
    log(f"App Directory: {APP_DIR}")
    log(f"Log File: {LOG_FILE}")
    log(f"PID File: {PID_FILE}")
    log("")
    
    # Check if virtual environment is activated
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        log("✓ Virtual environment is activated")
    else:
        log("⚠ Virtual environment not detected. Make sure dependencies are installed.", "WARNING")
    
    try:
        monitor_loop()
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        log(f"✗ Unexpected error: {e}", "ERROR")
        cleanup()


if __name__ == "__main__":
    main()
