# Game Time Monitor

An offline Windows 11 Gaming Hub and game-time monitor in one app. Launch games from a searchable library, measure foreground gameplay against a shared daily budget, and follow daily statistics in a dark English/Hungarian interface.

**Private preview 2.4.0.** The repository and release downloads remain private. Sign into GitHub with an account that has access on your other PC. Each PC keeps its own history; there is no cloud synchronization. [Magyar útmutató](README.hu.md).

The 2.0 interface uses Qt Widgets: a dark sidebar, responsive game cards, a daily-budget ring, contextual game actions and a redesigned statistics page. Artwork is read from existing local Steam caches, installed-game image files or game icons; no image service, launcher credentials or artwork downloads are used. Artwork and icons keep their original aspect ratios; complete cover images fit inside the card with dark padding where needed. Missing art has a colored monogram fallback. The shared controller/clock application icon remains unchanged.

## Install

1. Open this repository's **Releases**, download `GameTimeMonitor-2.4.0-Setup.exe`, and run it as your normal Windows user.
2. Python, Qt/PySide6 and SQLite are included. No separate Python, pip packages, administrator account or launcher login is needed by the monitor.
3. The app opens and discovers installed games. It starts in the tray when you sign into Windows. Open **Settings** to change your daily limit or Gaming Hub location.

The current installer is unsigned; Windows may show an unknown-publisher/SmartScreen prompt. Use the private release or a build you made yourself. A SHA-256 checksum accompanies the download.

Program files go under `%LOCALAPPDATA%\Programs\GameTimeMonitor`. Data goes in Windows Documents under `GameTimeMonitor\data`, including redirected Documents folders. A fresh install creates `Documents\Gaming Hub`. Upgrades preserve the existing Hub location, thresholds, history, executable rules, exclusions and hidden games, and back up the data before migration.

Setup adds one shared desktop **Gaming Hub** icon, a Start menu shortcut, Windows startup entries and an Installed apps entry. The desktop icon opens the integrated library in the running monitor, including when Statistics was open. The controller/clock icon stays the same. Upgrades consolidate and back up the previous owned monitor/Hub desktop entries. A fallback Startup shortcut and the Run entry share a per-profile mutex, so only one monitor runs. A restart is not required.

## Launch games

The **Library** page is the home screen, with artwork cards, quick Play buttons, search, source filters and sorting by name or today’s time. Search by name or filter by source, select a game and click **Play**, double-click its card or press Enter. Play uses Steam, Epic, Ubisoft and Riot launch routes, the Minecraft launcher or an existing shortcut with its original arguments. Standalone games with one executable can start directly. Discovery keeps the library up to date.

If the executable is ambiguous, use **Assign EXE** to choose it once. The app saves the choice and its tracking rule. **Add** also remembers the executable. Choices survive upgrades and discovery ID merges. Excluding a game's time does not prevent launching it. Removed games cannot launch. Preparation runs on a worker, keeping measurement and reminders responsive; opening a launcher alone does not count as gameplay.

Select a card and use its **…** menu for Hide / restore, Exclude / track, Assign EXE, EXE rules, Open game folder and Uninstall game. Statistics and Settings have their own pages in the left sidebar. **Open game folder** opens the selected installation when you need its files. The desktop Gaming Hub icon and tray's Open Gaming Hub return to this page without opening a separate folder or another monitor.

The library keeps labels brief: Today and Remaining above the cards, Play beside the game name, recorded time only when nonzero, and a source badge only when matching game names need distinguishing. The selected-game controls appear after selection. Extra help is available in tooltips; additional launcher locations are under **Settings → Games folder → Advanced**. The Settings title's tooltip shows the app version.

## Launcher clients and local artwork

Open **Launchers** in the sidebar for a separate client library: installed **Steam, Epic Games Launcher, Riot Client, Ubisoft Connect and Minecraft Launcher** appear with their own icons and **Open** buttons. Detection uses local Start menu/Desktop shortcut targets, known installation roots and installation-only registry/index records. Shortcuts with game-specific arguments are ignored for generic client opening; the executable path is rechecked before opening without shell command text or extra arguments. No client opens automatically. Refresh repeats detection, and the visible page refreshes about once a minute. A missing client shows a clear message.

