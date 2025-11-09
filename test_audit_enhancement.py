from main import log_scheduler_audit, ACCU_SCHEDULER_AUDIT
import json

# Clear existing entries for clean test
ACCU_SCHEDULER_AUDIT.clear()

# Test all the new operation names
operations = [
    ('scheduler.schedule.created', {'interval_sec': 300}),
    ('scheduler.schedule.paused', None),
    ('scheduler.schedule.resumed', None),
    ('scheduler.schedule.deleted', None),
    ('scheduler.import.force_run', {'ts_iso': '2025-11-09T04:03:30.737032Z'})
]

for op, meta in operations:
    log_scheduler_audit('test-tenant', op, source='ui', metadata=meta)

print(f'Created {len(ACCU_SCHEDULER_AUDIT)} audit entries')
for i, entry in enumerate(ACCU_SCHEDULER_AUDIT):
    print(f'{i+1}. {entry["operation"]} - source: {entry["source"]}')