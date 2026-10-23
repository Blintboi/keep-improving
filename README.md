# Game Time Monitor — 2.26.2

**[Download for Windows x64 — 2.26.2](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 checksum](downloads/GameTimeMonitor-Setup.exe.sha256) · [Magyar](README.hu.md)

A Windows 11 gaming hub that measures foreground game time, shows your remaining daily budget and reminds you when to finish. It includes a weekly schedule, bedtime reminders, customizable countdowns and optional encrypted statistics between your own computers.

This is a free, open-source personal project. Tracking and the desktop features work without an account or internet connection. **Automatic public update checks are on by default and can be disabled; cloud synchronization is off by default.**

## What is included

- **Game library:** discover installed games, launch them, search/filter cards, hide games and assign or exclude executables. Artwork comes from local files and caches.
- **Time tracking:** one local daily budget shared by tracked games. Background games, browsers, launchers, sleep and locked sessions do not consume it. Menus or pauses can count while the game remains in the foreground.
- **Weekly schedule:** select any of seven day buttons, individually or in groups, and configure budgets, warnings, restrictions and bedtime.
- **Countdown:** desktop or optional RTSS display, precise position, monitor, opacity, size, normal/warning colors and per-game overrides.
- **Reminders:** editable default messages, time placeholders, sound choices, a local WAV file or silence, with previews before saving.
- **Statistics:** color-coded daily bars by game or computer, legends, hover/click details, date ranges and summaries. Linked computers can be renamed.
- **English and Hungarian:** language changes update text while retaining loaded artwork, selections and unsaved settings.

**In 2.26.2:** countdown handoffs were tightened for rapid Alt–Tab, game switches and preview on/off. Late RTSS receipts cannot restore an earlier visit, and health checks retain visible text instead of repeatedly clearing it. Temporary discovery/watcher errors retry quietly in the log; persistent failures show a plain-language notice.

![Game library and daily budget](docs/images/library-en.png)
*Illustration of the English interface. Screenshots may show an earlier layout and demonstration history; game artwork belongs to its respective owners.*

## Requirements and supported sources

**Windows 11 x64** is the supported platform. The installer includes Python, Qt/PySide6 6.12.0 and the required runtime libraries; normal installation and use do not require administrator rights. There are no supported macOS, Linux or Windows ARM64 builds.

| Source | Recognition and launch support |
| --- | --- |
| Steam | Local installation records, including multiple libraries. |
| Epic Games Launcher | Installed-game manifests. |
| Ubisoft Connect | Installed games and publisher-client launch integration. |
| Riot Client | Installed games and client launch integration; Riot Client and Vanguard are excluded from game time. |
| EA app / Origin | Local installation registrations; publisher launch links or an assigned game EXE. |
| Battle.net | Installation registrations and the local Agent index; recognized product launch links. |
| GOG Galaxy / offline GOG | Registered games, Galaxy launch integration and local primary play tasks without Galaxy. |
| Xbox / Microsoft Store | Installed GDK/Xbox Live game packages; registered Windows application identities. |
| Rockstar Games Launcher | Installed-game registrations and publisher-client launch. |
| Amazon Games | Local installation database and publisher launch links. |
| Minecraft: Java Edition | Official Java game data and its dedicated runtime. |
| Standalone and other games | The configured Games folder and manual executable assignments. |

**The Games folder remains available.** It is an additional discovery location for standalone games; you do not need to move Steam or other recognized libraries into it. Manual EXE assignment helps with unrecognized games, but cannot make an inaccessible executable or unsupported installation inspectable. Store packages without recognizable game metadata, elevated games and protected installations can have limitations. Client detection does not install launchers or games.

The **Launchers** page keeps discovered clients between restarts. Use **Refresh** after installing, moving or removing a client. Hiding a library card and excluding a game from time tracking are separate actions.

## Install, update and close

1. Download **GameTimeMonitor-Setup.exe** from the link at the top and run it.
2. Open **Gaming Hub** from its desktop shortcut or tray icon. On subsequent Windows sign-ins, the monitor starts in the tray.
3. Open **Settings**, configure your preferences and select **Save**. The default app directory is `%LOCALAPPDATA%\Programs\GameTimeMonitor`; the profile is separate under the Windows Documents folder, `GameTimeMonitor\data`.

An upgrade backs up the existing profile and preserves history, settings, synchronization credentials, hidden games and tracking exclusions. The window's **X** hides the Hub; tracking and reminders continue. Use **Exit monitor** in the tray menu to stop it.

### Update notifications

Under **Settings → Application updates**, you can disable automatic checks, use **Check for updates** and see the installed version. Automatic checks request a small public GitHub version file at most once per day. A newer version is indicated in the Hub and tray without an interrupting popup.

