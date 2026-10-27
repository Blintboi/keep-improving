# Security and public operation

## Public update notices

Update checks read a fixed HTTPS GitHub manifest with an 8 KiB response bound,
socket/read deadlines, a strict stable-version/schema parser and no redirects.
Only newer versions are offered. Check cadence and public metadata are cached
locally; failed automatic requests stay in the log. The manifest may contain
only the fixed official installer URL, byte size and SHA-256. These hashes
describe release integrity; they are not an independent publisher signature.
The app never runs a remotely supplied command or automatically downloads or
installs executable code. The download button opens the official URL in the
user's browser, preserving the browser/Windows download checks. A compromised
repository/distribution account remains a distribution risk; HTTPS and a hash
hosted by the same account are not independent proof of authenticity.

The build emits matching Windows version resources and `downloads/latest.json`
from the completed installer. Version resources do not make an unsigned file
trusted. No Windows security setting, antivirus exclusion or trusted-root
certificate is changed. See [Windows trust and signing](docs/WINDOWS-TRUST.hu.md).

## Current launch status

**2.12.0 supports verified GitHub account admission and code-based computer
linking on the existing Supabase Free project.** GitHub OAuth, the native PKCE
round trip, token refresh, session revocation and existing-group ownership have
been checked against the live service. GitHub profile/email access is read-only;
email/password and anonymous sign-in are disabled. Registration is open within
the initial limits below, not unlimited. The repository and installer are public.
This is a personal-use project shared for others who find it useful, with no
promised release schedule or hosted-service availability.

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

Admission limits are 100 active groups, 25 new owners per UTC day,
and three group creations/claims/replacements per owner per UTC month. An Auth
Before User Created hook additionally restricts the provider, reserves at most
25 signup slots per UTC day and 500 total signup slots, before Auth can
allocate unbounded users. Failed signups may conservatively consume a
slot; inspect failures before reconciling slots, never reset them to bypass abuse.
The hook is explicitly activated in the dashboard before opening registration.
Existing users can still sign in when new registrations are paused. A Custom Access Token hook permits only verified GitHub OAuth/refresh with a
live session, caps sessions at ten per user, and token issues at 12/minute and
120/UTC day per user, 1,000/UTC day globally. A denied token issue rolls back
Auth session/refresh-token creation in the same transaction. The usage ledger
has one row per Auth user. Access tokens omit editable metadata. Dashboard IP
limits are 30 token requests, ten verifications and ten signups per five minutes;
these do not protect OAuth /authorize flow allocation by themselves.

Invoker triggers additionally cap account metadata at 32 KiB and the combined
Auth flow_state/oauth_client_states registry at 1,000 rows, each at most 16 KiB.
The combined ceiling covers orphan OAuth-client state created before a rejected
flow insert. Admission serializes on a nonblocking transaction advisory lock;
denied inserts allocate no counter rows. A five-minute cron job removes state
older than one hour, preserves active flows and sessions, and prunes its own run
logs to seven days. These custom triggers attach to provider-managed Auth tables;
recheck their presence, privileges, schema compatibility and real login after a
Supabase Auth upgrade. The limit can deliberately reject new sign-ins during
abuse; existing code-based synchronization and local history remain usable.
Provider logs and upstream resources still have their own limits.

The account endpoint has bounded bodies/deadlines/concurrency and an additional
bounded isolate-local throttle; this is not a distributed WAF. Account management
requires a user JWT, whereas normal encrypted statistics exchanges retain
code-based capability authorization for existing computers. Signing out of
management alone does not revoke a connection code. The server cannot recover
the encryption key for a lost code, even for its verified owner.

The desktop app remains usable offline without cloud registration. Public
distribution was authorized on 2026-10-21. The original source is MIT-licensed;
third-party components retain their own licenses. Cloud admission and resource
limits remain in place for the shared Free service.

## Desktop runtime update in 2.21.2

