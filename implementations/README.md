# AI-OPS Reference Implementation

The reference implementation will provide safe, read-only discovery first, followed by backup, execution, verification and reporting components.

## Planned commands

```text
aiops discover
aiops plan
aiops backup
aiops execute
aiops verify
aiops rollback
aiops report
aiops compliance
aiops dashboard
```

## Initial modules

- system and hardware inventory
- storage and filesystem health
- network, ports, firewall and Tailscale
- systemd, cron and timers
- Docker, Compose, Podman and Kubernetes
- Git repositories and worktree state
- AI agent capability registry
- MCP server registry
- OpenAPI and API discovery
- backup adapters
- verification runners
- JSON/YAML report generation

## Safety

Discovery is read-only by default. State-changing commands require a plan, risk classification, backup evidence and approval according to the specifications. The implementation must not alter system Python, replace existing configuration wholesale or expose secrets.