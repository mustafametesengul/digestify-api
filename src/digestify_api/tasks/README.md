# Tasks

CouchDB-backed generic tasks with one-time scheduling, fixed-interval or daily
recurrence, bounded retries, and explicitly partitioned asyncio workers. The
public API is exported from `digestify_api.task`. The experiment in `old.py`
is not used or migrated.

## Enqueue and Track

Construct `TaskService(database)` with the existing CouchDB `Database` and call
`await service.init()` before starting producers and workers. This creates the
database and indexes and is safe to repeat. Keep the database's HTTP client open
for the lifetime of the workers, with finite request timeouts. The changes feed
disables its own read timeout.

```python
from datetime import UTC, datetime, time, timedelta

from digestify_api.task import DailySchedule, IntervalSchedule, TaskService

service = TaskService(database)
await service.init()

immediate = await service.create(
    "digest", {"user_id": "user-123"},
    task_id="digest-request-456", partition_key="user-123",
)
scheduled = await service.create(
    "digest", {"user_id": "user-123"}, partition_key="user-123",
    scheduled_at=datetime.now(UTC) + timedelta(hours=1),
)
daily = await service.create(
    "digest", {"user_id": "user-123"}, partition_key="user-123",
    schedule=DailySchedule(time=time(9), timezone="Europe/Istanbul"),
)
periodic = await service.create(
    "refresh", schedule=IntervalSchedule(every=timedelta(minutes=15)),
)

current = await service.get(immediate.id)
user_tasks = await service.find(partition_key="user-123", status="pending")
await service.cancel(daily.id)
```

All timestamps must be timezone-aware; stored timestamps are normalized to UTC
with fixed precision for CouchDB range queries. Without `scheduled_at`, one-time
and interval tasks start immediately; daily tasks start at the next local
occurrence. An explicit `scheduled_at` overrides the first occurrence.

`task_id` is optional. IDs are stored as `task:<task_id>`; use the returned
`task.id` for reads and cancellation. A stable producer ID avoids accidentally
creating multiple documents for one request. Reusing it raises
`DocumentConflict`, not a silent overwrite. A timed-out or unconfirmed create
may have committed: inspect that stable ID before deciding to retry.

`get()` returns `None` for a missing task and refuses visible revision conflicts.
`find()` returns up to 100 tasks by default (configurable with `limit`), with no
guaranteed order. It is a discovery query, not a conflict-checked snapshot.
Tasks retain their latest result/error, timestamps, current occurrence and
attempt count, and successful/failed occurrence totals. There is no per-attempt
history or automatic retention cleanup. Terminal documents remain available.

## Run Workers

Register asynchronous handlers by task kind. Payloads and returned results must
be JSON values; returning `None` is valid. This example logs the work; replace
its body with your application operation.

```python
import logging

from pydantic import JsonValue

from digestify_api.task import Partition, Task, Worker

async def handle_digest(task: Task) -> JsonValue:
    logging.info("Processing %s for %s", task.idempotency_key, task.partition_key)
    return {"processed": True}

worker = Worker(
    service,
    {"digest": handle_digest},
    worker_id="digest-worker-0",
    partition=Partition(index=0, count=2),
    concurrency=10,
)
await worker.run()
```

Run the other process with `Partition(index=1, count=2)`. All workers in this
group must agree on the count, use unique indices, and cover the same task kinds.
Kinds without a registered handler remain pending. `Partition()` owns all work
for a single worker. Multiple workers with the same partition compete for claims
instead of dividing ownership; this can provide availability but increases the
risk of duplicate execution during a partition.

The UTF-8 partition key is SHA-256 hashed into 256 fixed buckets, then bucket
modulo worker count chooses the owner. Set the key to a user ID, tenant ID, or
another stable string. It defaults to the task ID. The assignment is identical
across processes and Python restarts. It groups tasks but does **not** serialize
tasks sharing a key or promise equal load. A worker may own multiple tasks for
the same user concurrently. There is no membership discovery or automatic
failover to an unassigned partition. Replace a failed worker using its index.
For count changes, stop the old group before starting the new group; overlapping
configurations can compete. Existing leases must expire before abandoned work
is reclaimed. Use clock synchronization across machines.

Each worker runs at most `concurrency` handlers and claims only when a slot is
available. It polls every 15 seconds by default; the changes feed wakes it sooner
and reconnects from the last observed sequence. Polling also covers startup
races, missed changes, and expired leases. Scheduled starts can be late by the
poll interval plus query time, replication lag, and queueing; this is not a
real-time scheduler. Queries retrieve all due tasks in owned buckets, so this
simple implementation is intended for moderate backlogs, not unbounded queues.

## Execution Rules

- A claim is a revision-checked document update with a random token, worker ID,
  and expiry. Handlers start only after a confirmed write. Every renewal and
  completion reloads conflict-checked state and verifies the token and expiry.
- The default lease is ten minutes; renewal happens every third of a lease.
  `heartbeat_interval` can be lowered to observe cancellation sooner. Renewals
  time out after one heartbeat interval. On expiry, uncertainty, or lost
  ownership, the worker cancels and awaits its handler.
- Cancellation is permanent for pending/running tasks and idempotent for
  terminal ones. It clears the lease; running handlers notice on their next
  renewal. Cancellation cannot undo effects already sent to another system.
- Cancel `worker.run()` to stop it. It cancels and awaits handlers and its feed
  watcher. Unfinished claims are left to expire, not marked successful. Handlers
  must yield to asyncio, honor cancellation, and not block the event loop.
- Handler exceptions retry after `retry_delay` (30 seconds by default), up to
  `max_attempts` (three starts per occurrence). Crash reclaims count as attempts.
  An expired final attempt is marked failed without running it again.
- A terminal one-time task becomes `succeeded` or `failed`. A recurring task
  advances after success or exhausted retries, preserving the last outcome.
  Fixed intervals stay anchored to the original schedule; missed slots are
  skipped rather than replayed. Daily schedules use local wall time, run the
  first occurrence of ambiguous DST times, and move nonexistent times forward
  by the DST gap. Retries preserve the occurrence's idempotency key.

## Consistency Limits

This is **best-effort duplicate avoidance**, not exactly-once execution or a
distributed lock service. CouchDB revisions reject stale writes on a visible
branch, but replication partitions can allow two branches to accept claims.
Random claim tokens fence stale completion against the state a worker can see;
they are not globally ordered fencing tokens for external systems.

Pass `task.idempotency_key` to a downstream operation that durably enforces
idempotency. It is stable across retries/reclaims and changes for each recurring
occurrence. A handler may finish its external effect and crash before recording
success; the next worker can repeat that effect. Cancellation, heartbeat loss,
clock skew, or blocking code can also overlap executions. There is no guaranteed
delivery: bounded retries, unresolved conflicts, or abandoned partitions can
leave an operation incomplete.

Visible CouchDB `_conflicts` block mutations and execution until an operator
reconciles the task and its external effects. Conflicting branches are never
automatically merged or deleted. A timed-out or HTTP 202 write may still commit;
workers do not treat it as a confirmed claim or completion. Replication conflicts
can later change the visible state, including cancellation and recorded success.
The caller of producer/status APIs receives these persistence exceptions.

## Tests

Run `uv run pytest tests/task -q`. Live tests reuse the CouchDB test settings and
temporary databases; they skip when no server is available. Start the development
database with `docker compose up -d db`. Tests cover visible conflicts and local
revision races, but do not simulate a partitioned multi-node CouchDB cluster.