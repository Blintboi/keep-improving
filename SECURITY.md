# Security and public operation

## Current launch status

**2.9.0 supports controlled, operator-approved synchronization groups. Open,
self-service public registration is disabled.** Existing linked computers keep
working. Generating a new code does not automatically authorize server storage;
an unapproved code produces a clear message and no group/device allocation.
Do not advertise unrestricted public cloud signup in this state.

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
the service. Revoke an exposed group and create/approve a replacement; changing
the client code alone does not revoke the old group's access.

**The Supabase Free plan is not a DDoS or availability guarantee.** Invalid,
rejected and health requests can still consume Edge invocations and provider
resources before database limits apply. The global budget counts successful
exchanges, not every provider invocation. Even an upstream JWT check accepts
public project API keys for compatibility; a public key is not a private WAF key.
An attacker could exhaust the free monthly allowance and interrupt cloud sync.
Neither accounts nor CAPTCHA alone eliminate that risk. No paid upgrade or
automatic billing change is performed by this application.

The current installer is **unsigned**. Its checksum detects corruption/substitution
only when compared with a trusted repository copy; it is not publisher identity
or Authenticode. An independent penetration test has not been performed. Passing
tests and provider advisors are evidence of the checks performed, not a guarantee
that no vulnerability exists.

## Before unrestricted public registration

Configure a real user sign-in provider (for example GitHub OAuth, or verified
email with production SMTP), anti-bot signup protection, account creation limits,
and one admitted group per verified owner. Bind creation/revocation to the verified
server-side identity. Preserve code-based linking and local encryption. Existing
groups need an explicit ownership/recovery migration; possession of a public
group hash must never establish ownership. Anonymous sign-ins or a shipped shared
admin/API secret are not substitutes. This onboarding is not implemented yet.

Set up operator MFA on Supabase and GitHub, restrict project/repository admins,
retain offline backups, monitor provider invocations/egress/database usage and
review abuse reports. Operator MFA and account recovery settings are outside the
desktop application's control and have not been verified by this release.
For stronger availability, a separately protected ingress/rate-limit layer or
appropriate hosting plan is necessary; confirm costs before changing providers.

## Operator controls and recovery

Use the Supabase SQL editor as an authorized project operator; never expose these
controls to the Windows client or grant them to `anon` / `authenticated`.

```sql
-- Pause all cloud exchanges without erasing any statistics.
update public.gametime_sync_budget set enabled=false where singleton;
-- Resume after investigating the incident.
update public.gametime_sync_budget set enabled=true where singleton;
-- Revoke one group using its 64-character server hash (not its connection code).
update public.gametime_sync_groups set enabled=false where group_hash='<hash>';
-- Inspect pressure without reading ciphertext or connection codes.
select enabled,used_bytes,device_count,month_requests,month_egress
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
without copying secrets, approve a replacement through the verified operator,
reconnect affected machines, and investigate how the code escaped. For a server
credential compromise, revoke/rotate it in Supabase and redeploy; do not embed
the replacement in a client release. Report security issues privately to the
repository owner, not in an issue containing codes, tokens or private statistics.

Provider references: [Free plan limits](https://supabase.com/pricing),
[Edge authentication](https://supabase.com/docs/guides/functions/auth-headers),
[production auth checklist](https://supabase.com/docs/guides/auth/production-checklist),
[Python runtime security fixes](https://www.python.org/downloads/release/python-31316/),
[official Windows runtime hashes](https://www.python.org/ftp/python/3.13.16/windows-3.13.16.json).