The Windows bundle uses Qt/PySide6/Shiboken 6.12.0, replacing 6.11.2.
This includes the upstream fixes for
[CVE-2026-95620](https://www.qt.io/blog/security-advisory-cve-2026-95620)
and the later-version fix identified for
[CVE-2026-101201](https://www.qt.io/blog/security-advisory-cve-2026-101201).
The application uses Python's HTTP and JSON libraries rather than the affected
Qt APIs directly; no reachable exploit path was demonstrated in the preceding
review. Both Python bindings are pinned together, Windows wheel hashes are
locked, and matching Qt component notices accompany the replaceable libraries.

The countdown editor can capture a still image of a recognized game's client
window when opened or explicitly refreshed. It keeps the image only in memory
for positioning; it does not save or synchronize it. This behavior is described
in [Privacy](PRIVACY.md).

## What is protected

- Local builds scan current source and the final installer with pinned,
  checksum-verified Gitleaks 8.30.1. The payload audit expands the cabinet, ZIPs
  and PyInstaller PYZ modules, including compiled string constants and UTF-16
  resources. It rejects private profile/database/environment files and provider
  credentials; build-time injection cannot bypass this by avoiding Git. Audit
  reports include locations and rule IDs, never credential values. Reviewed
  upstream Qt parser/format/locale/palette data and one deliberately invalid Auth fixture
  have exact content-hash exceptions; changes invalidate those exceptions.
- The secret-check workflow scans complete Git history and current source on
  pushes and pull requests. It takes effect when that workflow is published;
  local verification does not enable it on GitHub. Local `.env` files and
  private signing containers are ignored by Git. Ignoring a path is a preventive
  convenience, not an access control or a substitute for scanning artifacts.

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
group's statistics and supported settings. Treat it like a password. DPAPI does not defend against malware
running as the same Windows user, administrators, screenshots while revealed, or
a compromised running client. Local history/cache is not an encrypted database.
Remote statistics and computer names cannot execute code or choose local paths.
Synchronized focus rules can contain executable paths and change which foreground
applications are minimized during focus; only share a code with trusted devices.
Protected-game risk consent remains local and is not carried by a snapshot.

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

Keep the 100-group admission ceiling and review actual invocations, Auth traffic,
database size and egress before increasing capacity. Account verification and
signup reservations, Auth-state limits and statistics quotas bound stored app data, not upstream request floods. They do not prove one human per GitHub account. Retired group hashes and
owner quota ledgers are retained so revocation and rotation cannot reset limits.
The total code registry, including retired codes, is capped at 10,000 rows.
Saturated group/device/IP/management counters stop updating tuple versions.
Management has a durable 12/minute per-user throttle in addition to Edge checks.
Normal sync has a bounded isolate-local 60/IP/minute and 240/minute throttle,
plus short rate/quota cooldowns before body reading or database work. These
local guards are performance protection, not a distributed rate limiter.
New objects created by postgres no longer automatically grant public client
table/sequence/function access; migrations explicitly grant the required roles.

Each group has 2 MiB stored ciphertext. Monthly requests per group AND owner are
min(600, floor(350,000/max(25, enabled groups))); monthly response bytes are
min(128 MiB, floor(3 GiB/max(25, enabled groups))). Daily ingress/response caps
are 8 MiB per group and owner. Upload churn has a global 64 MiB/UTC day and
1 GiB/UTC month ceiling; each group AND owner gets monthly upload bytes of
min(64 MiB, floor(1 GiB/max(25, enabled groups))). These count accepted full
payloads, including replacements, not just net stored growth; they limit WAL,
dead tuples and write pressure. The new counters were seeded from retained bytes
at rollout because earlier uploads were not recorded monthly. Global 200 MiB storage, 350,000 exchanges and
4 GiB response ceilings remain. Owner counters survive rotation. The fair share
can shrink as users join; it does not reserve upstream capacity against floods.

The 2.12 client exchanges once at startup, on tracked gameplay start/stop events,
and manually. A one-minute quiet period combines nearby stops. Requests share a
ten-minute guard, persisted locally across restarts and checked independently per
device in PostgreSQL. Pending gameplay events wait for the guard; errors alone do
not schedule retries. Each linked group AND code owner is limited to 20 successful
requests per UTC day and 600 per UTC month, including missing-copy probes. Owner
daily/monthly ledgers survive code rotation; changing device IDs cannot reset them.
The existing service-only core exchange is called only through the limited RPC by
the Edge handler. Public client roles cannot invoke either function directly.

Cloud synchronization requires version 2.12.0 or newer. Requests without the v2
policy header receive HTTP 426 with Retry-After 86400 before body reading, hashing
or database work. The policy header is public protocol negotiation, not identity
or proof of an authentic binary. A caller that imitates it still meets the SQL
guards. Existing codes, encrypted snapshots and cached/local history remain valid.
Rejected traffic still consumes provider invocations; this is not flood protection.

Two computers each starting once a day generate about 60 startup requests per
30 days, plus gameplay events, manual requests and any missing-copy repairs. The
600 monthly cap is a fair-use ceiling, not predicted consumption or measured user
capacity. No increase to the 100-group admission ceiling or paid hosting is made.

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
       auth_signup_day,auth_signups_today,auth_token_day,auth_tokens_today,used_bytes,device_count,month_requests,month_egress
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
repository owner through [GitHub private vulnerability reporting](https://github.com/Blintboi/windows-game-time-monitor/security/advisories/new), not in an issue containing codes, tokens or private statistics. If that form is unavailable, open an issue asking for a private contact without including the vulnerability or any secrets.

Provider references: [Free plan limits](https://supabase.com/pricing),
[Edge authentication](https://supabase.com/docs/guides/functions/auth-headers),
[production auth checklist](https://supabase.com/docs/guides/auth/production-checklist),
[Python runtime security fixes](https://www.python.org/downloads/release/python-31316/),
[official Windows runtime hashes](https://www.python.org/ftp/python/3.13.16/windows-3.13.16.json).
