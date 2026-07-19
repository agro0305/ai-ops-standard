#!/usr/bin/env bash
set -euo pipefail

APPLY=0
HOST="0.0.0.0"
REQUESTED_PORT=8787
MAX_PORT_ATTEMPTS=100
SERVICE_NAME="aiops-dashboard"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$PROJECT_ROOT"
SERVICE_USER="${SUDO_USER:-${USER:-$(id -un)}}"

usage() {
  cat <<'EOF'
Usage: dashboard/install_systemd.sh [options]

Options:
  --apply                  Apply changes. Without this flag the script is dry-run.
  --host ADDRESS           Bind address (default: 0.0.0.0).
  --port PORT              Preferred port (default: 8787).
  --max-port-attempts N    Following ports to inspect (default: 100).
  --user USER              Service account (default: current/SUDO_USER).
  --data-dir PATH          Directory containing JSON reports (default: repository root).
  --project-root PATH      AI-OPS repository root.
  -h, --help               Show help.
EOF
}

while (($#)); do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --host) HOST="$2"; shift 2 ;;
    --port) REQUESTED_PORT="$2"; shift 2 ;;
    --max-port-attempts) MAX_PORT_ATTEMPTS="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --project-root) PROJECT_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

PROJECT_ROOT="$(readlink -f "$PROJECT_ROOT")"
DATA_DIR="$(readlink -f "$DATA_DIR")"
SERVER="$PROJECT_ROOT/dashboard/server.py"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TOKEN_FILE="/etc/${SERVICE_NAME}.token"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/var/backups/${SERVICE_NAME}/${TIMESTAMP}"

[[ -f "$SERVER" ]] || { echo "Missing dashboard server: $SERVER" >&2; exit 1; }
[[ -d "$DATA_DIR" ]] || { echo "Missing data directory: $DATA_DIR" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Unknown service user: $SERVICE_USER" >&2; exit 1; }
[[ "$REQUESTED_PORT" =~ ^[0-9]+$ ]] || { echo "Port must be numeric" >&2; exit 1; }
[[ "$MAX_PORT_ATTEMPTS" =~ ^[0-9]+$ ]] || { echo "Max attempts must be numeric" >&2; exit 1; }
(( REQUESTED_PORT >= 1 && REQUESTED_PORT <= 65535 )) || { echo "Port out of range" >&2; exit 1; }
[[ "$PROJECT_ROOT" != *$'\n'* && "$PROJECT_ROOT" != *' '* ]] || { echo "Project path must not contain spaces or newlines" >&2; exit 1; }
[[ "$DATA_DIR" != *$'\n'* && "$DATA_DIR" != *' '* ]] || { echo "Data path must not contain spaces or newlines" >&2; exit 1; }

SELECTED_PORT="$(python3 - "$HOST" "$REQUESTED_PORT" "$MAX_PORT_ATTEMPTS" <<'PY'
import socket, sys
host, start, attempts = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for port in range(start, min(65535, start + attempts) + 1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        continue
    sock.close()
    print(port)
    raise SystemExit(0)
raise SystemExit("no free port found")
PY
)"

SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

echo "AI-OPS Dashboard installation plan"
echo "  Mode:         $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo "  Project:      $PROJECT_ROOT"
echo "  Data:         $DATA_DIR"
echo "  Service user: $SERVICE_USER"
echo "  Bind:         $HOST:$SELECTED_PORT"
echo "  Unit:         $UNIT_FILE"
echo "  Token:        $TOKEN_FILE"
echo "  Backup:       $BACKUP_DIR"
echo "  Firewall:     unchanged"

if [[ $APPLY -ne 1 ]]; then
  echo "No changes made. Re-run with --apply after reviewing the plan."
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "Apply mode must be run with sudo/root." >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
for path in "$UNIT_FILE" "$TOKEN_FILE"; do
  if [[ -e "$path" ]]; then
    cp -a "$path" "$BACKUP_DIR/"
  fi
done

if [[ ! -s "$TOKEN_FILE" ]]; then
  umask 077
  python3 - <<'PY' >"$TOKEN_FILE"
import secrets
print(secrets.token_urlsafe(32))
PY
fi
chown root:"$SERVICE_GROUP" "$TOKEN_FILE"
chmod 0640 "$TOKEN_FILE"

cat >"$UNIT_FILE" <<EOF
[Unit]
Description=AI-OPS read-only dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 $SERVER --data-dir $DATA_DIR --host $HOST --port $SELECTED_PORT --strict-port --auth-token-file $TOKEN_FILE
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "$UNIT_FILE"

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME.service"
systemctl --no-pager --full status "$SERVICE_NAME.service"

echo
echo "Installation complete."
echo "Selected port: $SELECTED_PORT"
echo "Token file: $TOKEN_FILE"
echo "Backup directory: $BACKUP_DIR"
echo "Read the token with: sudo cat $TOKEN_FILE"
