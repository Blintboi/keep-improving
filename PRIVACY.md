# Privacy and stored data

Keep Improving is a personal project maintained by [Blintboi](https://github.com/Blintboi). This page describes the application's current data handling. Local tracking works without an account or internet access.

## Local use

Optional opening questions store your custom question/answers in the budget
settings. Accepted choices are recorded locally as budget, action and answer
IDs, member application/domain/game identity, renewal day, visit ID and timestamp so daily allowances survive restarts.
These choice receipts are not included in synchronized usage statistics.

For website opening choices, the extension inserts its own isolated dialog over
the active page using the scripting permission and its existing website access.
It does not inspect or transmit the site's text, form entries or full URL. Only
the domain, browser, random visit token and selected budget/action/answer IDs
are sent through the authenticated loopback connection to the desktop. The page
is not navigated or reloaded when a choice is accepted.

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

**Download and install update** starts only after you click it. The app requests
the fixed official GitHub installer URL with the `KeepImproving/updates-v2` user
agent and verifies its published size and checksum. This request sends no profile,
account or activity data. After verification it closes gracefully, starts the
installer and opens the updated app with your existing profile. Files are staged
under your local application data directory; automatic version checks do not
start this download or installation.

The app reads the foreground process identity and executable path, installed-game metadata and local shortcuts to identify a tracked game. It records daily play time by game, settings, exclusions and game availability in a local SQLite profile. There is no general analytics or advertising telemetry.

The app also records daily time by application executable path,
enabled by default and switchable in Statistics. Only the foreground application
counts, even while reading without keyboard or mouse input; locked desktops and
sleep gaps pause this activity measurement. Input contents are never captured. The app
stores daily aggregates. A local coverage ledger stores already counted time
intervals without application names or domains to prevent duplicate imports.

From version 2.42.0 (Android 0.5.0), a local session ledger also retains the
start/end of connected measured foreground intervals per game, application or
domain. It merges adjacent measurement batches and recovered browser intervals
without counting them again. Session counts are attributed to the starting day;
old aggregate-only history has no reconstructed counts. Optional synchronization
includes encrypted daily session counts and their availability date, without
the local session start/end timestamps.

Website tracking requires manually loading and pairing the included browser
extension. It sends only the focused tab's HTTP(S) domain (or explicitly
configured loopback host and port) and browser family
to an authenticated server bound to `127.0.0.1` on this computer. URL paths,
queries, fragments, page titles and contents are not sent to the desktop app or
recorded in activity history. For a blocked page, the extension can temporarily
keep its original HTTP(S) URL in local extension storage so a browser restart,
daily renewal or one-time allowance can return to the same page. An opaque token
identifies the cover; the address stays in the extension and is never synchronized.
Closing an individual tab removes its recovery record. Window closure retains
records for session restore; stale records are bounded to 1024 entries, excluding live tabs. Private
tabs, unconfigured loopback endpoints and other numeric/private hosts are excluded.
Adding a loopback website to a budget or focus block list opts that endpoint into
tracking. `localhost`, `127.0.0.1` and `[::1]` at the same port share a canonical
`127.0.0.1:port` identity; different ports stay separate. The application's own
authenticated control bridge is excluded. These endpoint identities follow the
same local history and optional encrypted synchronization rules as public domains;
URL paths, queries and page contents are not included. Website time is a breakdown of browser
time. Application/site aggregates are stored in the local SQLite profile and, when computer linking is enabled, synchronize in encrypted snapshots. Completed-round counts and timer state remain local. Focus preferences
and blacklists also synchronize in encrypted snapshots; application rules can contain
  executable paths and may not match paths on another computer. Focus group selections
  stay local because they refer to this computer's time budgets.
The pairing token is Windows-user protected in the desktop profile and stored
in the extension's local browser storage after pairing. It is not a cloud key.

After connecting once, the extension caches the local browser rules and timer
checkpoint. While the desktop application is stopped, it can continue browser
time tracking, Pomodoro and website restrictions. Its bounded local journal
contains interval timestamps, the active domain, timer identifiers and budget
actions, never page contents or full visited URLs. The browser idle permission
detects a locked computer; the notifications permission displays local timer
and budget notices. On reconnection the desktop imports only time it has not
already counted, and acknowledged journal records are removed. Closing the
browser or sleeping the computer does not create guessed usage. Monitoring
other Windows applications and desktop-only reminders requires the desktop app.
The extension has host permissions to redirect blocked sites during focus and
does not contact an internet service. Disabling activity tracking stops new
aggregates; existing local history is retained. Focus restrictions release on
pause, reset, break or loss of the extension's local connection. Protected
game minimization retains the existing permission gate.

