# Keep Improving — 2.35.0

**[Download for Windows x64 — 2.35.0](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 checksum](downloads/GameTimeMonitor-Setup.exe.sha256) · [Magyar](README.hu.md)

Keep Improving helps you see where your computer time goes and set limits that suit you. Track games, applications and websites, create individual or shared budgets, schedule reminders and run focus sessions. Free and open source, with English and Hungarian interfaces.

![Activities in version 2.35.0](docs/images/library-en.png)
*Current interface with the maintainer’s actual game library. Game artwork belongs to its respective owners.*

## Get started

1. On **Windows 11 x64**, install the download above. Python and administrator rights are not required for a normal installation.
2. Open **Keep Improving**. Choose your language at the bottom of the sidebar.
3. Review your games and activities. Add a missing game by selecting its executable.
4. Open **Time budgets → Add new**. Choose a game, application, website or a group sharing one allowance. New profiles start without a compulsory budget.
5. For website measurement and blocking, [connect the browser extension](#browser-extension).

Each page has its own settings button. **Day starts at** is universal: statistics and daily budgets renew together, at midnight by default. Choosing 01:00 keeps activity before 01:00 in the previous day. Older daily totals cannot be split retrospectively because they contain no exact interval timestamps.

Closing the main window leaves the monitor in the system tray. Choose **Exit monitor** there to stop it. Upgrades preserve your profile; the monitor starts with Windows.

The installer is currently **unsigned**. Code signing is deferred; there is no active SignPath certificate. See the [Windows trust guide](docs/WINDOWS-TRUST.hu.md). Do not disable antivirus protection to install a flagged file.

## Budgets: choose what happens

Open a budget and select **Warnings and restrictions…**. Enable **Use these steps**, add actions and then save the budget with **Save changes**.

| Action | Applications and games | Websites |
| --- | --- | --- |
| Warning | Sound, popup, or both | Sound, popup, or both |
| Minimize | Minimize the affected window | Show the block page |
| Cover and mute / block website | Opaque restriction screen and target audio mute | Redirect affected tabs to a local block page |
| Close application / browser tab | Ask the app to close, then force-close after up to five seconds | Close only affected tabs |

Warnings can run before, at or after expiry. Restrictions start at or after expiry. Add several steps at different times—for example, warn two minutes before, cover at expiry, then close five minutes later. A warning alone does not block anything. Simultaneous restrictions use the strongest action: close, cover, then minimize.

**One-time save allowance** can be disabled or set to **1–60 minutes**. The cover screen offers that time once per budget per day. The app and its audio are restored while you save; a countdown shows the remaining time, then the app closes. For websites, only the original tab gets the allowance, then blocking returns. Overlapping budgets must all allow it; the shortest allowance applies. Restarting the monitor does not renew the allowance.

Closing an application can lose unsaved work, so closing and save allowances require the checkbox in the editor. System processes, launchers and recognized protected games are excluded from the new cover/close operations. Exclusive fullscreen can require a one-time minimize to show the interactive restriction screen. Audio control covers the verified process's normal Windows audio sessions, not unrelated processes or system volume. Read the [restriction details](docs/RESTRICTION-PLAN.hu.md).

Existing budgets retain their earlier behavior until custom steps are enabled. Game limits, weekly schedules and optional bedtime caps remain available. This is a personal time-management tool, not tamper-resistant parental control.

![The current shared game budget editor](docs/images/bedtime-en.png)

## Reminders and countdowns

**Notifications** lists the built-in reminders and your scheduled messages together. Set the title, text, icon, time and weekdays of a custom notification. Desktop notifications can be dismissed or moved. Ordinary reminders and countdowns do not take keyboard focus from games.

Countdown appearance and position can be customized per target. Supported fullscreen games can use separately installed **RTSS 7.3.7 or later**; desktop rendering is used where available. Fullscreen compatibility depends on the game and renderer. Protected games have separate explicit consent controls; see the [anti-cheat guide](docs/ANTICHEAT.hu.md).

## What counts as activity?

Only foreground activity is measured. Reading, game menus and pauses count even without input. Background applications, launchers as game time, locked sessions and sleep do not count. Windows Explorer and shell screens are treated as idle and hidden from previous application statistics too.

The paired extension identifies public website domains and Brave's new-tab screen. An identified Brave new tab is idle. Other unclassified browser time is retained: older aggregate records cannot reliably separate a new tab from a site whose domain was unavailable. Website time is part of browser time, never extra time added on top.

Private tab domains, page titles and page contents are not recorded. Application and website measurement can be disabled; application exclusions hide past records and prevent new measurement. Game tracking and game exclusions remain separate.

## Browser extension

For Brave, Chrome and Edge:

1. Keep the monitor running and open **Focus mode → Browser connection**.
2. Open `brave://extensions`, `chrome://extensions` or `edge://extensions` and enable **Developer mode**.
3. Choose **Load unpacked** and select the `browser_extension` folder shown by the app.
4. Open the extension's options, paste **Copy pairing code** from the app, choose your browser and select **Save & connect**.
5. Repeat in each browser/profile you use. Keep the pairing code private.

After upgrading from an older version, **reload the extension** so the new block page and navigation permission take effect. It communicates with the monitor locally. To return from a block page, the original URL stays temporarily in browser session storage; it is not sent to the desktop app or statistics service. Disabling the extension stops website measurement and blocking. Restrictions are released if the monitor connection fails.

## Focus and statistics

**Focus mode** provides configurable work and break intervals. During work, selected websites are blocked and selected foreground applications are minimized. Pausing, stopping or taking a break releases those restrictions. A save allowance never overrides a separate active focus restriction.

**Statistics** shows games, applications and websites by day and computer, without double-counting browser activity. Optional computer linking combines history and supported settings from your own PCs. On the first PC, sign in with GitHub under **Computers & sync → Link computers**; use its connection code on the others. Keep the code private: it grants access to the shared data.

Synchronization encrypts data on the client before upload. Budgets and their consumption remain local; the new restriction plans and save allowances also stay local. Sync requests are at least ten minutes apart, with limits of 20 successful requests per UTC day and 600 per month. Local tracking works offline.

![Game statistics from real recorded activity](docs/images/statistics-en.png)
*Recorded local game history, captured on 2026-10-30 with permission. No generated usage values.*

![Current focus timer](docs/images/focus-en.png)

## Data and help

Your profile is in `Documents\GameTimeMonitor\data`. Exit the monitor before copying the folder for a backup. Uninstalling preserves it. Local history is not encrypted. There is no advertising or general analytics telemetry; see [Privacy](PRIVACY.md) and [Security](SECURITY.md).

Update checks contact GitHub at most once a day and can be disabled. Updates are downloaded through your browser and installed when you choose. The README link above is the primary download.

Report bugs in [GitHub Issues](https://github.com/Blintboi/keep-improving/issues), without connection codes, tokens or profile databases. See the [MIT license](LICENSE), [third-party notices](THIRD-PARTY-NOTICES.md), [development guide](docs/DEVELOPMENT.md), [architecture](ARCHITECTURE.md) and [testing](TESTING.md).
