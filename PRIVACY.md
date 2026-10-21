# Privacy and stored data

Game Time Monitor is a personal project maintained by [Blintboi](https://github.com/Blintboi). This page describes the application's current data handling. Local tracking works without an account or internet access.

## Local use

The app reads the foreground process identity and executable path, installed-game metadata and local shortcuts to identify a tracked game. It records daily play time by game, settings, exclusions and game availability in a local SQLite profile. It does not record keystrokes, browser history, screenshots or a continuous list of non-game activity. There is no general analytics or advertising telemetry.

The standard profile is in the Windows Documents folder under `GameTimeMonitor\data`. Local artwork is read from installed files and caches; artwork and executable paths are not uploaded by statistics sync. Upgrade backups stay beside the profile. Local history is not an encrypted database.

## Optional computer linking

Synchronization is off by default. When enabled, the app uploads each computer's cumulative daily game times, game names/sources and the computer's chosen display name. These contents are encrypted on the client using keys derived from the connection code. The service stores encrypted snapshots, random device identifiers, revisions, timestamps and resource counters. It does not receive the connection code or its encryption key.

Anyone who has the connection code can access and change that group's shared history. Treat it as a password. Connection codes and Supabase account sessions saved by the client use Windows user-scoped DPAPI. Protection does not extend to malware running as the same user or to all old profile backups.

The shared service runs on Supabase. It can observe request timing, sizes and network information; rate limiting stores keyed hashes for IP-based counters. Supabase also operates its own service and security logs. See [Supabase's privacy policy](https://supabase.com/privacy).

## GitHub sign-in

GitHub sign-in is used to create, replace or revoke a cloud connection code. Supabase Auth receives GitHub account identifiers, profile information and a verified email address. The desktop client discards GitHub provider tokens and protects its Supabase access/refresh session with DPAPI. Joining an existing connection code does not require another GitHub sign-in.

The GitHub account, hosting providers and any GitHub Issues you submit are also subject to [GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement). Keep personal data, connection codes and profile databases out of public issues.

## Retention and deletion

- **Local data:** uninstalling preserves the profile. To remove it, exit the monitor and delete the data folder and any backups you no longer need. Synced copies on other computers and external backups are separate copies.
- **Disable sync:** stops exchanges from that computer; it does not delete already cached or hosted history.
- **Revoke or replace a code:** while signed in as its owner, the app removes the old group's hosted encrypted snapshots. Local history and already downloaded copies on other computers remain. Signing out alone does not revoke code-based sync.
- **Inactive snapshots:** hosted device snapshots expire after 90 days without updates. A returning computer can upload its local history again.
- **Account and abuse records:** Auth identities, retired code hashes and quota/accounting records have separate retention and are not erased by uninstalling or replacing a code. Full service-account erasure requires a maintainer operation that first revokes the group and sessions. Request a private contact through the project if you need this; do not post credentials or account details publicly.

Cloud quotas or outages do not erase local history. For the protocol, operator controls and known limitations, see [Security](SECURITY.md). The hosted service's concise [data-handling page](https://jtvdbqwmejrckjejjrdl.supabase.co/functions/v1/statistics-sync/about) is also available without signing in.
