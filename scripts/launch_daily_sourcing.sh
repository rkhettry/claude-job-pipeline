#!/bin/bash
# launch_daily_sourcing.sh
# Opens iTerm 2 (Terminal.app fallback) in ~/resume and runs Claude Code with
# the daily-sourcing prompt. Output is mirrored to a timestamped log.
#
# Invoked by ~/Library/LaunchAgents/com.{{USERNAME}}.daily-sourcing.plist at noon local time,
# or manually for testing: bash ~/resume/automation/scripts/launch_daily_sourcing.sh

set -u

RESUME_ROOT="${RESUME_ROOT:-$HOME/<your-repo>}"
AUTOMATION_DIR="$RESUME_ROOT/automation"
PROMPT_FILE="$AUTOMATION_DIR/prompts/daily-sourcing.txt"
LOGS_DIR="$AUTOMATION_DIR/logs"
mkdir -p "$LOGS_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOGS_DIR/sourcing-$TIMESTAMP.log"

# Make sure we can find `claude` even when launchd gives us a minimal PATH.
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "FATAL: prompt file missing at $PROMPT_FILE" | tee "$LOG_FILE" >&2
  exit 1
fi

# Direct-from-ATS watchlist poll first — plain Python, no Claude tokens, ~60s.
# Appends new-grad hits from ~160 company boards straight into jobs.xlsx so
# the Claude sourcing run that follows already sees them (and dedupes against
# them). Failure here must never block the main sourcing run.
WATCHLIST_LOG="$LOGS_DIR/watchlist-$TIMESTAMP.log"
python3 "$AUTOMATION_DIR/watchlist_poller.py" > "$WATCHLIST_LOG" 2>&1 \
  && echo "[launcher] watchlist poll OK: $(tail -1 "$WATCHLIST_LOG")" \
  || echo "[launcher] watchlist poll FAILED (see $WATCHLIST_LOG) — continuing" >&2

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

# Per-run close helper — sets a unique window title via OSC 0 escape, then
# closes that exact Terminal window once claude exits. Lives next to the log.
WINDOW_TITLE="claude-sourcing-$TIMESTAMP"
CLOSE_SCRIPT="$LOGS_DIR/close-$TIMESTAMP.sh"
cat > "$CLOSE_SCRIPT" <<EOSCRIPT
#!/bin/bash
osascript -e 'tell application "Terminal" to close (every window whose name contains "$WINDOW_TITLE") saving no' 2>/dev/null
EOSCRIPT
chmod +x "$CLOSE_SCRIPT"

# Build the command that runs *inside* the new terminal window.
# `script` mirrors the interactive session to the log file so you can review later.
# `claude -p` would run headless; we use interactive so you can monitor and interject.
# After claude exits, the close helper runs in the background and the shell exits —
# Terminal disposes of the window automatically.
# stream-json (+ required --verbose) writes one JSON event per line LIVE into
# the log — feeds the 📡 live viewer at localhost:8765/runs. Plain -p would
# buffer all output until the end and leave the log empty mid-run.
# After the Claude run exits it has written automation/digest-YYYY-MM-DD.md;
# send_digest.py then emails it via Gmail SMTP (no Chrome needed). This runs
# inside the spawned window, right after claude, so the email always goes out.
INNER_CMD="printf '\\033]0;$WINDOW_TITLE\\007'; cd \"$RESUME_ROOT\" && claude -p --verbose --output-format stream-json --dangerously-skip-permissions --chrome \"\$(cat \"$PROMPT_FILE\")\" 2>&1 | tee \"$LOG_FILE\"; echo '[launcher] sending digest via SMTP...' | tee -a \"$LOG_FILE\"; python3 \"$AUTOMATION_DIR/send_digest.py\" 2>&1 | tee -a \"$LOG_FILE\"; bash \"$CLOSE_SCRIPT\" & sleep 1; exit"

# AppleScript helper: escape backslashes, quotes, newlines for embedding.
applescript_escape() {
  python3 -c 'import sys; s=sys.stdin.read(); print(s.replace("\\","\\\\").replace("\"","\\\"").replace("\n"," "))' <<< "$1"
}

CMD_ESC="$(applescript_escape "$INNER_CMD")"

# Use macOS native Terminal.app (the user has a weird iTerm config — Terminal is more reliable).
osascript <<EOF 2>/dev/null
tell application "Terminal"
  activate
  do script "$CMD_ESC"
end tell
EOF

# Fallback: if osascript failed entirely (e.g. no GUI session), run headless to log.
if [ $? -ne 0 ]; then
  echo "[launcher] osascript failed — falling back to headless run" | tee -a "$LOG_FILE"
  cd "$RESUME_ROOT"
  claude -p --verbose --output-format stream-json "$(cat "$PROMPT_FILE")" --dangerously-skip-permissions --chrome >> "$LOG_FILE" 2>&1
  echo "[launcher] sending digest via SMTP..." | tee -a "$LOG_FILE"
  python3 "$AUTOMATION_DIR/send_digest.py" >> "$LOG_FILE" 2>&1
fi
