# News

Topics are private to their owner. Permanent and admin accounts can create up
to five active topics; admins do not get extra quota or cross-account access.
Registered account state and token generation are checked on API calls. Workers
check that the account still exists and is not deleted before calling AI.

## Construction

The news service takes a CouchDB `Client` and task service, with optional
summarizer and clock overrides for testing. It selects the logical `news`
database (`digestify-news` by default), constructs only its own repositories,
and never creates databases. Startup provisions databases through the client:

```python
from digestify_api.news.service import Service as NewsService
from digestify_api.tasks import Service as TaskService

await client.ensure_databases(("identity", "news", "tasks"))
tasks = TaskService(client)
news = NewsService(client, tasks)
await tasks.init()
await news.init()
```

User records belong exclusively to identity's database. News calls identity's
read-only `Accounts` API to check permissions, token generations, and account
deletion; it does not read user documents directly. Task records similarly
belong to the tasks database and are accessed through the task service.
The caller owns the shared client connection. Workers need no email or JWT
secrets. There are no transactions across these separate databases.

## API

The `digestify_api.news` module exposes named use cases, like identity's
sign-in actions. Every endpoint uses POST, with inputs in a JSON body rather
than resource paths or query parameters. Authentication is unchanged.

- `POST /news/create-topic`: create a topic (201).
- `POST /news/list-topics`: list your topics; no body required.
- `POST /news/get-topic`: read your topic using `topic_id`.
- `POST /news/update-topic`: replace all editable details, including the
  schedule, using `topic_id` plus the complete topic details.
- `POST /news/delete-topic`: remove a topic using `topic_id` (204).
- `POST /news/get-usage`: today's consumed reservations and daily limit;
  no body required.
- `POST /news/list-stories`: newest daily batches for `topic_id`, each
  containing up to 20 stories. `limit` is the number of days (1-100, default
  10); `before` is an exclusive ISO date cursor. Both are optional body fields.
  Deleted topics' stories are no longer accessible.

The service has matching `create_topic`, `list_topics`, `get_topic`,
`update_topic`, `delete_topic`, `get_usage`, and `list_stories` methods.
The old `/topics` REST routes have been removed.

Create body (also include `topic_id` when updating):

```json
{
  "name": "Space exploration",
  "description": "Major launches and planetary science discoveries",
  "language": "en-US",
  "schedule": {"time": "09:00:00", "timezone": "Europe/Istanbul"}
}
```

Get/delete body:

```json
{"topic_id": "12345678-1234-5678-1234-567812345678"}
```

List stories body:

```json
{
  "topic_id": "12345678-1234-5678-1234-567812345678",
  "before": "2026-09-13",
  "limit": 10
}
```

Schedules use IANA timezones and local times without offsets. DST gaps shift
forward, folds use the first occurrence. Creation and schedule changes choose
the next future occurrence; edits to other details preserve the deadline.
Workers process one current occurrence after downtime, never a catch-up burst.
Execution is approximate: a per-user recurring task checks every 30 seconds,
plus queue/polling delay. A user's due topics are processed serially; different
users can run concurrently across workers. No AI work runs in HTTP handlers.

## Usage And Failures

The billing day is **UTC**, independent of the editable schedule timezone.
Each of the user's five durable slots may consume one AI attempt per UTC day,
so a topic gets at most one attempt and a user gets at most five. A slot's
consumption survives deletion, replacement, schedule edits, and worker restarts.
A replacement topic may therefore wait until tomorrow despite being due today.
Unused allowance is not carried forward. This is a calendar-day limit, not a
rolling 24-hour limit; attempts on either side of midnight are allowed.

Topic details, all five slots, next deadlines, and consumption dates live in
one `topic_account:{user_id}` document. Revision-checked updates enforce the
limit without counting query results or requiring cross-document transactions.
Reservations never move backwards to an earlier date.

Before calling the async summarizer, the worker confirms its task claim and
durably reserves that slot's daily allowance. A failure, cancellation, timeout,
or crash after reservation consumes the allowance even if no stories result.
Retries skip consumed slots. This deliberately favors bounded AI cost over
guaranteed delivery. A lost lease stops the handler, but cannot undo an external
request already sent. Deletion cannot retract AI work already in flight either.

The mock lives in `summarizer.py`; inject a `Summarizer` into `Service` to replace
it. The callback receives a topic snapshot and a deterministic topic/UTC-date
idempotency key. Pass that key to a provider that supports idempotency, and
disable implicit paid-call retries or make them provider-idempotent. The mock
returns two stories without contacting any AI service. All stories from one
attempt are written atomically in one `story_batch` document. A failed output
write is not recovered by calling the AI again.

## Distributed Operation

Summarization uses task kind `topics.summarize` and deterministic task IDs
`task:topics:{user_id}`. Tasks belong to the tasks database; topic accounts and
story batches belong to the news database. No migration or compatibility layer
for earlier storage layouts is maintained.

The recurring task has a deterministic per-user ID and is confirmed **before**
the first topic is written. If creation stops between these writes, only an
empty recurring task remains; a persisted topic cannot be stranded without its
dispatcher. No task rescheduling or cancellation is needed on topic changes.
Empty/deleted accounts retain their dispatcher and usage document; archival
and story retention are operational policies, not part of this module.

Workers use the tasks module's leases, heartbeats, revision retries, fixed
buckets, and optional static partitions. Use a shared CouchDB cluster with
normal quorum acknowledgments. A 202 response, visible revision conflict, or
uncertain write never authorizes AI work. Query results are not used to grant
quota; authority comes from conflict-checked document reads.

CouchDB is not a globally linearizable quota service. Independent writable
replicas, delayed conflict visibility, or split-brain operation can exceed
these limits temporarily. Provider idempotency protects same-topic/day calls,
but is not a global per-user budget. Do not describe this as exactly-once.
Resolve divergent account documents conservatively: preserve the latest
consumption date per slot, retain at most five topics, and do not reset usage
when merging. Keep clocks synchronized and follow `tasks/README.md` for worker
membership changes. Strict billing across partitions needs a stronger external
coordinator or provider-side budget enforcement.

Only the backend should have CouchDB credentials. End users must not be able
to write quota/task documents directly. This is a per-account limit, not a
defense against a person registering multiple accounts.