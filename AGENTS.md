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
