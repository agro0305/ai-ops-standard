# AGENTS.md

All AI agents MUST follow:

```text
Discovery → Analysis → Plan → Approval → Backup → Execution → Verification → Rollback Decision → Audit
```

Mandatory rules:

1. Inspect current state before changes.
2. Do not assume tools, ports, services or MCP servers are absent.
3. Back up before modifying existing configuration.
4. Preserve existing services unless explicitly requested otherwise.
5. Use the smallest possible change.
6. Verify every change.
7. Provide rollback instructions.
8. Produce a structured operation report.
9. Never expose secrets.
10. Stop before destructive or safety-critical actions without explicit approval.

## AI-OPS MCP skill

For infrastructure, service, deployment, configuration, migration, repair or other operational work, load and follow:

```text
.agents/skills/ai-ops-mcp/SKILL.md
```

Current MCP server: `aiops-dashboard`.

Current tools are read-only status checks:

- `getHealth`
- `getReadiness`

Call both tools once at the beginning of one infrastructure task. Reuse that result for the task. Do not repeat the same checks after every message or command unless the MCP/dashboard restarted, connectivity failed, the result became stale, or the user explicitly requested a new check.

Do not use this MCP pre-check for ordinary documentation, code refactoring or isolated local tests that do not affect infrastructure.

The current MCP integration does not perform or prove plan, approval, backup, execution, verification, rollback or audit stages. Never claim otherwise.
