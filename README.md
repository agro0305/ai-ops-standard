# AI-OPS Standard

Open standard for safe, repeatable and auditable AI operations on Linux infrastructure, MCP servers and AI coding agents.

AI-OPS defines how an AI agent discovers current state, plans a minimal change, obtains approval, creates backups, executes, verifies, rolls back and produces an audit record.

## Project layers

```text
AI-OPS Standard
├── Specification
├── Reference Implementation
├── Compliance Suite
└── Dashboard
```

## Lifecycle

```text
Discovery → Analysis → Plan → Approval → Backup → Execution → Verification → Rollback Decision → Audit
```

## Specifications

| Document | Title | Status |
|---|---|---|
| AIS-STYLE-0001 | Document Style Guide | Draft |
| AIS-0000 | Introduction | Draft |
| AIS-0001 | Mission | Draft |
| AIS-0002 | Core Principles | Draft |
| AIS-0003 | Discovery | Draft |
| AIS-0004 | Planning | Draft |
| AIS-0005 | Backup | Draft |
| AIS-0006 | Execution | Draft |
| AIS-0007 | Verification | Draft |
| AIS-0008 | Rollback | Draft |
| AIS-0009 | MCP Discovery | Draft |
| AIS-0010 | AI Capability Registry | Draft |
| AIS-0011 | Dashboard | Draft |
| AIS-0012 | Compliance | Draft |

English documents are canonical. Serbian translations use the `.sr.md` suffix.

## Repository

- `specifications/` — normative documents
- `implementations/` — reference implementation
- `compliance/` — conformance tests and fixtures
- `schemas/` — machine-readable records
- `dashboard/` — local-first operational UI
- `templates/` — reports and plans
- `skills/` — instructions for AI agents
- `rfcs/` — proposals before standardization

## Current status

- Project version: 0.1.0
- Specification status: Draft
- Canonical language: English
- Serbian documentation: maintained in parallel

## Scope

Initial targets include Ubuntu and other Linux systems, systemd, Docker, Podman, Kubernetes discovery, Git, MCP servers, Kimi Code, Claude Code, Codex CLI, OpenCode, model gateways, OpenAPI, Pydantic AI, local networks and Tailscale.

## License

Apache License 2.0.