# AIS-0003 Discovery Reference Implementation

This directory contains the initial reference implementation of the AIS-0003 Discovery specification.

## Goals

- read-only by default;
- standard-library-only Python 3.10+ core;
- best-effort collection without aborting the complete run;
- machine-readable JSON output;
- no secret values in reports;
- explicit command evidence and collection errors;
- no installation, service restart or configuration change.

## Usage

```bash
python3 implementations/discovery/aiops_discovery.py \
  --output discovery-report.json
```

Compact output:

```bash
python3 implementations/discovery/aiops_discovery.py \
  --compact \
  --output discovery-report.json
```

Selected collectors:

```bash
python3 implementations/discovery/aiops_discovery.py \
  --collect system,network,services,containers,ai
```

## Collected domains

- system identity, OS, kernel, CPU, memory and filesystems;
- network interfaces, routes, listeners, firewall and Tailscale;
- systemd services and timers;
- Docker, Podman and Kubernetes presence/state;
- runtimes and development tools;
- AI coding agents, model gateways and MCP-related processes/config paths;
- Git repository context;
- monitoring, reverse proxy, databases and backup tooling.

## Security

The collector records environment variable names only. It does not record environment values. Command output is redacted for common token, password, authorization and private-key patterns.

The first release is an inventory foundation, not a vulnerability scanner and not a full compliance implementation.
