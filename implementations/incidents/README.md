# AI-OPS Incident Lifecycle

The reference incident manager converts deterministic dashboard alerts into durable local incidents.

## Lifecycle

- `active` — alert is present and unhandled;
- `acknowledged` — an operator accepted ownership;
- `silenced` — notifications are suppressed until a UTC timestamp;
- `resolved` — manually resolved or automatically resolved when the underlying alert clears.

A resolved incident is reopened automatically when the same alert ID becomes active again. An expired silence returns to `active` during the next sync.

## Safety model

- commands are read-only unless `--apply` is supplied;
- acknowledgement, silence, unsilence and manual resolution require an actor and note;
- every applied transition is appended to `.aiops-audit/events.jsonl`;
- private state is stored in `.aiops-incidents/state.json.private` and is not indexed as a dashboard report;
- the dashboard consumes only `incident-status.json` and remains read-only.

## Synchronize alerts

Preview only:

```bash
python3 implementations/incidents/aiops_incidents.py \
  --root . sync
```

Apply:

```bash
python3 implementations/incidents/aiops_incidents.py \
  --root . sync \
  --actor aiops-incident-sync \
  --apply
```

## Operator transitions

List incidents and copy the required `alert_id`:

```bash
python3 implementations/incidents/aiops_incidents.py --root . list
```

Acknowledge:

```bash
python3 implementations/incidents/aiops_incidents.py \
  --root . acknowledge 'ALERT_ID' \
  --actor agro0305 \
  --note 'I am investigating this incident.' \
  --apply
```

Silence for 60 minutes:

```bash
python3 implementations/incidents/aiops_incidents.py \
  --root . silence 'ALERT_ID' \
  --minutes 60 \
  --actor agro0305 \
  --note 'Maintenance window.' \
  --apply
```

Unsilence or resolve:

```bash
python3 implementations/incidents/aiops_incidents.py \
  --root . unsilence 'ALERT_ID' \
  --actor agro0305 \
  --note 'Maintenance completed.' \
  --apply

python3 implementations/incidents/aiops_incidents.py \
  --root . resolve 'ALERT_ID' \
  --actor agro0305 \
  --note 'Root cause removed and verification passed.' \
  --apply
```

Manual resolution does not hide a persistent condition. The next sync reopens the incident if the underlying alert still exists.