Launcher clients remain accessible when the voluntary game restriction is active, so libraries, downloads and updates still work. Their foreground time does not consume the game budget. Starting an actual tracked game, including through a client, still follows the normal time/restriction policy.

Artwork discovery runs on a background worker for each library card. It tries the exact Steam app's local cache (including hashed filenames), an installed game's `steam_appid.txt` when available, and named cover/header/banner/splash/title/logo/icon files in the recognized installation. A bounded search prefers artwork/resource/content folders and skips saves, screenshots, mods, backups, logs, engine folders and reparse points. It does not scan whole drives or read launcher accounts. Minecraft can use its known title-logo PNG directly from a local version JAR, without extraction or execution. Images are decoded at thumbnail size with file/dimension/memory limits; corrupt/unsupported files are skipped. Only ordinary image files and that specific Minecraft image entry are supported; proprietary/encrypted game packs are not unpacked.

If no cover exists locally, the app uses a local game icon or the actual game's executable icon, then a monogram if neither is available. It does not invent or download covers. Images keep their complete aspect ratio with dark padding. **Refresh games and hub** repeats the artwork search, for example after an update adds new assets. This feature does not move/change game files, upload local images or change tracking history.

## Language and statistics

Choose **English** or **Magyar** from **Language / Nyelv** at the bottom of the sidebar. The main interface changes immediately and the choice is saved. New dialogs, tray menus and game-time reminders use that language. English remains the default for new installations.

Open the **Statistics / Statisztikák** page to see recorded play time by day and by game. Choose the last 7 days, last 30 days, this month, or enter an inclusive date range in `YYYY-MM-DD` format (up to 366 days). Click a chart bar or a date row to inspect that day's games; **Whole period** returns to the range-wide breakdown. The table shows play time and each game's percentage of the selected total. The summary shows total time, daily average and the most-played game. The visible page refreshes roughly every 10 seconds; Refresh also saves pending time before reading history.

Statistics include existing history, hidden/excluded games and removed installations. Hiding or uninstalling does not erase past time. Days without recorded time appear as zero. The daily average uses elapsed calendar days within the selected range, starting no earlier than installation; idle days after installation count, but days before installation and future dates do not. The footer shows the installation date and number of days used. That date survives upgrades; older profiles use the earlier available database creation date or first recorded activity. No activity before tracking began can be reconstructed, and the monitor does not infer unrecorded gameplay. Language changes preserve the selected date range.

## Daily use

Left click the tray icon to open the app. Right click for Open, Gaming Hub, Settings, Refresh games and hub, and Exit monitor. Closing the main window or using **Hide to tray** keeps tracking running. **Exit monitor** stops it until the next launch/sign-in.

Only a tracked game in the foreground counts. Browsers, launcher clients, background games, locked sessions and sleep do not count. Cutscenes still count; keyboard inactivity alone does not pause a game. Samples are taken once a second and saved regularly to SQLite. Midnight starts a new daily total.

The initial daily limit is **120 minutes**, with a warning at **100 minutes**. Alerts are reminders and do not kill games. The separate optional play restriction is described below. For an enabled popup at a threshold, the app tries one Escape in the currently tracked game, waits 200 ms, then displays an independent topmost alert. It verifies the foreground process identity and avoids sending Escape with modifier keys held. Hidden/minimized main windows do not suppress alerts. **Test alert** checks the popup itself, without simulating a gameplay threshold.

The earlier Tk version was confirmed over Minecraft Java fullscreen at real 20/30-second thresholds. The Qt version retains the guarded Escape/topmost mechanism and has independent hidden/minimized-window integration tests; repeat the real Minecraft trial before treating this preview as fullscreen-validated. Other fullscreen engines or elevated games may behave differently; see [testing](TESTING.md).

## In-game countdown (optional)

In **Settings → Countdown**, enable **Show while gaming**, then save. Fresh installs and older profiles keep it off until you enable it. Only the remaining-time digits appear, white on a fully transparent background, without a panel, border, caption or progress bar. The timer appears during tracked foreground gameplay and disappears when you switch to another app or lock Windows. Hiding the Hub does not hide the timer. The timer never accepts mouse/keyboard input or takes focus.

