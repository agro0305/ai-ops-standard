#!/usr/bin/env bash
set -euo pipefail

SERVER_COMMAND="${AIOPS_OPENAPI_MCP_COMMAND:-}"
if [[ -z "$SERVER_COMMAND" ]]; then
  SERVER_COMMAND="$(command -v awslabs.openapi-mcp-server || true)"
fi

if [[ -z "$SERVER_COMMAND" ]]; then
  echo "awslabs.openapi-mcp-server was not found in PATH" >&2
  exit 127
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SPEC_PATH="$SCRIPT_DIR/aiops-dashboard.openapi.yaml"
DASHBOARD_URL="${AIOPS_DASHBOARD_URL:-http://127.0.0.1:8789}"

exec "$SERVER_COMMAND" \
  --api-name aiops-dashboard \
  --api-url "$DASHBOARD_URL" \
  --spec-path "$SPEC_PATH" \
  --auth-type none \
  --allow-insecure-http \
  --allow-private-networks \
  --allowed-spec-dirs "$SCRIPT_DIR" \
  --log-level ERROR
