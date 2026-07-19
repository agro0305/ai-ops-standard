# AI-OPS Standard Release Checklist

Use this checklist before tagging or deploying a release candidate.

## Repository

- [ ] `VERSION` contains one semantic version.
- [ ] `CHANGELOG.md` contains a section for that version.
- [ ] `python3 scripts/validate_repository.py` passes.
- [ ] `python3 -m compileall -q implementations scripts compliance/tests dashboard` passes.
- [ ] Every `dashboard/install_*.sh` passes `bash -n`.
- [ ] `python3 -m pytest -q compliance/tests` passes.
- [ ] Git working tree contains no generated reports, private state or credentials.

## Release acceptance

```bash
python3 scripts/acceptance.py \
  --project-root . \
  --output acceptance-result.json
```

- [ ] `success` is `true`.
- [ ] Repository validation passed.
- [ ] Python compilation passed.
- [ ] Shell syntax checks passed.
- [ ] Compliance tests passed.
- [ ] Dry-run execution changed no target.
- [ ] Apply execution required and verified a backup manifest.
- [ ] Verification passed.
- [ ] Rollback preview changed no target.
- [ ] Rollback apply restored the initial state.
- [ ] Incident opened, was acknowledged and auto-resolved.

## Runtime deployment

Follow `docs/INSTALLATION.md` in order.

- [ ] `aiops-dashboard.service` is active.
- [ ] `aiops-report-refresh.timer` is active and waiting.
- [ ] `aiops-incidents.timer` is active and waiting.
- [ ] `aiops-notifications.timer` is active and waiting.
- [ ] `aiops-retention.timer` is active and waiting.
- [ ] The latest refresh service exited with status 0.
- [ ] The latest incident service exited with status 0.
- [ ] The latest notification service exited with status 0.
- [ ] `/healthz` returns HTTP 200.
- [ ] `/readyz` returns HTTP 200.
- [ ] Dashboard authentication works over LAN and Tailscale.
- [ ] No service exposes credentials in its journal.

## Runtime health

```bash
python3 scripts/runtime_health.py \
  --project-root . \
  --dashboard-url http://127.0.0.1:8789 \
  --require-services \
  --output runtime-health.json
```

- [ ] `success` is `true`.
- [ ] `summary.fail` is `0`.
- [ ] Required reports are present and fresh.
- [ ] Audit log exists.
- [ ] Dashboard and timers are healthy.

## Security review

- [ ] `/etc/aiops-dashboard.token` mode and ownership are restricted.
- [ ] `/etc/aiops-notifications.env` contains no placeholder credentials when webhook is enabled.
- [ ] Private incident and notification state are absent from dashboard report API.
- [ ] Operation execution refuses missing, incomplete or altered manifests.
- [ ] Exact protected system roots cannot be operation targets.
- [ ] High-risk apply and rollback require explicit approval.
- [ ] Command actions define explicit rollback argv arrays.
- [ ] Retention dry-run was reviewed before policy changes.

## Tagging

Only after all checks pass:

```bash
VERSION="$(cat VERSION)"
git tag -a "v${VERSION}" -m "AI-OPS Standard ${VERSION}"
git push origin "v${VERSION}"
```

Do not tag a release when local acceptance, CI or runtime health is failing.
