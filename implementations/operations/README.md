# AI-OPS Operations Reference Implementation

This directory implements the operational chain defined by AIS-0004 through AIS-0008:

```text
Planning → Backup → Execution → Verification → Rollback
```

## Safety model

- planning is read-only;
- all filesystem action targets, including `mkdir`, are included in the backup target set;
- backup manifests contain the plan digest, exact target set and verified object digests;
- `execute --apply` is refused when a required manifest is missing, incomplete, altered or belongs to another plan;
- execution is dry-run unless `--apply` is supplied;
- dry-run does not require approval;
- high-risk and critical state changes require `--approved`;
- exact system roots such as `/`, `/etc`, `/usr`, `/var`, `/tmp`, `/home` and `/root` cannot be action targets;
- command actions use argv arrays with `shell=False` and require an explicit `rollback_argv`;
- action contents and full argv values are not copied into execution result descriptors;
- writes through symlinks are refused unless `replace_symlink` is explicitly enabled;
- rollback is dry-run unless `--apply` is supplied;
- rollback verifies the manifest before making any change and verifies restored object digests afterward.

## 1. Create a plan

```bash
python3 implementations/operations/aiops_operations.py plan \
  --discovery discovery-report.json \
  --request examples/operation-request.json \
  --output operation-plan.json
```

Relative target paths are normalized into absolute paths in the generated plan. Manual string preconditions require `--manual-preconditions-confirmed` during apply. Machine-checkable preconditions should use objects such as `exists`, `not_exists`, `writable`, `file_contains`, `sha256` or `command`.

## 2. Create a backup

```bash
python3 implementations/operations/aiops_operations.py backup \
  --plan operation-plan.json \
  --backup-root .aiops-backups
```

The manifest path is printed on success, for example:

```text
.aiops-backups/example-safe-write/backup-manifest.json
```

An existing non-empty backup directory is never overwritten unless `--replace` is explicitly supplied.

## 3. Dry-run execution

```bash
python3 implementations/operations/aiops_operations.py execute \
  --plan operation-plan.json \
  --output execution-report.json
```

Dry-run does not require a manifest or approval and does not evaluate state-changing preconditions.

## 4. Apply a plan

```bash
python3 implementations/operations/aiops_operations.py execute \
  --plan operation-plan.json \
  --manifest .aiops-backups/example-safe-write/backup-manifest.json \
  --apply \
  --output execution-report.json
```

Add `--approved` only when the plan reports `approval_required: true`.

When a plan contains manual string preconditions, also add:

```text
--manual-preconditions-confirmed
```

## 5. Verify

```bash
python3 implementations/operations/aiops_operations.py verify \
  --plan operation-plan.json \
  --output verification-report.json
```

Verification is independent from command success and produces a separate report.

## 6. Preview rollback

```bash
python3 implementations/operations/aiops_operations.py rollback \
  --plan operation-plan.json \
  --manifest .aiops-backups/example-safe-write/backup-manifest.json \
  --output rollback-report.json
```

This validates the plan and manifest but does not restore anything.

## 7. Apply rollback

```bash
python3 implementations/operations/aiops_operations.py rollback \
  --plan operation-plan.json \
  --manifest .aiops-backups/example-safe-write/backup-manifest.json \
  --apply \
  --output rollback-report.json
```

For plans containing command actions, also provide the execution report so only commands that actually completed receive their `rollback_argv`:

```text
--execution-report execution-report.json
```

High-risk rollback also requires `--approved`.

## Supported actions

- `mkdir`
- `write_file`
- `copy_file`
- `delete`
- `command`

Production integrations should still wrap package managers, firewall tools, storage controllers and safety-critical industrial equipment with domain-specific adapters and policy checks.
