# Security and public operation

## Current launch status

**2.10.0 supports verified GitHub account admission and code-based computer
linking on the existing Supabase Free project.** GitHub OAuth, the native PKCE
round trip, token refresh, session revocation and existing-group ownership have
been checked against the live service. GitHub profile/email access is read-only;
email/password and anonymous sign-in are disabled. Registration is open within
the initial limits below, not unlimited. The repository and installer remain
private; this update does not change distribution visibility.

Native sign-in uses PKCE S256 and a nonce-bearing, ephemeral `127.0.0.1` callback,
allowed only at `http://127.0.0.1:*/gametime/callback/*`. Supabase access/refresh
tokens use Windows user-scoped DPAPI; GitHub provider tokens are discarded. The
GitHub OAuth client secret exists only in Supabase provider configuration. The
Windows client ships only a public publishable project key, which is not an
administrative credential. Local tracking needs no account or network.

Provisioning verifies the Auth user, verified GitHub identity and live
`auth.sessions` row. It never authorizes from user-editable metadata. One account
owns at most one current code; possession of an existing code permits linking,
not taking ownership. A legacy unowned group can be claimed only with its
capability and verified sign-in. Rotation/revocation removes old server
ciphertext and retires that code, retaining local history and owner quota
counters. A pending replacement is DPAPI-protected before the request, allowing
recovery if the dialog/app closes after server acceptance.

Initial admission limits are ten active groups, five new owners per UTC day,
and three group creations/claims/replacements per owner per UTC month. An Auth
Before User Created hook additionally restricts the provider, reserves at most
five signup slots per UTC day and fifty total signup slots, before Auth can
allocate unbounded users. Failed signups may conservatively consume a
slot; inspect failures before reconciling slots, never reset them to bypass abuse.
The hook is explicitly activated in the dashboard before opening registration.
Existing users can still sign in when new registrations are paused. Provider
Auth sessions, OAuth flow state and provider logs have their own lifecycle and
rate controls; the application quotas do not bound every provider resource.

The account endpoint has bounded bodies/deadlines/concurrency and an additional
bounded isolate-local throttle; this is not a distributed WAF. Account management
requires a user JWT, whereas normal encrypted statistics exchanges retain
code-based capability authorization for existing computers. Signing out of
management alone does not revoke a connection code. The server cannot recover
the encryption key for a lost code, even for its verified owner.

The desktop app remains usable offline without cloud registration. The repository
and installer remain private. Public distribution requires a separate release
decision; this update does not change repository visibility.

## What is protected

- A random 128-bit connection code derives independent authorization and
  AES-256-GCM encryption keys. HTTPS carries encrypted statistics; the server
  stores a hash of the authorization key, random device IDs, revisions, ciphertext,
  byte/request counters and timestamps. It cannot decrypt game/computer names or
  daily times. Encrypted payloads bind the device ID and revision as authenticated
  data. Imported totals never become a local daily budget or a new local export.
- RLS and explicit grants deny `anon` and `authenticated` all statistics tables
  and RPCs. Only the server credential may exchange data. Admission is checked
  before storage allocation; caller-supplied group IDs are not accepted. Server
  credentials are read from Supabase environment variables, never from the app.
- Strict request formats, canonical ciphertext envelopes, bounded upload streams,
  timeouts, bounded per-isolate concurrency, transactional storage/request/egress
  quotas and one lock order limit resource use. Revisions cannot roll back data.
  Responses disable caching. Errors contain no database messages or credentials.
- The Windows connection code is saved using **user-scoped DPAPI**. Cache routing
  labels contain a domain-separated hash, not another copy of the code. Existing
  local profiles migrate without changing their code, device identity or history;
  SQLite secure deletion and a WAL checkpoint remove superseded active records.
  A credential that cannot decrypt on another Windows account disables cloud sync
  and asks for the original code; it is not silently replaced. Unrelated settings
  changes retain the unavailable encrypted credential.
- Codes remain masked by default. Redirects cannot receive the authorization
  header. Clients cap response size and decompression, use network deadlines,
  honor bounded `Retry-After`, and back off with jitter after failed exchanges.
  A server outage/quota does not erase local measurements or the last good cache.
- Release builds require patched CPython 3.13.16 and OpenSSL 3.5.9 or newer.
  The Python distribution was checked against its official release-manifest
  SHA-256 before use. Windows x64 / CPython 3.13 dependency locks contain official PyPI wheel SHA-256
  digests. CI actions use immutable commits and read-only repository permissions.
  The installer has an integrity manifest and published SHA-256 checksum.

## Limits and remaining threats

The code is a bearer secret: anyone who obtains it can read and falsify that
group's statistics. Treat it like a password. DPAPI does not defend against malware
running as the same Windows user, administrators, screenshots while revealed, or
a compromised running client. Local history/cache is not an encrypted database.
No remote statistics or computer name may execute code or select local paths.

