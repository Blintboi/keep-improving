# Encrypted statistics service

The optional service links a user's own computers. Local tracking, budgets and history work without it. The desktop app uses the existing **Game Monitor** Supabase project on its **Free** plan; users do not need a Supabase account or their own deployment. [Hungarian operator notes](README.hu.md) are also available.

The service consists of PostgreSQL, Supabase Auth and two Edge Functions:

- `statistics-account` verifies a GitHub identity and live session to create, claim, replace or revoke a connection code.
- `statistics-sync` exchanges encrypted snapshots using a code-derived capability. Joining a known code does not require another GitHub sign-in.

The client generates a random 128-bit code and derives separate authentication and AES-256-GCM keys. The server stores an authentication-key hash, device identifiers, encrypted snapshots and accounting metadata. It does not receive the code or encryption key. Each computer uploads its own cumulative daily totals; imported time does not become a new upload or consume another computer's local budget.

Supported preferences are optional fields inside the same encrypted snapshots. They do not introduce another endpoint or sync schedule; older clients continue to exchange statistics and ignore those fields. Local budget consumption, protected-game consent and machine-specific folders remain local.

The hosted endpoint is `https://jtvdbqwmejrckjejjrdl.supabase.co/functions/v1/statistics-sync`. Its `/about` route describes data handling. See [Privacy](../PRIVACY.md) and [Security](../SECURITY.md) for retention, owner controls and known limitations.

## Deployment and operator controls

These instructions describe recovery or a separately operated deployment. They do not change the desktop app's existing service automatically.

1. Inspect the target project's schema and plan before applying anything. The supplied service uses PostgreSQL 17 and the Free plan; the code does not upgrade hosting.
2. Apply **all** files in `supabase/migrations/` in filename order. Statistics tables use RLS with no direct `anon` or `authenticated` access; exchange RPCs require the server role.
3. Configure GitHub OAuth in Supabase with `https://<project>.supabase.co/auth/v1/callback`. Keep the OAuth secret in the provider settings. Disable email/password, anonymous sign-in and identities without a verified email. Allow the native client's `http://127.0.0.1:*/gametime/callback/*` redirect.
4. Activate the `public.gametime_before_user_created` Before User Created hook and the custom access-token hook defined by the migrations. Keep registration closed until the real flow and grants have been verified.
5. Deploy `statistics-sync` with `verify_jwt=false`: it performs its own code-derived authorization. Deploy `statistics-account` with `verify_jwt=true`: management requires a verified session. Both functions use the Supabase server credential only from the function environment.
6. Verify two isolated clients can merge using the same code, a different code cannot access them, direct client-role database access fails, and invalid/oversized/stale writes preserve valid data. Test sign-in, refresh, logout, replacement and revocation. Remove only the synthetic fixtures and reconcile their storage counters.
7. Changing the desktop endpoint requires a rebuilt and verified installer, updated README download and matching source delivery.

Never embed `service_role`, provider admin credentials or OAuth secrets in the desktop client. Its public publishable project key is for Auth, not database administration.

## Shared-service limits

Limits are enforced transactionally in the supplied migrations. They protect storage and fair use; they do not guarantee availability under request floods.

| Resource | Application limit |
| --- | --- |
| Active groups | 100; 25 new owners per UTC day |
| Signup reservations | 25 per UTC day; 500 total |
| Code creation, claim or replacement | 3 per owner per UTC month |
| Devices | 20 per group; 10,000 globally |
| Encrypted device snapshot | 512 KiB; base64 envelope up to 699,052 bytes |
| Stored base64 data | 2 MiB per group; 200 MiB globally |
| Requests per minute | 4 per device; 40 per group; 600 per keyed IP hash |
| Successful exchanges | 20 per UTC day and `min(600, 350,000 / max(25, active groups))` per UTC month, per group AND owner; 350,000 globally per month |
| Device cooldown | Ten minutes between completed exchanges; persistent server check |
| Counted monthly response traffic | `min(128 MiB, 3 GiB / max(25, active groups))` per group; 4 GiB globally |
| Daily upload and response traffic | 8 MiB in each direction per group and owner |
| Global uploads | 64 MiB per UTC day; 1 GiB per UTC month, including overwrites |
| Monthly uploads per group and owner | `min(64 MiB, 1 GiB / max(25, active groups))` |
| HTTP request body | 750,000 bytes; 5-second read deadline; 8 concurrent requests per isolate |
| Inactive device snapshots | Removed after 90 days by hourly maintenance |

The 2.12 client syncs once at startup, on tracked gameplay start/stop events and
manually. One quiet minute coalesces nearby stops; a single-shot event timer waits
for the ten-minute guard or server Retry-After. No periodic network timer or
error-only retry is scheduled. The guard is cached locally and persisted across
restarts/code changes. SQL applies device cooldowns and combined group/owner daily
and monthly quotas transactionally; owner quotas survive rotation. Missing-copy
probes consume request quotas but permit an immediate repair upload.

All linked computers need 2.12.0 or newer. Requests without the v2 policy header
are rejected with 426 before body/SQL work. The public header is not authentication;
imitating it cannot bypass the SQL guards. Encryption, existing codes, local
history and budgets are preserved. Local tracking and cached statistics remain
available offline. A source computer must stay online until its pending upload
completes for its latest time to reach another computer.

Two computers starting once daily generate about 60 startup requests per 30 days,
plus gameplay/manual/repair requests. Provider metering also includes rejected
requests, headers and other project traffic. These are request counts, not
measured capacity or flood resistance; see [current pricing](https://supabase.com/pricing).

Auth hooks and provider-table triggers also bound sessions, token issues, metadata and OAuth state. Their exact limits, upgrade checks and remaining threats are documented in [Security](../SECURITY.md). Failed registrations may reserve capacity. Code rotation preserves owner quotas and retired-code records. Do not reset accounting or erase retired records to bypass limits.

`registration_enabled=false` stops new registrations and group creation; `enabled=false` also stops normal exchanges. Existing users can sign in while new registration is paused. `group_fingerprint.py` is an operator recovery tool, not an end-user setup requirement.

## Validation

From the repository root, with the development environment prepared:

```powershell
.\.venv\Scripts\python.exe -m pip install -r sync_backend/requirements-dev.txt
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_statistics_cloud.py -v
node --test sync_backend/tests/*.test.mjs
```

Unit tests cover encrypted transport and function boundaries. The SQL fixtures under `tests/` exercise actual PostgreSQL grants, identity isolation, quotas, revisions, retention and Auth bounds inside transactions that roll back. They stop on conflicting fixture markers and must never use a real user's connection code. Deployment also needs real OAuth/refresh/logout checks: mocked transport cannot establish provider availability or managed Auth-hook execution.

The existing service passed the checks recorded in [Testing](../TESTING.md). Revalidate custom triggers on Supabase-managed Auth tables after provider upgrades; their presence and permissions are part of the operating assumptions.
