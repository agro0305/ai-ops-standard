# AI-OPS Compliance Suite

The compliance suite maps normative AIS requirements to automated tests and documented manual assessments.

## Profiles

- `core`: AIS-0000 through AIS-0008
- `mcp-aware`: core plus AIS-0009
- `multi-agent`: mcp-aware plus AIS-0010
- `platform`: multi-agent plus AIS-0011
- `full-draft`: all current specifications

## Rules

- Tests are non-destructive by default.
- State-changing tests use fixtures, sandboxes, containers or disposable virtual machines.
- Every result references a requirement ID.
- Evidence must be redacted.
- A profile passes only when all applicable MUST requirements pass.

## Planned structure

```text
compliance/
├── README.md
├── manifest.yaml
├── tests/
│   ├── core/
│   ├── discovery/
│   ├── backup/
│   ├── mcp/
│   └── registry/
└── fixtures/
```

Results conform to `schemas/compliance-result.schema.json`.