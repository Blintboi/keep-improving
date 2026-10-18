# Game Time Monitor

An offline Windows 11 tray app that measures foreground gameplay, shares one daily budget across games, and reminds you to stop. Includes a dark English/Hungarian interface, daily statistics and an automatically maintained Gaming Hub.

**Private preview 1.5.0.** The repository and release downloads remain private. Sign into GitHub with an account that has access on your other PC. Each PC keeps its own history; there is no cloud synchronization. [Magyar útmutató](README.hu.md).

## Install

1. Open this repository's **Releases**, download `GameTimeMonitor-1.5.0-Setup.exe`, and run it as your normal Windows user.
2. Python, Tk and SQLite are included. No separate Python, pip packages, administrator account or launcher login is needed by the monitor.
3. The app opens and discovers installed games. It starts in the tray when you sign into Windows. Open **Settings** to change your daily limit or Gaming Hub location.

The current installer is unsigned; Windows may show an unknown-publisher/SmartScreen prompt. Use the private release or a build you made yourself. A SHA-256 checksum accompanies the download.

Program files go under `%LOCALAPPDATA%\Programs\GameTimeMonitor`. Data goes in Windows Documents under `GameTimeMonitor\data`, including redirected Documents folders. A fresh install creates `Documents\Gaming Hub`. Upgrades preserve the existing Hub location, thresholds, history, executable rules, exclusions and hidden games, and back up the data before migration.

Setup adds Start menu and desktop app shortcuts, a desktop Gaming Hub shortcut with the same controller/clock icon as the app, Windows startup entries and an Installed apps entry. The Hub icon is kept with user data so it survives removing the monitor. A fallback Startup shortcut and the Run entry share a per-profile mutex, so only one monitor runs. A restart is not required.

## Language and statistics

Choose **English** or **Magyar** from **Language / Nyelv** at the top of the window. The main interface changes immediately and the choice is saved. New dialogs, tray menus and game-time reminders use that language. English remains the default for new installations.

Open the **Statistics / Statisztikák** tab to see recorded play time by day and by game. Choose the last 7 days, last 30 days, this month, or enter an inclusive date range in `YYYY-MM-DD` format (up to 366 days). Click a chart bar or a date row to inspect that day's games; **Whole period** returns to the range-wide breakdown. The table shows play time and each game's percentage of the selected total. The summary shows total time, daily average and the most-played game. The visible page refreshes roughly every 10 seconds; Refresh also saves pending time before reading history.

Statistics include existing history, hidden/excluded games and removed installations. Hiding or uninstalling does not erase past time. Days without recorded time appear as zero; the average uses every calendar day in the selected range. No activity before tracking began can be reconstructed, and the monitor does not infer unrecorded gameplay. Language changes preserve the selected date range.

## Daily use

Left click the tray icon to open the app. Right click for Open, Gaming Hub, Settings, Refresh games and hub, and Exit monitor. Closing the main window or using **Hide to tray** keeps tracking running. **Exit monitor** stops it until the next launch/sign-in.

Only a tracked game in the foreground counts. Browsers, launcher clients, background games, locked sessions and sleep do not count. Cutscenes still count; keyboard inactivity alone does not pause a game. Samples are taken once a second and saved regularly to SQLite. Midnight starts a new daily total.

The initial daily limit is **120 minutes**, with a warning at **100 minutes**. Alerts are reminders: they do not kill games or enforce a lockout. At a threshold, the app tries one Escape in the currently tracked game, waits 200 ms, then displays an independent topmost alert. It verifies the foreground process identity and avoids sending Escape with modifier keys held. Hidden/minimized main windows do not suppress alerts. **Test alert** checks the popup itself, without simulating a gameplay threshold.

Minecraft Java in fullscreen was successfully tested on one Windows 11 PC at real 20/30-second thresholds. Other fullscreen engines or elevated games may behave differently; see [testing](TESTING.md).

## Discovery and Gaming Hub

Sources: **Steam, Epic Games, Ubisoft Connect, Riot including VALORANT, Minecraft Java**, and standalone games under the configured Games/Hub folder. Installation metadata and file/registry events update the catalog and shortcuts; repair scans cover missed events. Multiple Steam libraries and extra launcher locations can be configured.

Games outside known locations cannot always be recognized safely. Use **Add game** to select the game's actual EXE and name it; this also enables a Hub shortcut. **Assign EXE** maps an extra executable to an existing game. Browsers and launcher clients are blocked. Shared `javaw.exe` is not globally treated as Minecraft; known Minecraft runtime locations or an exact manual rule are required.

Hub entries are links: installations and saves are not moved. Original launcher shortcuts retain arguments, working directory and icons. Without a reliable launch command, a folder link is used. `Folders` contains installation-folder links; `Launchers` contains client shortcuts. Separate real installations of the same title are labeled by source.

