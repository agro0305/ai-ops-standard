# Standard overview

AI-OPS Standard separates normative requirements from the reference implementation. English specification documents are canonical; Serbian translations use the `.sr.md` suffix.

## Normative documents

| Document | Subject |
|---|---|
| [AIS-0000](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0000.md) | Introduction |
| [AIS-0001](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0001.md) | Mission |
| [AIS-0002](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0002.md) | Core principles |
| [AIS-0003](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0003.md) | Discovery |
| [AIS-0004](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0004.md) | Planning |
| [AIS-0005](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0005.md) | Backup |
| [AIS-0006](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0006.md) | Execution |
| [AIS-0007](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0007.md) | Verification |
| [AIS-0008](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0008.md) | Rollback |
| [AIS-0009](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0009.md) | MCP discovery |
| [AIS-0010](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0010.md) | AI capability registry |
| [AIS-0011](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0011.md) | Dashboard |
| [AIS-0012](https://github.com/agro0305/ai-ops-standard/blob/main/specifications/AIS-0012.md) | Compliance |

## Conformance model

An implementation is expected to:

1. discover current state without mutation;
2. create a deterministic plan;
3. classify risk and obtain required approval;
4. create and verify backups before execution;
5. execute only the approved plan;
6. verify the resulting state independently;
7. provide a safe rollback path;
8. produce machine-readable audit records.

The `schemas/` directory defines machine-readable records, while `compliance/tests/` validates required behavior and safety invariants.

## Status

The specifications are currently Draft. Version 0.2.0 is a reference implementation release candidate, not a claim of universal production certification.
