# Privacy and stored data

Keep Improving is a personal project maintained by [Blintboi](https://github.com/Blintboi). This page describes the application's current data handling. Local tracking works without an account or internet access.

## Local use

Automatic update checks are enabled by default and can be turned off in
**Settings → Application updates**. At most once per day, the app requests a
small public version file from this project's GitHub repository over HTTPS.
GitHub receives the normal connection information, including your IP address
and the fixed `GameTimeMonitor/updates-v1` user agent. The request does not send
play history, game names/paths, computer names, account/connection credentials,
device identifiers or the installed app version. The latest public release
record, last-attempt time and a dismissed version may be cached locally.
**Check for updates** makes the same request manually, with a short retry guard.
Turning checks off stops future automatic requests; an in-progress request may
finish. Tracking remains available offline.

**Download update** opens the fixed official GitHub installer URL in your normal
browser only after you click it. The browser handles the download and its normal
security checks. The app does not download or install executables in the
background. Installing an update is a separate action you choose. Requests for
the installer and any browser security checks follow the browser/provider's
normal data handling.

The app reads the foreground process identity and executable path, installed-game metadata and local shortcuts to identify a tracked game. It records daily play time by game, settings, exclusions and game availability in a local SQLite profile. There is no general analytics or advertising telemetry.

The app also records daily time by application executable path,
enabled by default and switchable in Statistics. Only the foreground application
counts, even while reading without keyboard or mouse input; locked desktops and
sleep gaps pause this activity measurement. Input contents are never captured. The app
stores daily aggregates, not a chronological activity timeline.

Website tracking requires manually loading and pairing the included browser
extension. It sends only the focused tab's HTTP(S) domain and browser family
to an authenticated server bound to `127.0.0.1` on this computer. URL paths,
queries, fragments, page titles and contents are not sent or stored. Private
tabs and local/numeric hosts are excluded. Website time is a breakdown of browser
time. Application/site aggregates are stored in the local SQLite profile and, when computer linking is enabled, synchronize in encrypted snapshots. Completed-round counts and timer state remain local. Focus preferences
and blacklists also synchronize in encrypted snapshots; application rules can contain
executable paths and may not match paths on another computer.
The pairing token is Windows-user protected in the desktop profile and stored
in the extension's local browser storage after pairing. It is not a cloud key.
The extension has host permissions to redirect blocked sites during focus and
does not contact an internet service. Disabling activity tracking stops new
aggregates; existing local history is retained. Focus restrictions release on
pause, reset, break or loss of the extension's local connection. Protected
game minimization retains the existing permission gate.

When a countdown position editor opens, or you choose to refresh its game image, the app can capture a still image of a recognized running game's client window to help position the countdown. This is not continuous screen recording. The image is held only in memory for the preview, is not saved to disk by the app, and is never included in statistics sync or uploaded to the service. Closing or hiding the editor clears the displayed image.

Automatic anti-cheat compatibility checks inspect game identifiers, executable names and the presence of specific files/folders in game installations. These checks stay local and do not read game memory, account data, process command lines or driver contents. Without explicit per-game risk consent, detected protected games do not provide game-image previews or countdown overlays. No anti-cheat service or game security setting is disabled.

For a detected protected game, you can separately accept the overlay risk notice.
The app stores the notice version, UTC acceptance time and a hash binding the
permission to that game's ID and installation location in the local profile.
These records are not uploaded or included in statistics synchronization.
Permission is saved immediately, can be revoked in Per-game countdowns and must
be accepted again if the notice version or game/install location changes.
Without consent, protected overlays/previews remain blocked. Automatic Escape
remains disabled for protected games even after consent.

Automatic minimization of detected protected games requires an independent,
local risk acknowledgement. Its notice version, UTC acceptance time and
game/install-location hash are stored separately under the same rules; overlay
consent does not grant this permission. Neither kind of consent is synchronized.
Protected-game reminders avoid foreground activation. Where the Windows
notification state cannot support a visual reminder during fullscreen play,
the app uses the selected sound without creating a popup; muted or unavailable
sound leaves delivery pending until a visual reminder can be shown.

The standard profile is in the Windows Documents folder under `GameTimeMonitor\data`. Local artwork is read from installed files and caches and is not uploaded. Application paths in focus blocklists and exclusions are included in encrypted settings synchronization. Upgrade backups stay beside the profile. Local history is not an encrypted database.

If daily quota reset times differ from midnight, recent quota-period totals are stored separately from calendar-day history. These local per-game totals preserve the current allowance across midnight and restarts, are limited to recent periods, and are not included in statistics synchronization. Alert markers remain local; reset schedules can synchronize.

Optional per-game time limits can synchronize with linked computers. They reuse each computer's locally measured foreground time and quota periods.

## Optional computer linking

Synchronization is off by default. When enabled, the app uploads each computer's cumulative daily game times, game names/sources, daily application executable paths and website domains with their measured times, chosen display name and supported settings, including focus lists, application-rule paths and per-game preferences. These contents are encrypted on the client using keys derived from the connection code. Account credentials, computer names as settings, local game folders, monitor selection, custom WAV paths and protected-game consent remain local. The service stores encrypted snapshots, random device identifiers, revisions, timestamps and resource counters. It does not receive the connection code or its encryption key.

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