Old upgrade backups can still contain the previously plaintext code. Keep backups
private and encrypted when sharing/storing them. The app preserves those backups
for recovery; it cannot promise forensic erasure on SSDs, cloud backups or file
history. Moving a profile to a new Windows account requires re-entering its code.
An owner who loses all copies of a code cannot recover its encryption key from
the service. Revoke an exposed group and create a replacement while signed in; changing
the client code alone does not revoke the old group's access.

**The Supabase Free plan is not a DDoS or availability guarantee.** Invalid,
rejected and health requests can still consume Edge invocations and provider
resources before database limits apply. The global budget counts successful
exchanges, not every provider invocation. Even an upstream JWT check accepts
public project API keys for compatibility; a public key is not a private WAF key.
An attacker could exhaust the free monthly allowance and interrupt cloud sync.
Neither accounts nor CAPTCHA alone eliminate that risk. No paid upgrade or
automatic billing change is performed by this application.

The provider advisor reports [leaked-password protection disabled](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
That feature requires a paid plan. This project uses GitHub only and has the
email/password provider disabled; it does not accept Supabase password sign-in.
Do not enable that provider without its own production security review.

The current installer is **unsigned**. Its checksum detects corruption/substitution
only when compared with a trusted repository copy; it is not publisher identity
or Authenticode. An independent penetration test has not been performed. Passing
tests and provider advisors are evidence of the checks performed, not a guarantee
that no vulnerability exists.

## Before a broader public rollout

Keep the initial ten-group ceiling and review actual invocations, Auth traffic,
database size and egress before increasing capacity. Account verification and
signup reservations limit stored users and statistics, not upstream request
floods. They do not prove one human per GitHub account. Retired group hashes and
owner quota ledgers are retained so revocation and rotation cannot reset limits.

Set up operator MFA on Supabase and GitHub, restrict project/repository admins,
retain offline backups, monitor provider invocations/egress/database usage and
review abuse reports. A full Auth-user erasure requires first revoking the owned
group and sessions, then removing the account ledger and Auth user as an operator
in one reviewed transaction. Do not delete the Auth user first or reset quotas
as a self-service workaround; owner foreign keys deliberately prevent orphaning.
Operator MFA and account recovery settings are outside the
desktop application's control and have not been verified by this release.
For stronger availability, a separately protected ingress/rate-limit layer or
appropriate hosting plan is necessary; confirm costs before changing providers.

## Operator controls and recovery

Use the Supabase SQL editor as an authorized project operator; never expose these
controls to the Windows client or grant them to `anon` / `authenticated`.

```sql
-- Pause all cloud exchanges without erasing any statistics.
update public.gametime_sync_budget set enabled=false where singleton;
-- Pause new Auth registrations and group creation, preserving existing sync.
update public.gametime_sync_budget set registration_enabled=false where singleton;
-- Resume after investigating the incident.
update public.gametime_sync_budget set enabled=true where singleton;
-- Revoke one group using its 64-character server hash (not its connection code).
update public.gametime_sync_groups set enabled=false where group_hash='<hash>';
-- Inspect pressure without reading ciphertext or connection codes.
select enabled,registration_enabled,account_limit,auth_signup_total,
       auth_signup_day,auth_signups_today,used_bytes,device_count,month_requests,month_egress
from public.gametime_sync_budget;
select count(*) as groups, count(*) filter(where enabled) as enabled_groups
from public.gametime_sync_groups;
```

The Edge admission cache lasts at most 15 seconds; the database rechecks admission
and the kill switch on every exchange. In an active request flood, deactivate the
Edge deployment at the provider as well: the database switch cannot prevent Edge
invocation consumption. Retention is an hourly database-local `pg_cron` job;
it removes up to 1,000 ciphertext snapshots inactive for 90 days and prunes its
own run history to seven days. It does not delete local history, cached remote
history or admitted group credentials; a returning computer can reupload its
full local snapshot. Check `cron.job_run_details` for failures. Do not reset quotas
or counters to work around abuse. Back up ciphertext, admitted groups and exact
quota counters together; restore and validate accounting in one transaction.

For a suspected leak: revoke the affected group, retain relevant provider logs
without copying secrets, replace the code through its verified owner,
reconnect affected machines, and investigate how the code escaped. For a server
credential compromise, revoke/rotate it in Supabase and redeploy; do not embed
the replacement in a client release. Report security issues privately to the
repository owner, not in an issue containing codes, tokens or private statistics.

Provider references: [Free plan limits](https://supabase.com/pricing),
[Edge authentication](https://supabase.com/docs/guides/functions/auth-headers),
[production auth checklist](https://supabase.com/docs/guides/auth/production-checklist),
[Python runtime security fixes](https://www.python.org/downloads/release/python-31316/),
[official Windows runtime hashes](https://www.python.org/ftp/python/3.13.16/windows-3.13.16.json).
