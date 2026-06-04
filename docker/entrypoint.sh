#!/usr/bin/env bash
# Unraid-friendly entrypoint: map the runtime user to the host's PUID/PGID so
# files written to the array are owned correctly, apply UMASK, prepare the
# volume directories, then drop privileges and launch the server.
set -euo pipefail

PUID="${PUID:-99}"
PGID="${PGID:-100}"
UMASK="${UMASK:-022}"
PORT="${PORT:-8080}"

umask "$UMASK"

# Create / re-id the unprivileged user to match the host IDs.
if getent group appuser >/dev/null 2>&1; then
  groupmod -o -g "$PGID" appuser
else
  groupadd -o -g "$PGID" appuser
fi
if id appuser >/dev/null 2>&1; then
  usermod -o -u "$PUID" -g "$PGID" appuser
else
  useradd -o -u "$PUID" -g "$PGID" -d /app -s /usr/sbin/nologin appuser
fi

mkdir -p "$CONFIG_DIR/cookies" "$CONFIG_DIR/logs" "$DOWNLOAD_DIR"
# Config is small -> safe to chown recursively. Downloads may be huge, so only
# fix the top-level dir (new files inherit the runtime user anyway).
chown -R "$PUID:$PGID" "$CONFIG_DIR" 2>/dev/null || true
chown "$PUID:$PGID" "$DOWNLOAD_DIR" 2>/dev/null || true

echo "[entrypoint] Starting as PUID=$PUID PGID=$PGID UMASK=$UMASK on port $PORT"

if [ "$#" -gt 0 ]; then
  exec gosu "$PUID:$PGID" "$@"
fi

exec gosu "$PUID:$PGID" uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
