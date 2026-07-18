# AI-OPS Dashboard

The dashboard is a local-first, read-only-by-default view of AI-OPS inventory, operations and compliance.

## Required views

- Overview
- System Inventory
- AI Capability Registry
- MCP Registry
- Operations
- Backups
- Verification
- Rollback
- Compliance
- Alerts and Audit

## Deployment principles

- Operates on localhost, LAN and Tailscale.
- Does not require public internet exposure.
- Uses authenticated backend APIs for control operations.
- Never treats UI state as source of truth.
- Redacts secrets and sensitive payloads.
- Exposes `/health`, `/ready` and optional `/metrics` endpoints.

## Initial technical direction

A reference implementation may use FastAPI/Pydantic for the backend and a lightweight TypeScript frontend. OpenAPI Generator may generate the frontend client, while Pydantic AI may provide diagnostic and reporting agents. AI control proposals remain subject to deterministic authorization and human approval.