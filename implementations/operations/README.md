# AI-OPS Operations Reference Implementation

This directory implements the initial operational chain defined by AIS-0004 through AIS-0008:

```text
Planning → Backup → Execution → Verification → Rollback
```

## Safety model

- planning is read-only;
- backup copies every declared target before mutation;
- execution is dry-run unless `--apply` is supplied;
- high-risk and critical plans require `--approved`;
- command actions accept argv arrays and never invoke a shell;
- verification is independent from command success;
- rollback restores the backup manifest in reverse order.

## 1. Create a plan

```bash
python3 implementations/operations/aiops_operations.py plan \
  --discovery discovery-report.json \
  --request examples/operation-request.json \
  --output operation-plan.json
```

## 2. Create backup

```bash
python3 implementations/operations/aiops_operations.py backup \
  --plan operation-plan.json \
  --backup-root .aiops-backups
```

## 3. Dry-run execution

```bash
python3 implementations/operations/aiops_operations.py execute \
  --plan operation-plan.json \
  --output execution-report.json
```

## 4. Apply an approved plan

```bash
python3 implementations/operations/aiops_operations.py execute \
  --plan operation-plan.json \
  --apply \
  --approved \
  --output execution-report.json
```

## 5. Verify

```bash
python3 implementations/operations/aiops_operations.py verify \
  --plan operation-plan.json \
  --output verification-report.json
```

## 6. Roll back

```bash
python3 implementations/operations/aiops_operations.py rollback \
  --manifest .aiops-backups/<plan-id>/backup-manifest.json \
  --output rollback-report.json
```

This release intentionally supports a small action set: `mkdir`, `write_file`, `copy_file`, `delete`, and `command`. Production integrations SHOULD wrap privileged service, package, firewall and storage changes with domain-specific adapters and policy checks.