Only unchanged shortcuts recorded as owned are removed when a game disappears. Edited/unowned files are preserved. A disconnected/unreadable library is kept until a successful scan. A Hub root has one authoritative profile owner and a lock to prevent duplication; do not delete `.gametime-hub.json` or share one Hub between independent profiles.

## Hide, exclude and uninstall

| Action | Result |
| --- | --- |
| **Hide / restore** | Hides the selected row. Tracking, history and Hub links stay. Enable Show hidden games, select it and click again to restore. Survives restart and discovery. |
| **Exclude / track** | Changes whether future time counts; history stays. |
| **EXE rules** | Excludes or maps an individual executable. |
| **Uninstall game…** | Shows a guide, then opens an external removal tool only after Continue. |

Steam opens its uninstall flow. Epic/Ubisoft open the detected client with library removal instructions, or Installed apps if the client is missing. Riot/Minecraft use Windows Installed apps. Standalone games use an exact-match Windows Installer product removal or an identified uninstaller in that installation. Otherwise the game folder opens with manual instructions and an Installed apps fallback.

The app never executes arbitrary registry command text, adds silent-removal flags, or recursively deletes game files. Review the publisher's final confirmation, close running games if requested, and back up local saves. Discovery subsequently retires the removed game and unchanged owned Hub links, retaining history. A portable game's actual mapped EXE/folder must disappear before it is considered removed. Hiding does not uninstall anything.

Fresh installs count chess normally. **Exclude chess games by default** is optional. Pre-1.4 profiles keep their previous exclusion policy during migration; explicit per-game choices take precedence.

## Privacy and removing the monitor

The app has no telemetry, online account, data upload or cloud component. It reads local installation metadata, foreground process paths, game directories and shortcut metadata. It does not read launcher tokens, browser history, messages or save contents. GitHub downloads are separate from the offline monitor.

Data includes `usage.sqlite3` (history, configuration including language, rules, visibility and alert markers), rotating `monitor.log`, `hub-state.json`, and the Hub icon under `assets`. Logs may contain local paths. Data, installed manifests and logs are excluded from Git. Stop the app before backing up the data folder. Whole-profile transfer is not automatic multi-PC sync: paths, EXE rules and Hub ownership are machine-specific.

Remove the monitor via **Windows Settings → Apps → Installed apps → Game Time Monitor → Uninstall**. Its uninstaller removes owned program files, app shortcuts and startup entries, preserving games, Hub links and data. To erase history afterwards, check your backup and delete the data folder manually. Removing the monitor never uninstalls games.

## Troubleshooting

- **No time counted:** check Active game while the actual game has focus, and confirm Tracked status. Add game / Assign EXE for unknown standalone games. EXE exclusions take precedence; a launcher alone does not count.
- **Missing after sign-in:** check Task Manager → Startup apps; Windows lets you disable startup. Launch from the Start menu. Setup errors are recorded in `%TEMP%\GameTimeMonitor-setup.log`.
- **Fullscreen alert hidden:** compare in borderless mode and check privilege levels. The monitor does not request administrator access. Report the game, display mode, time and relevant log lines privately.
- **Stale link:** use Refresh games and hub. Unreadable libraries and edited/unowned links are intentionally preserved. Removing only a shortcut does not remove the installed game.
- **Setup failed:** read its log and rerun after resolving the error. Setup refuses an unowned existing target folder and checks payload hashes. File copying is not a transactional MSI operation; a failed upgrade may need rerunning. The data backup stays.

## Develop and build

Source uses Python 3.9+ with Tk and no third-party runtime Python packages. The standalone build targets **Windows 11 x64**, tested with CPython 3.12.10. ARM64 and 32-bit builds are not provided/tested.

```powershell
python -B main.py
python -B -m unittest discover -s tests -v
```

Always use temporary `--data-dir` paths for testing. Source launchers reuse an installed profile to prevent split catalogs. Commands include `--diagnose --report report.json`, `--configure`, `--scan-once`, `--sync-hub` and `--stop-wait 20`. Stop the resident app before configuration commands. Never point test Hubs at real game folders.

Build on Windows x64 with Python/Tk, PowerShell and built-in IExpress:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r packaging\requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build.ps1 -PythonPath .venv\Scripts\python.exe
```

Output is in `dist`. PyInstaller bundles the runtime; IExpress packages it with the per-user bootstrap. Setup verifies hashes, stops the old resident, backs up data, installs/verifies the app, configures startup and launches it without downloading a runtime. See [architecture](ARCHITECTURE.md), [testing](TESTING.md) and [third-party notices](THIRD-PARTY-NOTICES.md). The manual GitHub workflow produces private build artifacts and does not publish a release.

Legacy `Telepites.cmd` / `install.ps1` remain for source development and require Python. Normal users should download Setup. No open-source license has been chosen; public publication is a separate decision.
