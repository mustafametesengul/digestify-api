# Identity

## Construction

`Service` requires repositories for `User` and `SignInCode`, plus the email
client, token generator, and token verifier. The repositories can share a
CouchDB database. Create the database before serving requests. There is no
session repository, refresh-token table, or rotation worker.

```python
from digestify_api.couchdb import Repository
from digestify_api.identity.service import Service
from digestify_api.identity.sign_in_code import SignInCode
from digestify_api.identity.user import User

service = Service(
    users=Repository(User, database),
    sign_in_codes=Repository(SignInCode, database),
    email_sender=email_client,
    token_generator=token_generator,
    token_verifier=token_verifier,
)
```

Configure `app.state.identity_service` and `app.state.identity_token_verifier`
before including the router. Generator and verifier must use matching signing
settings. No backward-compatibility or data-migration layer is included.

## Account Provisioning

Successful code verification reserves a deterministic user ID derived from
the normalized email's document ID and the previous account ID. Replicas with
the same account mapping choose the same next ID. The user is then created,
and the challenge is consumed before tokens are returned. Retries reuse the
reservation. A soft-deleted account is never reactivated: the next sign-in
creates a new account ID so old tokens do not authorize the new account.

This is a recoverable workflow, not a transaction across documents. A database
failure can leave provisioning pending until the next sign-in attempt. If a
failure occurs after the challenge was consumed, the client must request a new
code. Rejected writes (409) trigger bounded verification retries from fresh
state. Accepted but unconfirmed writes (202) do not authorize token issuance;
they may still commit, so clients must not assume that an error rolled back
the operation.

## Tokens and Authorization

Tokens require `exp`, `iat`, `sub`, `role`, `type`, `jti`, `iss`, and `aud`.
Registered-user tokens also require `gen`, the UUID stored as
`User.token_generation`. Both token purposes carry the same account generation.
Access and refresh purposes cannot be interchanged. Defaults are five minutes
for access tokens and 45 days for refresh tokens, configurable through
`DIGESTIFY_API_ACCESS_TOKEN_EXPIRE_MINUTES` and
`DIGESTIFY_API_REFRESH_TOKEN_EXPIRE_DAYS`.

Refresh tokens are reusable until their individual expiry. Refreshing returns
a new pair with a new 45-day window, without database writes or replay
revocation. Monthly use can therefore keep a user signed in indefinitely.
The client must actually refresh and persist the new pair; simply loading a
page does not extend anything. After more than 45 days without refreshing,
the default configuration requires another email sign-in. Concurrent refresh
requests and retries are allowed; either returned pair is usable.

There is no per-device logout or stolen-token replay detection. Clearing local
tokens signs out that client only. A stolen refresh token can also keep
renewing indefinitely until account recovery or deletion invalidates its
generation. Changing the signing key invalidates all signed tokens.
Protect refresh tokens with TLS and platform-secure storage; for a browser,
prefer an HttpOnly, Secure cookie behind a backend with appropriate CSRF
protection. This API currently returns tokens in JSON and does not implement
cookie storage. Do not log credentials, email codes, or token responses.

`require_user` verifies the signature and checks registered-account status and
token generation. Refresh and direct account operations check these too.
`require_registered_user` additionally rejects anonymous identities. Direct
callers of `TokenVerifier.verify()` must call `Service.authorize()` if they
need the account-status and generation checks. Tokens are stateless; registered-user
authorization is not database-free. Database failures return 503 rather than
falling back to token-only authorization. Anonymous identities need no
database record and have no account-level revocation.

## Account Recovery

To recover from a stolen token and sign out all devices:

1. Request a fresh six-digit code through `POST /identity/sign-in-with-email`
    with `{"email": "alice@example.com"}`.
2. Submit it to `POST /identity/recover-account` with
    `{"email": "alice@example.com", "code": "123456"}`.
3. Persist the returned token pair, replacing any locally stored tokens.

Recovery requires email proof, not an access or refresh token. It uses the
same email challenge as normal sign-in, consumes it, then saves a fresh random
account generation before returning replacement tokens. All previous access
and refresh tokens for that account become invalid once the new generation is
visible to their authorization reads. The account ID and data are preserved.
Other accounts are unaffected. Ordinary sign-in and refresh do not change the
generation, so normal use does not sign out other devices. A refresh already
in flight may return an old-generation pair, but cannot upgrade it to the new
generation.

Challenge consumption and generation replacement are separate writes. On a
failure, no tokens are returned; revocation may or may not have committed.
Request a fresh code and repeat recovery if the outcome is uncertain. A normal
sign-in after a failed recovery is not proof that old tokens were revoked.
Concurrent document updates can require another fresh code. Recovery uses the
normal provisioning flow if no active account exists. Registered user records
must contain a persisted generation; there is no migration/default-on-read
for older records or compatibility with tokens lacking `gen`.

## Eventual Consistency

Six-digit codes expire after ten minutes. The five-attempt budget, 60-second
issuance cooldown, and challenge consumption are best-effort across replicas,
not globally strict limits or guaranteed one-time use during partitions.
Keep per-IP and per-address throttling at the API gateway before production;
the document counter alone is not adequate abuse protection for six digits.
Cluster-wide throttling is not implemented here.

Repository reads request conflict metadata and reject visible divergent
revisions. Identity returns 503 for these conflicts and unconfirmed writes.
This prevents an arbitrary winning revision from silently overriding a
revocation or choosing an account owner. It cannot detect conflicts that have
not yet replicated or guarantee a bound on stale authorization during an
outage. Quorums and HTTP acknowledgement checks do not provide global CAS.

Unresolved identity conflicts require operator intervention; this deliberately
small implementation does not automatically merge them. Inspect all leaf
revisions through CouchDB's conflict APIs. Preserve deletion if any user
branch is deleted, invalidate conflicting challenges, and establish account
ownership before resolving divergent mappings. Never simply discard a losing
revocation. For conflicting user generations, store a fresh generation and
require a fresh email sign-in; do not restore either branch's tokens. Resolve
every competing leaf and monitor for further conflicts
after replication catches up. A retry alone will not resolve a stored conflict.

The tests exercise ordinary concurrent writes and explicitly replicated
conflicts against a live CouchDB server. They are not a multi-node partition
or failover certification.

Email delivery uses a finite 10-second read timeout. Delivery failures return
502; the persisted challenge and issuance cooldown remain in place. A later
code request is allowed after the cooldown.