**Download update** opens the official installer URL in your browser. You choose when to download and run it; the app does not download or install executables in the background. Temporary automatic-check failures stay in the log. Builds older than 2.26.0 need a manual download to gain this feature.

### Windows trust

The installer and main executable are currently **unsigned**. Windows may warn about an unknown publisher or block execution under local security policies. File icons, version properties and a matching SHA-256 do not constitute Microsoft approval or a publisher signature. The app does not add antivirus exceptions or disable Windows protection. See the [Windows trust/signing guide (Hungarian)](docs/WINDOWS-TRUST.hu.md).

## Daily limits, weekly schedule and bedtime

Use **Settings → Weekly schedule**. Seven day buttons and **Every day / Weekdays / Weekend** shortcuts select a single day or any group. Mixed values are marked; a group edit changes only fields you edit. A separate command copies a day's complete plan. Existing weekend settings remain compatible.

| Setting | Fresh-profile value |
| --- | --- |
| Daily budget, shared across tracked games | 120 minutes |
| Early warning | After 100 minutes |
| Optional play-restriction threshold | 125 minutes; restriction off |
| Bedtime warning / bedtime / morning resume | 23:55 / 00:00 / 06:00; bedtime off |
| Cap remaining game time at bedtime | Off |
| Countdown / RTSS / cloud synchronization | Off |
| Automatic update checks | On |

The daily quota resets at **local midnight**. The optional **Cap remaining game time at bedtime** shows the smaller of the unused quota and the time until bedtime. For example, with two hours still unused at 23:00 and bedtime at 00:00, it shows one hour. The Hub, tray and desktop/RTSS countdown agree. During the configured sleep window, the cap stays at zero until morning resume. It changes the displayed available time, not the configured quota or calendar-day history.

Daily restriction and bedtime minimization are separate opt-in controls. Daily restriction repeatedly minimizes an eligible tracked game after its threshold, allowing ten seconds to save/quit on a return. Bedtime minimization can affect eligible foreground apps, including browsers, every ten seconds until resume. **The app does not shut down the PC.** A minimized game may keep running, and online games may apply inactivity/leaving penalties. Protected games have additional safeguards below.

Bedtime follows the local clock while the monitor runs; it does not wake the computer or replay a missed warning. The Hub remains accessible to change settings. This is a personal reminder tool, not tamper-resistant parental control.

![Bedtime settings](docs/images/bedtime-en.png)

## Countdown, preview and custom reminders

Enable the countdown in **Settings**. Choose a monitor, opacity and separate normal/warning colors. Set an **8–72 pt** text size and precise horizontal/vertical pixel coordinates, or drag the miniature. Arrow keys move one pixel; Shift + arrow moves ten. Instructions stay below the miniature instead of covering it on hover.

**Per-game countdowns**, also accessible from a game's menu, list installed games. Each game can inherit the global settings, use its own monitor/position/size/colors, or hide its countdown. Opacity and the RTSS automatic-mode switch are global. Hiding a countdown does not disable time tracking; reminder fallback remains available. Removed games leave the installed-game selector while their history and saved preferences remain.

The editor can show a dim **still image** of an allowed running game's client window. Opening the editor or choosing **Refresh game image** requests a capture; it is not a live video feed. Some renderers cannot supply an image. Pictures stay in memory and are neither saved nor synchronized.

**Preview (10s)** brings an allowed recognized game to the foreground, restores it if minimized and uses the desktop/RTSS path. Alt–Tab away ends that preview. Draft changes update the existing countdown; preview numbers are examples while actual foreground time tracking continues. Choose the preview state next to the preview button, then save or cancel the drafts.

For compatible fullscreen games, install [RTSS 7.3.7+ separately](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/) and enable it in the countdown settings. The app automatically selects recognized, allowed games; a manual EXE list is not needed. A game that was already running may need to be saved and restarted once after enabling RTSS. Desktop fallback and reminder behavior depend on the renderer and Windows notification state.

Under **Settings → Custom messages**, edit the warning, daily-limit, later-session and bedtime texts. Editors start with the editable default. Supported time tokens are `{remaining}`, `{minutes}`, `{time}` and `{bedtime}`; other text stays literal. Defaults can be restored. Sound choices include Windows sounds, a local WAV file and silence. Messages, sounds, per-game styles and risk permissions stay local.

## Protected games and anti-cheat limitations

Detection uses game identifiers, executable names and known installation markers. It is game-specific and does not distinguish ranked/offline modes by reading game data. Compatibility detection is not publisher approval and cannot guarantee freedom from bans or crashes for every game/version.

