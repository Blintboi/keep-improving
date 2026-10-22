# Architecture

Additional publisher support lives in `launcher_defs.py`, `platforms.py` and
`battlenet.py`. Client identities are shared by the launcher page, Hub shortcut
collection and foreground exclusions. EA, GOG, Battle.net and Rockstar use
installation registrations in user/machine and 32/64-bit registry views.
Battle.net also reads a bounded subset of its local Agent protobuf index;
Amazon's installation database is opened read-only and closed after each scan.
Only installed records with existing dedicated local directories become games.
Registry notifications and narrowly scoped directory watches trigger debounced
discovery; these sources add no periodic disk scans or network requests.
Previously measured folder/manual games and reidentified publisher entries
retain their usage, rules, hidden state and exclusions when their exact root
becomes a recognized publisher game. Existing Steam/Epic/etc. roots take
priority over duplicate publisher registrations.

Xbox discovery reads current-user package registrations and bounded manifests.
GDK configuration or Xbox Live declarations distinguish games from ordinary
Store apps. Package roots are resolved to their physical installation location;
launches use the registered application identity. Only an installed
`Microsoft.GamingApp` package creates the packaged Xbox client entry. Provider
arguments are structured argv, with proper Windows quoting when creating Hub
links. EA/Amazon URLs are reconstructed as launch-only operations; GOG can use
its bounded local primary play task without Galaxy. Publisher removals open
Windows Installed apps and retain publisher/Windows confirmation.

