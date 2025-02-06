#!/bin/bash

# Create a log directory in the user's home directory (or relative to the repo if preferred)
LOG_DIR="${HOME}/.ddns"
mkdir -p "${LOG_DIR}"
LOGFILE="${LOG_DIR}/ddns_monitor.log"
VENV_PYTHON="./venv/bin/python3"

# Define maximum allowed log file size (in bytes, e.g., 10MB)
MAX_SIZE=5485760
# Define maximum number of rotated log files to keep
MAX_ROTATED=5

# Function to perform log rotation
rotate_log() {
    if [ -f "$LOGFILE" ]; then
        FILE_SIZE=$(stat -c%s "$LOGFILE")
        if [ "$FILE_SIZE" -ge "$MAX_SIZE" ]; then
            TIMESTAMP=$(date '+%Y%m%d%H%M%S')
            mv "$LOGFILE" "${LOGFILE}.${TIMESTAMP}"
            # Optionally, compress the rotated log file:
            # gzip "${LOGFILE}.${TIMESTAMP}"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: Log file rotated." >> "$LOGFILE"
            prune_logs
        fi
    fi
}

# Function to prune old rotated logs
prune_logs() {
    # List rotated log files matching the pattern: ddns_monitor.log.*
    ROTATED_FILES=( $(ls -1t "${LOGFILE}".* 2>/dev/null) )
    NUM_FILES=${#ROTATED_FILES[@]}
    if [ "$NUM_FILES" -gt "$MAX_ROTATED" ]; then
        # Remove the oldest files if we have more than MAX_ROTATED files
        for (( i=MAX_ROTATED; i<NUM_FILES; i++ )); do
            rm -f "${ROTATED_FILES[$i]}"
        done
    fi
}

while true; do
    # Check and rotate the log if needed before each run
    rotate_log

    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    # Run your Python script and append its output to the log file
    $VENV_PYTHON ./ddns/ddns_update.py >> "$LOGFILE" 2>&1
    EXIT_STATUS=$?
    if [ $EXIT_STATUS -ne 0 ]; then
        echo "[$TIMESTAMP] ERROR: ddns_update.py exited with status $EXIT_STATUS" >> "$LOGFILE"
    else
        echo "[$TIMESTAMP] SUCCESS: ddns_update.py ran successfully" >> "$LOGFILE"
    fi
    sleep 10
done