By default, enabling it replaces the early warning popup with red digits at your configured warning threshold (20 minutes remaining with the initial 100/120-minute settings). No Escape, sound or focus change occurs for that color warning. You can retain the early popup instead. **Popup when time expires** is a separate switch, on by default, and controls later over-budget session reminders too. The timer stays at zero after expiry. Popups keep the existing guarded Escape behavior; they do not stop games.

Drag the miniature timer inside Settings to choose its position, or use the arrow keys. Choose the active game's monitor automatically or a specific display; a disconnected display falls back to the primary monitor. **Preview (10s)** shows your unsaved placement without changing time/history. Click **Save** to keep changes. **Text opacity** adjusts only the digits from 25–100%; the surrounding area remains fully transparent. Upgrades keep the saved opacity percentage and apply it to the text. **Test alert** in this section checks the expiry-style popup.

This is a Windows desktop overlay, without game injection. Exclusive fullscreen or elevated/protected games may hide it. Borderless/windowed mode is more reliable; test visibility in your game before relying on the color warning. The app does not force fullscreen changes. Turn off the replacement option to retain the early popup if needed. A renderer error restores early popup delivery, but an exclusive-fullscreen game hiding an otherwise healthy desktop window cannot always be detected.

## Optional play restriction

Enable **Settings → Play restriction → Enable play restriction**, choose the total daily minutes, and save. It is off by default on fresh installs and upgrades; the initial threshold is **125 minutes**. This threshold is independent of the reminder budget (initially 120 minutes).

At or above the threshold, the monitor tries a guarded Escape for the recognized foreground game, waits 200 ms, then requests minimization of that exact process/window and opens the Hub. Returning to a tracked game triggers minimization again, with a two-second retry interval; Escape is attempted once per running process/day in the resident session so retries do not keep toggling its menu. The Hub blocks Play too, including already-prepared launch requests. External launcher starts are detected through foreground tracking. The shared total survives restarts, resets at local midnight, and includes hidden games; excluded games/apps remain outside this policy. A persistent banner explains the restriction and keeps Settings accessible. Disable it or change the threshold there at any time.

This is a voluntary interruption tool, not tamper-resistant parental control. It does not terminate/suspend processes, delete saves, block the keyboard/mouse, lock Windows or require admin rights. Minimizing may not pause a game, especially online play. Save/leave matches before the threshold. Unknown, elevated or protected games may need manual handling. Input/window actions are rechecked against the current interactive foreground process identity; switching apps, locking Windows or disabling the option during the delay cancels the pending action. If minimization is refused, a status message explains it and the monitor retries only on tracked foreground gameplay. After restriction, its banner replaces queued reminder popups.

## Discovery and Gaming Hub

Sources: **Steam, Epic Games, Ubisoft Connect, Riot including VALORANT, Minecraft Java**, and standalone games under the configured Games/Hub folder. Installation metadata and file/registry events update the catalog and shortcuts; repair scans cover missed events. Multiple Steam libraries and extra launcher locations can be configured.

Games outside known locations cannot always be recognized safely. Use **Add** to select the actual game EXE and name it. **Assign EXE** maps an executable to an existing game and remembers it for Play. Browsers and launcher clients are blocked. Shared `javaw.exe` is not globally treated as Minecraft; known Minecraft runtime locations or an exact manual rule are required.

The existing shortcuts folder is an optional companion, controlled by **Maintain game shortcuts** in Settings. The integrated library and Play work with this option off too. Installations and saves are not moved. In the companion folder, original shortcuts retain arguments, working directory and icons; an unknown launch command produces a folder link. `Folders` contains installation links and `Launchers` contains client shortcuts. Separate real installations of the same title are labeled by source.

Only unchanged shortcuts recorded as owned are removed when a game disappears. Edited/unowned files are preserved. A disconnected/unreadable library is kept until a successful scan. A Hub root has one authoritative profile owner and a lock to prevent duplication; do not delete `.gametime-hub.json` or share one Hub between independent profiles.

## Hide, exclude and uninstall

| Action | Result |
| --- | --- |
| **Hide / restore** | Hides the selected game from the integrated Hub. Tracking, history and optional folder links stay. Enable Show hidden games, select it and click again to restore. Survives restart and discovery. |
| **Exclude / track** | Changes whether future time counts; history stays. |
| **EXE rules** | Excludes or maps an individual executable. |
| **Uninstall game…** | Shows a guide, then opens an external removal tool only after Continue. |

