#!/bin/bash

# Create a log directory in the user's home directory (or relative to the repo if preferred)
LOG_DIR="${HOME}/.ddns"
mkdir -p "${LOG_DIR}"
LOGFILE="${LOG_DIR}/ddns_monitor.log"
VENV_PYTHON="./venv/bin/python3"
while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    # Now ddns_update.py is referenced relative to REPO_ROOT (the working directory)
    $VENV_PYTHON ./ddns/ddns_update.py >> "$LOGFILE" 2>&1
    EXIT_STATUS=$?
    if [ $EXIT_STATUS -ne 0 ]; then
        echo "[$TIMESTAMP] ERROR: ddns_update.py exited with status $EXIT_STATUS" >> "$LOGFILE"
    else
        echo "[$TIMESTAMP] SUCCESS: ddns_update.py ran successfully" >> "$LOGFILE"
    fi
    sleep 10
done