| Action | Detected protected game |
| --- | --- |
| Foreground time measurement | Continues where Windows permits process identification. |
| Overlay, image capture and live preview | Off until explicit per-game overlay risk consent. Controls remain hidden without permission. |
| Automatic minimization | Off until separate per-game minimization consent; overlay permission does not grant it. |
| Automatic Escape | Always disabled, including after consent. |
| Reminders | Nonactivating windows; fullscreen situations unsuitable for a visual reminder use the selected sound. Muted/failed sound leaves delivery pending. |
| Uncheckable installations / anti-cheat helper processes | Consent cannot override these blocks. |

Review or revoke permission in **Per-game countdowns → Review overlay risks**. Consent is stored locally for the game and installation location; changes can require renewed acceptance. Casual/unprotected games retain their configured features. RTSS remains external hooking software, and revoking permission cannot unload a module another program already injected. See the [compatibility review and official references (Hungarian)](docs/ANTICHEAT.hu.md).

## Statistics and optional computer linking

Statistics provide stacked, color-coded daily bars with a **game/computer** switch, matching legends/table markers, time/share summaries, date ranges and daily details on hover/click. **Rename computer** works for every linked computer: your own name is shared on the next sync; aliases for other computers are local to the current connection and work offline.

![Daily statistics](docs/images/statistics-en.png)

To link your own computers:

1. On the first computer, open **Statistics → Link computers**, sign in with GitHub, enable synchronization and save.
2. Copy the connection code into the same dialog on another computer and save. Joining an existing code does not require another GitHub sign-in.

Sync is event-driven: once at startup, when tracked gameplay starts, and after it stops, combining nearby changes after a quiet minute. There is no periodic background sync. **Sync now** is also available. Each computer waits at least ten minutes between requests, including after restart. The shared service permits 20 successful requests per UTC day and 600 per UTC month across linked computers, also limited per code owner. Pending uploads wait for the guard; the computer must remain on and online for its latest time to reach other computers. Use 2.12.0 or newer on every linked computer; the latest version is recommended for current fixes.

Charts can combine computers, but **daily budgets, settings and game exclusions remain local**. The shared service has registration/resource limits and no guaranteed availability. Local tracking continues during sync outages.

## Privacy, backup and removal

- Local daily history/settings are stored in `Documents\GameTimeMonitor\data` (using Windows' actual Documents location). There is no advertising or general analytics telemetry; the local history database is not encrypted.
- The default daily update request gives GitHub normal connection metadata, including IP address, but sends no play history, game paths/names, computer name, credentials, device ID or installed version. Automatic requests can be disabled.
- Optional sync encrypts game times, game names/sources and computer display names on the client. The service receives encrypted snapshots and request metadata. **Anyone with the connection code can access/change the group's shared history: keep it private.**
- Saved connection codes and account sessions use Windows user-scoped protection. Backups are private; a move to another Windows account/computer may require signing in or entering the connection code again.

For a backup, **exit the monitor from the tray**, then copy the complete data folder. Updates create profile backups. Uninstalling preserves the profile; deleting local data also requires removing the folder/backups you no longer need. Disabling sync or signing out does not revoke an existing code or remove copies on other computers. Owner revocation/replacement and hosted retention are explained in [Privacy](PRIVACY.md) and [Security](SECURITY.md).

## Common questions

| Situation | What to check |
| --- | --- |
| An installed game is missing | Refresh discovery, check its launcher records, or assign an accessible game EXE. Keep the Games folder for standalone games. |
| An uninstalled game appears in history | History is retained intentionally; per-game countdown choices only list installed games. |
| No countdown / game image | Check global/per-game settings, the selected monitor, risk permission and RTSS availability. Image capture is renderer-dependent. |
| The timer shows less than the daily quota | Check the optional bedtime cap and that day's schedule. |
| A closed window still tracks | X hides to the tray. Use Exit monitor to stop it. |
| Another computer's time is delayed | Check synchronization, connectivity and the ten-minute/shared-service limits. |
| A temporary discovery problem appears | Automatic retries stay in the log; a persistent failure shows an understandable notice. |

## Project, support and development

Report reproducible bugs through [GitHub Issues](https://github.com/Blintboi/windows-game-time-monitor/issues), including app/Windows versions, game source and reproduction steps. Never attach connection codes, tokens or personal profile databases to a public issue. Report security issues privately through the route in [Security](SECURITY.md).

You can [support development through GitHub Sponsors](https://github.com/sponsors/Blintboi). Support is optional; the app stays free and open source. The project's own code/documentation use the [MIT license](LICENSE); artwork and bundled components retain their respective rights and [licenses](THIRD-PARTY-NOTICES.md).

For source setup/builds and contribution testing, see [Development](docs/DEVELOPMENT.md), [Architecture](ARCHITECTURE.md) and [Testing](TESTING.md). Releases include source and installer secret scans; checks reduce risk rather than guarantee universal compatibility.
