# OpenAPI MCP + Pydantic AI example

This example connects:

```text
Pydantic AI
    ↓
New API
    ↓
codex/gpt-5.5
    ↓
AWS Labs OpenAPI MCP Server
    ↓
AI-OPS Dashboard API
```

## Requirements

- AI-OPS Dashboard at `http://127.0.0.1:8789`
- OpenAPI Generator CLI 7.23.0
- AWS Labs OpenAPI MCP Server 1.1.1
- FastMCP 3.4.4
- Pydantic AI 2.13.0
- New API with an OpenAI-compatible `/v1` endpoint

## Validate the OpenAPI specification

```bash
openapi-generator-cli validate \
  -i examples/openapi-mcp-pydantic-ai/aiops-dashboard.openapi.yaml
```

## Generate the Python client

```bash
openapi-generator-cli generate \
  -i examples/openapi-mcp-pydantic-ai/aiops-dashboard.openapi.yaml \
  -g python \
  -o examples/openapi-mcp-pydantic-ai/generated/python-client \
  --additional-properties=packageName=aiops_dashboard_client,projectName=aiops-dashboard-client,packageVersion=0.1.0
```

The `generated/` directory is intentionally excluded from Git.

## Persistent local configuration

Store credentials outside the repository:

```bash
install -d -m 700 ~/.config/aiops
umask 077
cat > ~/.config/aiops/new-api.env <<'ENV'
NEW_API_TOKEN='replace-with-a-valid-token'
NEW_API_BASE_URL='http://127.0.0.1:3500/v1'
NEW_API_MODEL='codex/gpt-5.5'
AIOPS_DASHBOARD_URL='http://127.0.0.1:8789'
ENV
chmod 600 ~/.config/aiops/new-api.env
```

Never commit the token.

## Run the Pydantic AI agent

```bash
set -a
source ~/.config/aiops/new-api.env
set +a

~/.local/share/pydantic-ai/venv/bin/python \
  examples/openapi-mcp-pydantic-ai/run_agent.py
```

The agent must call both MCP tools:

- `getHealth`
- `getReadiness`

## Use from another coding agent

Copy the contents of `mcp-config.example.json` into the MCP configuration used by the coding agent. The configuration starts `run_mcp_server.sh`, which resolves the installed AWS Labs server and the OpenAPI specification automatically.

Add the rules from `AGENT_INSTRUCTIONS.md` to the project's agent instruction file, such as `AGENTS.md` or `CLAUDE.md`.

The MCP integration is currently read-only. It checks dashboard health and readiness; it does not perform or prove backup, execution, verification, rollback or audit operations.