Steam opens its uninstall flow. Epic/Ubisoft open the detected client with library removal instructions, or Installed apps if the client is missing. Riot/Minecraft use Windows Installed apps. Standalone games use an exact-match Windows Installer product removal or an identified uninstaller in that installation. Otherwise the game folder opens with manual instructions and an Installed apps fallback.

The app never executes arbitrary registry command text, adds silent-removal flags, or recursively deletes game files. Review the publisher's final confirmation, close running games if requested, and back up local saves. Discovery subsequently retires the removed game and unchanged owned Hub links, retaining history. A portable game's actual mapped EXE/folder must disappear before it is considered removed. Hiding does not uninstall anything.

Fresh installs count chess normally. **Exclude chess games** is optional. Pre-1.4 profiles keep their previous exclusion policy during migration; explicit per-game choices take precedence.

## Privacy and removing the monitor

The app has no telemetry, online account, data upload or cloud component. It reads local installation metadata, foreground process paths, game directories, local artwork assets and shortcut metadata. It does not read launcher tokens, browser history, messages or save contents. GitHub downloads are separate from the offline monitor.

Data includes `usage.sqlite3` (history, configuration including language, rules, visibility and alert markers), rotating `monitor.log`, `hub-state.json`, and the Hub icon under `assets`. Logs may contain local paths. Data, installed manifests and logs are excluded from Git. Stop the app before backing up the data folder. Whole-profile transfer is not automatic multi-PC sync: paths, EXE rules and Hub ownership are machine-specific.

Remove the monitor via **Windows Settings → Apps → Installed apps → Game Time Monitor → Uninstall**. Its uninstaller removes owned program files, app shortcuts including the integrated Hub desktop icon, and startup entries. Games, companion-folder links and data stay. To erase history afterwards, check your backup and delete the data folder manually. Removing the monitor never uninstalls games.

## Troubleshooting

- **No time counted:** check the active-game name while the actual game has focus, and inspect its tracking option in the **…** menu. Use Add / Assign EXE for unknown standalone games. EXE exclusions take precedence; a launcher alone does not count.
- **Missing after sign-in:** check Task Manager → Startup apps; Windows lets you disable startup. Launch from the Start menu. Setup errors are recorded in `%TEMP%\GameTimeMonitor-setup.log`.
- **Fullscreen alert hidden:** compare in borderless mode and check privilege levels. The monitor does not request administrator access. Report the game, display mode, time and relevant log lines privately.
- **Stale link:** use Refresh games and hub. Unreadable libraries and edited/unowned links are intentionally preserved. Removing only a shortcut does not remove the installed game.
- **Setup failed:** read its log and rerun after resolving the error. Setup refuses an unowned existing target folder and checks payload hashes. File copying is not a transactional MSI operation; a failed upgrade may need rerunning. The data backup stays.

## Develop and build

Source uses Python 3.10+ and Qt for Python, pinned in `requirements-runtime.txt`. The standalone build targets **Windows 11 x64**, tested with CPython 3.12.10. ARM64 and 32-bit builds are not provided/tested.

```powershell
python -m pip install -r requirements-runtime.txt
python -B main.py
python -B -m unittest discover -s tests -v
```

Always use temporary `--data-dir` paths for testing. Source launchers reuse an installed profile to prevent split catalogs. Commands include `--diagnose --report report.json`, `--configure`, `--scan-once`, `--sync-hub` and `--stop-wait 20`. Stop the resident app before configuration commands. Never point test Hubs at real game folders.

Build on Windows x64 with Python, PowerShell and built-in IExpress:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r packaging\requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build.ps1 -PythonPath .venv\Scripts\python.exe
```

Output is in `dist`. PyInstaller bundles the runtime; IExpress packages it with the per-user bootstrap. Setup verifies hashes, stops the old resident, backs up data, installs/verifies the app, configures startup and launches it without downloading a runtime. See [architecture](ARCHITECTURE.md), [testing](TESTING.md) and [third-party notices](THIRD-PARTY-NOTICES.md). The manual GitHub workflow produces private build artifacts and does not publish a release.

Legacy `Telepites.cmd` / `install.ps1` remain for source development and require Python. Normal users should download Setup. No open-source license has been chosen; public publication is a separate decision.