When a countdown position editor opens, or you choose to refresh its game image, the app can capture a still image of a recognized running game's client window to help position the countdown. This is not continuous screen recording. The image is held only in memory for the preview, is not saved to disk by the app, and is never included in statistics sync or uploaded to the service. Closing or hiding the editor clears the displayed image.

Automatic anti-cheat compatibility checks inspect game identifiers, executable names and the presence of specific files/folders in game installations. These checks stay local and do not read game memory, account data, process command lines or driver contents. No anti-cheat service or game security setting is disabled.

Protected-game countdowns and notifications are off by default. The Notifications
page has one switch covering all protected games, requiring a separate unchecked
risk acknowledgement before enabling. The notice version and UTC acceptance time
are stored only in this computer's profile. Disabling the switch withdraws active
displays and RTSS preparation; previous game preferences are preserved.

Game-image previews retain their separate per-game permission, bound to the
game ID and installation location. Neither this permission nor the new display
consent is synchronized. Unknown installations, anti-cheat helpers and automatic
Escape remain blocked even after display consent.

Automatic minimization of detected protected games requires an independent,
local risk acknowledgement. Its notice version, UTC acceptance time and
game/install-location hash are stored separately under the same rules; overlay
consent does not grant this permission. Neither kind of consent is synchronized.
Protected-game reminders avoid foreground activation. Where the Windows
notification state cannot support a visual reminder during fullscreen play,
the app uses the selected sound without creating a popup; muted or unavailable
sound leaves delivery pending until a visual reminder can be shown.

The standard profile is in the Windows Documents folder under `GameTimeMonitor\data`. Local artwork is read from installed files and caches and is not uploaded. Application paths in focus blocklists and exclusions are included in encrypted settings synchronization. Upgrade backups stay beside the profile. Local history is not an encrypted database.

Configurable notification rules, triggers, icon paths, button application paths, Pomodoro defaults, closing delays and unfinished notification drafts stay in the local profile and are not synchronized. An application button launches only the selected local executable after a click; it does not run a shell command or launch automatically when the reminder appears. Pomodoro completion goals use local completed-round counts. Notification buttons that start Pomodoros save the chosen focus timing under the existing focus-preference synchronization rules.

Multi-stage restriction plans, delivery markers, one-time allowance usage and
deadlines remain local. Closing applications is separately enabled in each plan;
it first requests a normal close, then may terminate that exact process instance.
Covering uses a separate Windows surface; it does not capture or blur application
pixels. Its short-lived audio helper controls only verified shared-mode audio
sessions of the target process and restores the mute state when released or when
the monitor exits. It does not change system volume or record audio. Protected
processes, Windows components and launchers are not forcibly closed. Website
restrictions navigate or close matching tabs rather than terminating the browser.

The Activities list combines installations of the same executable across versions and linked computers into one entry, including named installers for that application. Website hosts with and without `www.` share an entry; other subdomains remain separate. Historical paths, device attribution and measured time are retained. The list reads application icons from existing local executable files or their Windows application-package logos, and retains a local copy across upgrades. While the Websites list is open, it preloads icons for all listed websites and requests the site's public favicon over HTTPS; if needed, it reads the site's home page to locate its declared icon. The site or its icon host receives a normal asset request, including your IP address, without browser cookies, login credentials or usage totals. No third-party favicon lookup service receives your website list. Scrolling keeps the already loaded icons. Icon requests stop when the list is hidden or the window is minimized. Small icon images and retry timestamps are cached locally, are not synchronized, and can be removed by deleting `cache/activity-icons` inside the profile while the app is closed.

If daily quota reset times differ from midnight, recent quota-period totals are stored separately from calendar-day history. These local per-game totals preserve the current allowance across midnight and restarts, are limited to recent periods, and are not included in statistics synchronization. Alert markers remain local; reset schedules can synchronize.

Optional per-game time limits can synchronize with linked computers. When linking is enabled, the shared game budget and per-game limits also include the other computers' last synchronized daily game statistics. Activity budgets and restriction plans remain local. The last synchronized totals may be stale while offline or rate-limited; all computers need an updated client to count each other's time.

## Optional computer linking

The paired extension's dashboard reads statistics and settings from the authenticated local desktop connection and sends explicit editing commands through it. Application launches, uninstall commands and notification buttons require user actions. Dashboard drafts and navigation choices stay in the browser profile; uploaded notification images are copied into the desktop profile. Browser access does not expose account access/refresh tokens. A connection code is revealed only through its explicit show/copy control. The dashboard uses no remote scripts, fonts or analytics. Hidden dashboard tabs stop refreshing.

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

The Overview remembers view choices and list-search text locally in the profile database. These view preferences are not included in synchronized snapshots.