Installation format references: [MicrosoftGame.config](https://learn.microsoft.com/en-us/gaming/gdk/docs/features/common/game-config/microsoftgameconfig-overview),
[Battle.net index schema](https://github.com/overtools/TACTLib/blob/master/TACTLib/Agent/Protobuf/ProtoDatabase.cs),
and the independently implemented local registration/launch formats documented
by the [Playnite library integrations](https://github.com/JosefNemec/PlayniteExtensions/tree/master/source/Libraries).
Clients not present on this development machine are covered with synthetic
registry, package, protobuf, SQLite and launch-boundary fixtures; compatibility
with every protected game or publisher build is not implied.

The local bedtime schedule (`bedtime.py`) shares the existing one-second monitor
tick; it adds no resident process, fast timer, network request or catalog scan.
Reminder/bedtime/resume times form a validated daily interval across midnight.
Delivery markers use the existing alert store and a cached per-cycle ledger.
Sleep, lock and clock discontinuities suppress missed reminders and reset the
ten-awake-second minimization grace. Bedtime is independent of game budgets and
exclusions. Its direct popup and guarded foreground minimization never inject
Escape; the app's own windows and desktop/taskbars are excluded so settings stay
accessible. Only the canonical user profile attempts one-time migration of the
known SID/marker/action-matched legacy reminder task, backing up its XML and
persisting the integrated setting before disabling it. Other profiles never
touch that task.

The app combines a Qt Widgets interface (PySide6 Essentials) with the existing standard-library tracker and native Windows APIs. QApplication owns UI state on its main thread. Workers communicate through queues; the native tray callback must never invoke widgets directly. CLI diagnostics/configuration commands do not import Qt.

The one-second tracker continues while the Hub is hidden/minimized, including alerts, restrictions, discovery/Hub result handling and tray totals. Its Qt render hook skips library queries and widget refreshes in that state; show/restore events refresh the current view immediately. Hidden statistics and launcher pages do not run periodic presentation refreshes. Worker result polling uses 100 ms only while artwork, client discovery or sync is pending, otherwise 1000 ms; the existing synchronization interval is unchanged. The 200 ms countdown timer starts for tracked gameplay/preview and stops while idle or disabled; the tracker detects gameplay start. RTSS clears once on hide, then its condition variable sleeps until resumed or stopped, preserving active receipt refreshes. Unchanged tray tooltips and budget-ring values cause no native update/repaint. Explicit shutdown signals QApplication directly instead of a separate 100 ms exit-poll timer.

| Module | Responsibility |
| --- | --- |
| `main.py` | CLI, per-profile mutex, logging, diagnostics and lifecycle; frozen builds separate writable data from program files. |
| `model.py` | Stable IDs, path matching, helper blocking, exact EXE rules and tracking policy. Legacy internal `Kézi` source values display as Manual. |
| `store.py` | SQLite WAL, configuration/history, overrides, visibility and discovery merges. Schema v2 adds `game_preferences` idempotently. |
| `discovery.py`, `ubisoft.py`, `riot.py`, `minecraft.py` | Local metadata readers; only successful scans retire installations. |
| `service.py` | Debounced file/registry watches, retries and repair scans. |
| `tracker.py` | Foreground intervals, shared daily totals, late classification, checkpointing and threshold/process-session alerts. |
| `win32.py` | Native process/session identity, file/registry watches, queued tray events, instance mutex and guarded Escape/topmost behavior. |
| `hub.py`, `hub_links.ps1` | Shortcut planning/COM, root ownership, locking, hashes and safe retirement of unchanged owned links. |
| `launch.py` | Read-only launch preparation on a lazy worker, canonical game-launch URIs, preserved shortcut arguments and explicit EXE choices; execution follows Play on the GUI thread. |
| `qt_ui.py`, `qt_widgets.py` | Default Qt library/settings, responsive painted cards, local artwork, independent alerts/removal dialogs and lifecycle. |
| `clients.py` | Background installed-client discovery and explicit, revalidated executable-only client opening, independent of game budgets. |
| `artwork.py` | Bounded local asset lookup and thumbnail decoding on a worker; no widget/pixmap, game execution or archive extraction. |
| `controller.py` | Shared UI-neutral tracking/discovery/tray/launch actions; all callbacks use the GUI scheduler. |
| `overlay.py` | Unparented, translucent, non-activating countdown and the Hub's draggable position editor. |
| `ui.py`, `statistics_ui.py` | Retained Tk regression fixtures; not imported by the production entry point or collected into the binary. |
| `i18n.py` | English/Hungarian presentation catalog; language is a saved setting and never changes IDs or paths. |
| `statistics.py`, `qt_statistics.py` | Inclusive date-range history summaries, zero days, daily chart, drilldown and per-game shares. All recorded rows remain eligible, regardless of current visibility or installation state. |
| `removal.py` | Side-effect-free removal plans and explicitly confirmed execution; no raw registry command execution or direct game deletion. |
| `packaging/` | Frozen runtime build, per-user bootstrap and owned-file uninstaller. |

Visibility is a stable-ID preference, independent of tracking and Hub eligibility. Manual/pending entries becoming launcher entries migrate history, rules, overrides and visibility. Removed entries with today's history remain viewable unless hidden.

Popup alerts are marked delivered only after they become visible. Its independent window avoids minimized-parent withdrawal. Foreground identity guards Escape; failed presentations remain queued. Explicitly suppressed warning/expiry alerts are persisted without Escape, sound or a dialog. Game exclusions use saved per-game or exact-executable preferences. Upgrades preserve user thresholds and Hub location.

Only during interactive account sign-in, an ephemeral loopback callback listens on 127.0.0.1. There is no persistent local server, administrator service or kernel hook. Optional multi-PC statistics exchange uses the encrypted relay. The default desktop overlay does not inject into games. The optional, separately installed RTSS component provides its own in-game rendering for tracked foreground games. Unknown standalone games outside known roots require explicit assignment rather than a whole-drive EXE scan.

`statistics_sync.py` keeps imported daily measurements in separate SQLite tables keyed by connection group and computer UUID. Tracking, alert thresholds, restrictions and overlay totals continue to read only `usage`. Each computer exports only its local history as a complete versioned snapshot, never imported data. A newer snapshot transactionally replaces that computer's prior rows; repeated or stale revisions are ignored. Launcher IDs remain stable across computers, and manual/standalone titles use a normalized source/title key. The statistics page can select local, all linked or one remote computer and uses the selected computers' earliest monitoring date for averages.

`statistics_cloud.py` exchanges compressed AES-256-GCM snapshots over HTTPS with the Supabase Edge Function in `sync_backend`. A random 128-bit connection code derives separate encryption and authorization keys with domain-separated HMAC-SHA-256; only the authorization key is transmitted. The server selects a group using its SHA-256 hash, stores opaque ciphertext, and has no code/encryption key. Per-device revisions are decimal strings on the wire to retain 64-bit precision in JavaScript. Unchanged snapshots are not reuploaded and known remote revisions are omitted. Only the GUI thread prepares snapshots or applies queue results to SQLite; network I/O and authenticated bounded decompression run in a daemon worker. Invalid responses retain the cache, redirects are refused, configuration generations discard retired results, and shutdown has a bounded join. Protocol v2 runs once at startup and on tracked foreground gameplay transitions, plus manual requests. A one-shot timer combines nearby game stops after 60 quiet seconds and waits out a shared ten-minute per-computer guard or server Retry-After. The guard is cached in memory and persisted in SQLite across restarts/code changes; there is no periodic network timer or automatic error retry. Ciphertext format and associated data remain v1 so existing codes/caches remain compatible. Exported content excludes executable paths, rules, launch metadata and settings. Legacy folder codes remain usable only for cached history and require a new opt-in internet code. SQLite is always local.

The Supabase database denies `anon` and `authenticated` all six app tables and management/exchange RPCs. Invoker functions use explicit server/Auth-only grants. The Auth signup hook has only `supabase_auth_admin` execution and narrow budget-column grants/RLS policies; it reserves at most 25 signup slots/day and 500 total before allocating new Auth users. Token/session and Auth-state guards are described below; upstream provider logs and invocations remain separately limited. `statistics-account` requires a JWT, verifies Auth /user, verified GitHub identity and a live session row, then hashes the submitted capability. It admits one current group per owner, 100 active groups overall, 25 new owners/day and three creations/claims/rotations per owner/month. Existing capability holders can link but cannot take over another account's ownership. Rotation/revocation retires old codes and removes only their server ciphertext, retaining owner quotas and local history.

The lock order is budget → owner (if any) → group → device, with a two-second timeout. Monotonic snapshots, device/group/IP throttles, global/group/owner storage and monthly/daily request/traffic budgets, bounded response pagination and a kill switch limit resource consumption. Hourly pg_cron maintenance retires 90-day inactive server copies. Service-role credentials and the GitHub OAuth client secret stay server-side; the Windows app contains only a public publishable Auth key. Rejected requests still consume provider resources, so Free hosting is not a DDoS availability guarantee. See `SECURITY.md`.

`statistics_auth.py` performs native PKCE S256 in a lazily started blocking-queue worker. Its random loopback callback validates Host, path and absent Origin, has a finite lifetime and never reflects codes/errors into HTML. Token responses are whitelisted, discarding GitHub provider tokens. The GUI alone persists DPAPI-protected sessions and pending replacement codes, including refreshed tokens when the following management request fails or its dialog has closed. `qt_account.py` requires sign-in for generated codes, confirms destructive rotation/revocation, retains code-only linking and merges only sync settings after asynchronous completion. Account management uses the existing one-second result timer and does no idle background refresh.


`secrets.py` protects the persisted connection code with user-scoped Windows DPAPI. `Store` unwraps it only for the in-memory settings, reuses unchanged ciphertext and preserves an unreadable encrypted credential while disabling sync. `StatisticsData` migrates plain group routing labels and snapshot-state keys to domain-separated hashes, preserving higher revisions and cached rows. Secure SQLite deletion and a checkpoint retire active plaintext records; historical upgrade backups are deliberately preserved and remain confidential. `CloudSyncWorker` honors bounded server retry hints, applies exponential backoff with jitter, caps response/decompression work, refuses redirects and sleeps on its queue while idle.

The first page is the integrated Gaming Hub; search and source filters affect presentation only. Play does not depend on optional shortcut-folder synchronization or tracking exclusions. `settings` rows named `launch_exe:<game ID>` store explicit executable choices, validated against the exact tracking rule. Rule removal/reassignment clears a stale choice; discovery merges transfer it transactionally. The launch worker never invokes widgets, SQLite or game execution, and closing the app cancels preparation. Launch requests are executed by the GUI thread after rechecking installation state. Protocol links are canonicalized to launch actions; original `.lnk` arguments are preserved and file hashes are rechecked before opening. The `--hub` entry point requests `show-hub.request` when another instance owns the profile, returning to the Library page in that instance. Setup migrates the former folder shortcut and removes only the old owned duplicate monitor desktop shortcut. A redirected desktop folder supports isolated installation tests.

Language switching rebuilds the main widgets on the GUI thread and finalizes retired Tcl variables there. It preserves the current statistics dates and does not restart tracking. The visible statistics page flushes pending measurements before querying SQLite at most about every 10 seconds. Historical days use the same local date keys already recorded by the tracker. Averages use the intersection of the selected range with the profile's installation day through today, including zero-activity days. `settings.tracking_started_on` is stored separately from the user configuration and preserved on upgrade. Legacy profiles use the earlier available filesystem creation day or first recorded usage; restored earlier history can move the marker backwards. The installer stores the Hub shortcut icon in retained user data rather than relying on a program file that disappears during uninstall.

Qt notifications are unparented topmost dialogs, avoiding hidden/minimized parent suppression. They use the existing guarded Escape and native foreground presentation, and remain queued if presentation fails. Qt timers service the tracker and dispatch native tray events without toggling an already-open window. Local artwork loading is staggered; Qt pixmaps and shell icons are created only on the GUI thread. Cards retain their colored background and use a shared 156-pixel rounded tile with a 144-pixel image area. Icons are fitted completely without distortion; suitable cover images use a centered square crop. Covers take priority over incidental installation icons, while small or extreme-aspect posters can fall back to a native icon. A transparent accessible button covers the image area and launches on a single click; its play cue appears on hover or keyboard focus. The options button is beside the title in the footer. Double clicks do not issue a second launch, and the existing busy/restriction checks disable the image button. Source labels, filtering and sorting do not change catalog IDs or measurement policy.

The Windows packager isolates its process PATH while freezing, avoiding dependencies from unrelated developer tools. `-FreezeOnly` supports validating the actual GUI before producing Setup. Windows ICU remains an OS dependency. Upgrades back up and remove unchanged obsolete files listed in the previous payload; changed obsolete executable/runtime files cause a clear failure and remain preserved. All retired paths and backup destinations are checked against their roots, and reparse points are rejected.

Native shell icon pixmaps are normalized to device pixel ratio 1 before logical card/selection sizing; some Windows shell icons otherwise carry a size-dependent DPR that would shrink them when painted. Image and icon aspect ratios remain unchanged.

Both initial artwork and asynchronous results use the same native-icon normalization: crop the transparent mask bounds, then reset DPR before card sizing. The launcher page uses it too. This avoids a small mark inside a much larger shell bitmap being scaled into an unreadable dot after a worker update.

The launcher page is separate from the tracked-game library. A lazy client worker reads shortcut targets and known installation records; only recognized client basenames with no game-specific shortcut arguments become entries. Explicit opening revalidates a local absolute EXE and uses an argv list with shell=False and no extra flags. Client access remains available under play restriction; actual game launches remain subject to the tracker policy. The worker closes its own PowerShell bridge when the Hub exits; failures retain the previous client snapshot and show a refresh message.

Local artwork searches run on one worker, with per-game limits of 80 folders, depth four, 6000 entries and a 750 ms search budget. Whole-drive roots, reparse points and personal save/screenshot/log/mod folders are excluded. Candidates are ranked by product-specific Steam cache association or artwork filename; arbitrary hashed cache images are accepted only inside that exact Steam app's folder. `steam_appid.txt` is read only as a bounded numeric ID. Minecraft supports the fixed `pack.png` icon and title-logo entries in existing version JARs; file/central-directory/entry limits precede decoding and no archive entry is extracted. Other packed game formats are not parsed. Game EXEs are inspected for icons, never executed by artwork discovery, and bootstrapper/helper icons are avoided. Results are QImages transferred by queues; QPixmap creation, native shell icons and card updates stay on the GUI thread. [QImageReader](https://doc.qt.io/qt-6/qimagereader.html) is reentrant and supports scaled decoding; the worker uses a 64 MiB allocation limit, a 20 MiB ordinary-file limit, a 32-million-pixel dimension limit and 640×420 aspect-preserving thumbnails, downscaling only and retaining the native resolution of small images. Tokens/generations discard retired results on refresh or rule changes. Refresh invalidates both successful and missing-art caches; shutdown cancels the bounded worker.

The optional countdown is a separate Qt Tool window with translucent background, WindowTransparentForInput, WindowDoesNotAcceptFocus and ShowWithoutActivating. Native WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_NOACTIVATE and WS_EX_TOOLWINDOW are checked before presentation. ShowWindow(SW_SHOWNOACTIVATE) and SetWindowPos(SWP_NOACTIVATE) maintain visibility/topmost order without foreground activation. Windows documents mouse pass-through for [transparent layered windows](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#layered-windows). No game hooks, injection, global input handlers or game-process modifications are used. Exclusive fullscreen can occlude desktop windows; the renderer does not force a game out of fullscreen.

A 200 ms GUI timer rechecks the interactive desktop, exact foreground process identity and catalog tracking policy before showing the countdown. It hides outside tracked gameplay, including Alt-Tab/lock/exclusions, independently of Hub visibility. The display interpolates at most 1.5 seconds beyond the last tracker sample; only the existing tracker writes usage. The shared daily total determines the remaining time and warning color. Renderer errors restore early warning popups. A ten-second settings preview uses unsaved placement/opacity without crediting time or changing alert markers. Only the miniature inside Settings accepts dragging/arrow keys; the real HUD always passes input through. Monitor choice uses native device names mapped to Qt logical screen geometries; the desktop overlay and miniature both use the full screen geometry rather than the taskbar-reduced work area. Normalized placement survives DPI/resolution changes, with primary-screen fallback when a selected screen disconnects. New/legacy profiles leave the overlay off until enabled; expiry popups remain independently configurable.

Optional play restriction uses the existing tracker total and an independent persisted threshold (default 7500 seconds, disabled until enabled). The one-second tracker tick first requires a ten-second foreground grace, then gates guarded Escape and schedules exact-process minimization after 200 ms. Grace state includes date, normalized path, process creation identity and the previous sample; focus loss, lock, a sample gap over three awake seconds or wall/awake divergence resets it. No input is sent during grace. Before minimization, configuration, date, interactive foreground identity/path and current catalog inclusion are rechecked; native code rechecks PID creation time and window focus immediately before ShowWindowAsync(SW_MINIMIZE). [ShowWindowAsync](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindowasync) posts the window-state request without waiting on a hung game. Completion clears the grace even if minimization fails, so every return/retry allows a fresh full ten seconds. Escape is not repeatedly sent to the same process/day in that resident session. Launch preparation and final execution both reject tracked games while restricted. The Hub exposes a persistent banner and always-accessible Settings; no process termination/suspension, global input lock, Windows lock or admin elevation is involved. Exclusions are honored, hidden games remain tracked, and midnight naturally resets the daily policy. Queued reminders are silently acknowledged once restriction is reached, avoiding conflicting popups. The feature is voluntary and does not guarantee that online gameplay pauses or that elevated/protected apps accept minimization.


Optional RTSS: `rtss.py` owns a single background worker and a pipe-connected `rtss_bridge.exe` child. The helper is built from `rtss_bridge.cs` using the Windows .NET Framework 4 compiler; no compiler or SDK is downloaded. It opens only an existing RTSSSharedMemoryV2 mapping, validates signature/version/array bounds/alignment/overlap, and uses CLR Interlocked on the SDK busy field. Slot zero, foreign slots, unknown fields and foreign locks are preserved. Own text/ownership are cleared on hide, lock, disable, normal exit and parent-pipe EOF. The helper never opens or terminates a game process. No SQLite access occurs in either worker. A stalled helper receipt expires, so it cannot suppress an early warning.

Automatic RTSS defaults on within the independently opt-in countdown. It uses any tracked foreground executable regardless of launcher/source; legacy selected-path lists remain readable but do not gate automatic routing. One bounded background queue prepares profiles from exact rules and already discovered artwork EXEs, revalidating tracking policy and avoiding additional directory scans. Other profiles are prepared while idle; an active game's profile takes priority. Unchanged profiles are neither rewritten nor reloaded. Per-game OSD/detection settings are merged; global settings, framerate limits and display-mode settings are preserved. RTSS profiles use basenames, so the additional exact-path/identity publishing gate is essential. The existing SDK mapping is checked before starting RTSS, with a ten-second start throttle and no additional Windows startup registration. RTSS runs with the monitor's existing privileges through the child-only [RunAsInvoker compatibility fix](https://learn.microsoft.com/en-us/windows/deployment/planning/compatibility-fixes-for-windows-8-windows-7-and-windows-vista); system/UAC policy and executable manifests are not changed. Desktop preview never publishes to RTSS. Unavailable or stale RTSS receipts fall back to the desktop countdown. Early-popup replacement still requires a fresh matching renderer receipt or a desktop overlay outside the Windows fullscreen/busy state. Disabling automatic RTSS/overlay cancels queued preparation; no game or foreign RTSS process is stopped.

RTSS placement uses its native per-game PositionX/PositionY properties with signed edge anchors and CoordinateSpace=1 (whole framebuffer). Absolute hypertext P/L layers were removed after the Stardew trial showed displaced text. The worker changes native profile placement only when the normalized position or render resolution changes, preserves that placement during profile preparation, and reloads it through the documented SDK API. OSD coordinates are shared by RTSS clients within that game.


### 2.12 event-driven sync and Auth storage guards

Qt uses startup, tracked gameplay transitions and manual requests. Nearby transitions
share one single-shot timer, which also waits for the durable ten-minute guard.
The existing visible GUI timer updates the countdown without rebuilding statistics.
Protocol negotiation rejects old automatic clients with HTTP 426 before reading
bodies or querying SQL. The service-only limited RPC adds an atomic ten-minute
device cooldown and daily 20/monthly 600 request limits per group AND owner.
Dedicated UTC-day ledgers survive code rotation. Rejected cooldown/quota requests
do not write payloads or accounting tuples. The existing core RPC remains
service-role-only for internal validation and traffic/storage budgets. Backend admission allows
100 groups, with dynamic fair request/egress shares and persistent owner ledgers.
Saturated SQL counters stop writing tuple versions. Bounded Edge maps reject
excess traffic before database/body work; they are isolate-local.

An invoker Custom Access Token hook bounds session/token creation and removes
metadata from JWT claims. Invoker Auth-table triggers bound account metadata and
the combined OAuth/PKCE state registry, covering orphan client state. A separate
five-minute cron job removes old state, leaving active flows/sessions intact.
These provider-schema integrations require post-upgrade compatibility checks.
Upstream Edge/Auth invocations and network floods remain provider concerns;
see SECURITY.md for exact limits, estimates and the remaining availability risk.
