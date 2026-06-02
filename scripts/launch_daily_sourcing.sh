#!/bin/bash
# launch_daily_sourcing.sh
# Opens Terminal.app and runs Claude Code with the daily-sourcing prompt.
# Output is mirrored to a timestamped log in <repo>/logs/.
#
# Invoked by ~/Library/LaunchAgents/com.<you>.daily-sourcing.plist at noon
# local time, or manually for testing:
#   bash <repo>/scripts/launch_daily_sourcing.sh

set -u

# Resolve paths relative to this script — no hardcoded user paths.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PROMPT_FILE="$REPO_ROOT/prompts/daily-sourcing.txt"
LOGS_DIR="$REPO_ROOT/logs"
mkdir -p "$LOGS_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOGS_DIR/sourcing-$TIMESTAMP.log"

# Make sure we can find `claude` even when launchd gives us a minimal PATH.
# The Claude Code CLI installs to ~/.local/bin by default on macOS.
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "FATAL: prompt file missing at $PROMPT_FILE" | tee "$LOG_FILE" >&2
  exit 1
fi

# Kill any lingering daily-sourcing claude processes before starting a new one.
# Without this, sleep cycles can leave claude stuck on dead API/Chrome connections
# indefinitely, piling up zombies across multiple days.
LINGERING="$(pgrep -f 'claude.*--chrome.*job-sourcing-spec.md' 2>/dev/null || true)"
if [ -n "$LINGERING" ]; then
  echo "[launcher] killing lingering sourcing claudes: $LINGERING" | tee -a "$LOG_FILE" >&2
  pkill -f 'claude.*--chrome.*job-sourcing-spec.md' 2>/dev/null || true
  sleep 2
  pkill -9 -f 'claude.*--chrome.*job-sourcing-spec.md' 2>/dev/null || true
fi

# Build the command that runs *inside* the new Terminal window.
# `script` mirrors the interactive session to the log file so you can review later.
INNER_CMD="cd \"$REPO_ROOT\" && script -q \"$LOG_FILE\" claude --dangerously-skip-permissions --chrome \"\$(cat \"$PROMPT_FILE\")\""

# AppleScript helper: escape backslashes, quotes, newlines for embedding.
applescript_escape() {
  python3 -c 'import sys; s=sys.stdin.read(); print(s.replace("\\","\\\\").replace("\"","\\\"").replace("\n"," "))' <<< "$1"
}

CMD_ESC="$(applescript_escape "$INNER_CMD")"

# Use macOS native Terminal.app for reliability across user configs.
osascript <<EOF 2>/dev/null
tell application "Terminal"
  activate
  do script "$CMD_ESC"
end tell
EOF

# Fallback: if osascript failed (e.g. no GUI session), run headless to log.
if [ $? -ne 0 ]; then
  echo "[launcher] osascript failed — falling back to headless run" | tee -a "$LOG_FILE"
  cd "$REPO_ROOT"
  claude -p "$(cat "$PROMPT_FILE")" --dangerously-skip-permissions --chrome >> "$LOG_FILE" 2>&1
fi
