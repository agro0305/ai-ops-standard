#!/usr/bin/env bash
set -euo pipefail

APPLY=0
INTERVAL="5min"
SERVICE_NAME="aiops-incidents"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="${SUDO_USER:-${USER:-$(id -un)}}"

usage() {
  cat <<'EOF'
Usage: dashboard/install_incident_timer.sh [options]

Options:
  --apply                  Apply changes. Without this flag the script is dry-run.
  --interval VALUE         systemd interval: number + s|min|h|d (default: 5min).
  --user USER              Service account (default: current/SUDO_USER).
  --project-root PATH      AI-OPS repository root.
  -h, --help               Show help.
EOF
}

while (($#)); do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --project-root) PROJECT_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

PROJECT_ROOT="$(readlink -f "$PROJECT_ROOT")"
INCIDENT_SCRIPT="$PROJECT_ROOT/implementations/incidents/aiops_incidents.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TIMER_FILE="/etc/systemd/system/${SERVICE_NAME}.timer"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/var/backups/${SERVICE_NAME}/${TIMESTAMP}"

[[ -f "$INCIDENT_SCRIPT" ]] || { echo "Missing incident script: $INCIDENT_SCRIPT" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Unknown service user: $SERVICE_USER" >&2; exit 1; }
[[ "$INTERVAL" =~ ^[1-9][0-9]*(s|min|h|d)$ ]] || { echo "Invalid interval: $INTERVAL" >&2; exit 1; }
[[ "$PROJECT_ROOT" != *$'\n'* && "$PROJECT_ROOT" != *' '* ]] || { echo "Project path must not contain spaces or newlines" >&2; exit 1; }

SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

echo "AI-OPS incident synchronization timer installation plan"
echo "  Mode:         $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo "  Project:      $PROJECT_ROOT"
echo "  Service user: $SERVICE_USER"
echo "  Interval:     $INTERVAL"
echo "  Service:      $SERVICE_FILE"
echo "  Timer:        $TIMER_FILE"
echo "  Backup:       $BACKUP_DIR"
echo "  State:        $PROJECT_ROOT/.aiops-incidents/state.json.private"
echo "  Report:       $PROJECT_ROOT/incident-status.json"
echo "  Immediate run: no"
echo "  Firewall:     unchanged"

if [[ $APPLY -ne 1 ]]; then
  echo "No changes made. Re-run with --apply after reviewing the plan."
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "Apply mode must be run with sudo/root." >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
for path in "$SERVICE_FILE" "$TIMER_FILE"; do
  if [[ -e "$path" ]]; then
    cp -a "$path" "$BACKUP_DIR/"
  fi
done

install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0750 \
  "$PROJECT_ROOT/.aiops-incidents" "$PROJECT_ROOT/.aiops-audit"

cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=Synchronize AI-OPS deterministic alerts into incident lifecycle state
After=aiops-report-refresh.service

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 $INCIDENT_SCRIPT --root $PROJECT_ROOT sync --actor aiops-incidents --apply
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$PROJECT_ROOT
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=6
EOF
chmod 0644 "$SERVICE_FILE"

cat >"$TIMER_FILE" <<EOF
[Unit]
Description=Periodically synchronize AI-OPS incidents

[Timer]
OnBootSec=4min
OnUnitActiveSec=$INTERVAL
RandomizedDelaySec=20s
Persistent=true
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF
chmod 0644 "$TIMER_FILE"

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.timer"
systemctl --no-pager --full status "${SERVICE_NAME}.timer"

echo
echo "Installation complete."
echo "No incident synchronization was run during installation."
echo "Backup directory: $BACKUP_DIR"
echo "Run now: systemctl start ${SERVICE_NAME}.service"
echo "Check schedule: systemctl list-timers ${SERVICE_NAME}.timer --no-pager"
