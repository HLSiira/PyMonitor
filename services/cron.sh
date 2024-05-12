#!/bin/bash

# Get the directory of the current script.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

# Call sendAlert.py with the absolute path
cd "$SCRIPT_DIR/.." && python3 "$SCRIPT_DIR/../sendAlert.py" -s "CRON" "$@"
