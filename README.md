# Game Time Monitor — 2.11.0

**[Download for Windows x64 — 2.11.0](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 checksum](downloads/GameTimeMonitor-Setup.exe.sha256) · [Magyar](README.hu.md)

A Windows 11 gaming hub that tracks foreground play time, shows your daily budget and reminds you when it is time to finish. It also includes a configurable bedtime reminder.

I built this for my own daily use and am sharing it for anyone who finds it useful. The desktop features work offline, without an account. Linking statistics between your computers is optional.

![Game library and daily play-time budget](docs/images/library-en.png)
*English interface with real games and locally available artwork. Play-history values are demonstration data; game artwork belongs to its respective owners.*

## Features

- **Foreground time tracking.** Counts time while a tracked game is active. Browsers, launchers, background games, sleep and locked sessions do not consume the daily budget.
- **Daily budget and reminders.** A shared local budget across tracked games, an early warning and an expiry reminder. Thresholds are configurable; the day resets at local midnight.
- **Gaming Hub.** Find and launch installed games, search and filter the library, hide cards, assign executables and exclude individual games from tracking. Covers and icons come from local files.
- **In-game countdown.** Optional transparent countdown with monitor, position and opacity controls. Supports a desktop overlay and integration with a separately installed RTSS.
- **Play restriction.** Optional repeated minimization after a separate daily threshold, with ten seconds to save and quit on each return to a tracked game.
- **Bedtime reminder.** Separate reminder, bedtime and morning-resume times. Optional minimization of the foreground window every ten seconds during bedtime, including browsers and other apps, without sending Escape.
- **Statistics and computer linking.** Daily charts, date ranges and per-game totals, with optional encrypted synchronization and filtering by computer.
- **English and Hungarian.** Switch languages from the sidebar.

## Supported platforms and games

| Platform or source | Support |
| --- | --- |
| Windows 11 x64 | Supported desktop platform; no administrator rights needed for normal installation and use. |
| Steam | Automatic discovery from local installation metadata, including multiple libraries. |
| Epic Games Launcher | Automatic discovery of installed games from local manifests. |
| Ubisoft Connect | Installed-game discovery and launch integration. |
| Riot Client | Installed-game discovery and launch integration; Riot Client and Vanguard are excluded from game time. |
| Minecraft: Java Edition | Discovery from the official Java game data and recognition of its dedicated runtime. |
| Standalone and other games | Discovery in the configured games folder, plus manual executable assignment. |
| RTSS 7.3.7+ | Optional in-game countdown integration; [RTSS is a separate download](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/). |

macOS, Linux and Windows ARM64 are not supported builds. Minecraft Bedrock and Xbox/Microsoft Store games have no dedicated automatic discovery. Manual tracking requires an accessible game executable. Elevated, protected and anti-cheat games can limit foreground inspection, overlays or minimization; compatibility varies by game.

## Install or update

1. Download **GameTimeMonitor-Setup.exe** using the link at the top.
2. Run the installer. Python, Qt and the required runtime libraries are included.
3. Open **Gaming Hub** from the desktop or tray icon. It starts in the tray on subsequent Windows sign-ins.

Updates preserve history, settings, hidden games and tracking exclusions, and create a profile backup first. The installer is currently **unsigned**, so Windows may show a publisher or reputation warning.

The main window's **X** hides it to the tray; tracking and reminders continue. Use **Exit monitor** from the tray menu to stop the app.

## Set your limits

Open **Settings**, change the values and select **Save**.

| Setting | Initial value |
| --- | --- |
| Daily game-time budget | 120 minutes |
| Early warning | After 100 minutes |
| Optional play-restriction threshold | 125 minutes |
| Bedtime reminder / bedtime / morning resume | 23:55 / 00:00 / 06:00 |

The countdown, play restriction, bedtime reminder and cloud synchronization are off on a fresh profile until enabled. The daily game budget and bedtime schedule are independent. Bedtime uses the local clock while the monitor runs; it does not wake the PC or catch up a missed reminder.

![Configurable bedtime reminder](docs/images/bedtime-en.png)

Minimizing a game may leave it running, particularly in online play. The Hub remains accessible so you can change or disable restrictions. This is a personal reminder tool, not tamper-resistant parental control.

## Statistics and optional synchronization

**Statistics** shows daily play time, date-range summaries and a breakdown by game and computer.

![Daily statistics and per-game history](docs/images/statistics-en.png)

To link your own computers:

1. On the first computer, open **Statistics → Link computers**, sign in with GitHub, enable synchronization and save.
2. Copy the generated connection code. Paste it into the same dialog on the other computer and save. Joining an existing code does not require another GitHub sign-in.

Automatic sync runs every five minutes while Statistics is visible and every fifteen minutes in the background. **Sync now** permits a manual request once a minute, within server limits. The charts can combine linked computers; daily budgets and exclusions remain local to each computer.

**Keep the connection code private:** it provides access to the linked group's encrypted history. The shared hosted service has registration and usage limits and no guaranteed availability. Local tracking continues when sync is unavailable.

## Your data

History and settings are stored locally in the Windows Documents folder under `GameTimeMonitor\data`. Account-free tracking has no analytics or general telemetry. Optional sync encrypts game history and computer names on the client before uploading them; GitHub sign-in is used to manage the cloud connection.

To back up your profile, exit the app from the tray and copy the data folder. Uninstalling the app preserves the history. See [Privacy](PRIVACY.md) for the data handled by optional online features and their deletion controls.

## Project and support

This is a personal project, maintained as time permits. Others are welcome to use it, report reproducible bugs and suggest improvements through [GitHub Issues](https://github.com/Blintboi/windows-game-time-monitor/issues). Include your app version, Windows version, game source and reproduction steps. Keep connection codes, tokens and personal databases out of public reports.

The project's own code and documentation use the [MIT license](LICENSE). Game artwork and bundled dependencies retain their respective rights and licenses; see [Third-party notices](THIRD-PARTY-NOTICES.md).

For source setup and builds, see [Development](docs/DEVELOPMENT.md). Technical details are in [Architecture](ARCHITECTURE.md), [Testing](TESTING.md) and [Security](SECURITY.md).
