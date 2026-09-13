# Development

Install dependencies:

```bash
uv sync
```

Format code:

```bash
uv run poe format
```

Check code:

```bash
uv run poe check
```

Run tests:

```bash
uv run poe test
```

## Try The API

Start CouchDB, the API, and a separate worker:

```bash
docker compose --profile api up --build -d db web worker
docker compose logs -f web
```

Swagger is at http://localhost:8000/docs. The Compose configuration is for
local development: it binds ports to localhost, uses development credentials,
and prints email sign-in codes to the web logs. Never expose this configuration
publicly. No AI or email-provider credentials are needed in this mode.

1. Call `/identity/sign-in-with-email` with an email address.
2. Find the six-digit code in the web logs and submit it to
	`/identity/verify-sign-in-code`.
3. Paste the returned `access_token` into Swagger's **Authorize** dialog.
4. Create a topic using `POST /news/create-topic`. For a quick test, choose a UTC time a
	minute or two ahead and timezone `UTC`.
5. After it is due, call `POST /news/list-stories` with `{"topic_id": "..."}`
	in the JSON body and `POST /news/get-usage` without a body.

News endpoints are named POST actions. Use `/news/update-topic` with `topic_id`
and all editable topic fields, or `/news/delete-topic` with only `topic_id`.
See [News](src/digestify_api/news/README.md) for all request shapes.

Access tokens expire after five minutes by default. Use `/identity/refresh-token`
with the refresh token to get a new pair. Anonymous tokens cannot manage topics.

To run from PowerShell instead of Docker (CouchDB is still required):

```powershell
docker compose up -d db
$env:DIGESTIFY_API_SECRET_KEY = 'local-development-only-change-this-secret'
$env:DIGESTIFY_API_EMAIL_BACKEND = 'console'
$env:DIGESTIFY_API_RUN_WORKER = 'true'
uv run digestify-api serve
```

For separate workers, omit `DIGESTIFY_API_RUN_WORKER` and run
`uv run digestify-api worker` in another terminal. Multiple full-range workers
may compete for task leases. For static partitioning, set
`DIGESTIFY_API_WORKER_COUNT` identically and assign each partition a distinct
`DIGESTIFY_API_WORKER_INDEX` from zero to count minus one. Do not mix partition
counts during deployment; see the tasks documentation for membership rules.
`DIGESTIFY_API_WORKER_CONCURRENCY` defaults to 10 user tasks per worker.

Outside local development, configure a strong shared `DIGESTIFY_API_SECRET_KEY`,
`DIGESTIFY_API_EMAIL_BACKEND=resend`, `RESEND_API_KEY`, and `RESEND_FROM_ADDRESS`.
Connection settings are `COUCHDB_URL`, `COUCHDB_USER`, `COUCHDB_PASSWORD`, and
`COUCHDB_DATABASE_PREFIX` (default `digestify`, identical for API and workers).
The separate databases are `digestify-identity`, `digestify-news`, and
`digestify-tasks`. Application startup provisions them through the CouchDB
client before initializing service indexes; services never create databases.
Restrict database access to backend service accounts. Workers do not need JWT
or email secrets. The existing Compose MCP services are unrelated to this mock.

This is a new project: obsolete development data can be discarded. Database
migrations and backward compatibility with earlier storage layouts are not
required.

Live tests use isolated temporary databases and run automatically when CouchDB
is reachable:

```bash
uv run pytest tests/news tests/tasks tests/identity tests/couchdb -q
uv run poe check
```
