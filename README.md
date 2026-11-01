# Keep Improving — 2.39.21

**[Download for Windows x64 — 2.39.21](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 checksum](downloads/GameTimeMonitor-Setup.exe.sha256) · [Magyar](README.hu.md)

Keep Improving helps you see where your computer time goes and set limits that suit you. Track games, applications and websites, create individual or shared budgets, schedule reminders and run focus sessions. Free and open source, with English and Hungarian interfaces.

![Activities in version 2.35.0](docs/images/library-en.png)
*Current interface with the maintainer’s actual game library. Game artwork belongs to its respective owners.*

## Get started

1. On **Windows 11 x64**, install the download above. Python and administrator rights are not required for a normal installation.
2. Open **Keep Improving**. Choose your language at the bottom of the sidebar.
3. Review your games and activities. Add a missing game by selecting its executable.
4. Open **Time budgets → Add new**. Choose a game, application, website or a group sharing one allowance. New profiles start without a compulsory budget.
5. For website measurement and blocking, [connect the browser extension](#browser-extension).

To remove a budget, select its trash icon and then **Save changes**. Recorded activity history stays available.

Each page has its own settings button. **Day starts at** controls the statistics boundary and the default for daily budgets, at midnight by default. Each budget can instead use its own renewal time. Changing it carries already consumed time forward; older daily totals cannot be split retrospectively because they contain no exact interval timestamps. Linked computers running an older version temporarily contribute their entire overlapping daily totals until updated. Website breaks can redirect to a chosen HTTP or HTTPS page; reload the Keep Improving browser extension after updating to use it.

Closing the main window leaves the monitor in the system tray. Choose **Exit monitor** there to stop it. Upgrades preserve your profile; the monitor starts with Windows.

The installer is currently **unsigned**. Code signing is deferred; there is no active SignPath certificate. See the [Windows trust guide](docs/WINDOWS-TRUST.hu.md). Do not disable antivirus protection to install a flagged file.

The **Overview** remembers its activity, period, computer, day and list filters, search text and matching-name setting on this computer. Relative periods such as the last 30 days continue to follow the current day.

## Budgets: choose what happens

Open a budget, choose the days and daily allowance, then use **Add action** to choose a warning or restriction. Blocks sort automatically by time. Existing enabled restrictions also appear here and remain active unless removed. When creating a budget, choose **All games** to build the weekly shared game budget, or **Computer use · scheduled period** to set start and end times. The period warning and window minimization can be added or removed independently.

Each budget has one configuration and its own active weekdays. For different weekend limits, add another budget with those days selected; multiple named computer-use periods are supported too. The editor flags overlapping activities and times, and all applicable restrictions remain in force. Selected members are listed in full, including websites you have not visited yet.

Unfinished budget edits are kept locally as drafts when you leave the editor or restart the app. **Save** applies them; **Discard draft** removes the unfinished changes after confirmation. General settings are not included in these drafts.

| Action | Applications and games | Websites |
| --- | --- | --- |
| Warning | Sound, popup, or both | Sound, popup, or both |
| Break | Chosen restriction for the configured duration | Chosen restriction for the configured duration |
| Restriction | Request save time or close the application now | Show the block page with optional save time |

Choose the weekdays when each budget applies. An action can start after the chosen number of minutes of actual use or at a daily clock time. The daily window runs from that budget’s renewal time to the chosen closing time; the minute allowance can be disabled when the window alone is enough. An enabled 0-minute budget blocks access immediately, without adding an action. Mixed budgets provide separate application/game and website settings within each action. Applications have one new restriction action; previously saved minimize, cover and close actions retain their behavior until edited. When a restriction and break overlap, the restriction takes priority and permits its save allowance while the break continues.

A **break** starts after the chosen amount of use, applies the selected restriction for the configured number of minutes, then releases. Another break follows after the same amount of additional use, only while time remains in the budget. Breaks run in real time and survive restarts and day changes; other active rules may still restrict access.

**One-time save allowance** is **0–60 minutes**. With 0, the application closes without a save interval. Otherwise the restriction screen offers that time once per budget per day, or you can close the application immediately. The app and its audio are restored while you save; a countdown shows the remaining time, then the app closes. For websites, only the original tab gets the allowance, then blocking returns. Overlapping restrictions must all allow it; the shortest allowance applies. Restarting the monitor does not renew the allowance.

Closing an application can lose unsaved work, so closing and save allowances require the checkbox in the editor. System processes, launchers and recognized protected games are excluded from the new cover/close operations. Exclusive fullscreen can require a one-time minimize to show the interactive restriction screen. Audio control covers the verified process's normal Windows audio sessions, not unrelated processes or system volume. Read the [restriction details](docs/RESTRICTION-PLAN.hu.md).

Previously saved restriction actions retain their behavior until edited. Game limits, weekly schedules and optional bedtime caps remain available. This is a personal time-management tool, not tamper-resistant parental control.

![The current shared game budget editor](docs/images/bedtime-en.png)

## Reminders and countdowns

Each budget has **Countdown settings…** for visibility, position, size and colors. Game budgets also offer **Use RTSS in games**. These changes apply when you save the budget and can be cancelled with it. Individual activity styles take precedence over budget defaults; website and application countdowns use the desktop renderer. All new regular action menus, including website budgets, offer a single **Restriction** choice.

In a group's countdown editor, choose **Budget default** or an individual member in **Countdown target**. Members can have their own position, size, colors and visibility; games can also use their own RTSS setting. Switching targets retains edits, and budget cancellation discards them.

**Notifications** lists the built-in reminders and your scheduled messages together. Set the title, text, icon, time and weekdays of a custom notification. Desktop notifications can be dismissed or moved. Ordinary reminders and countdowns do not take keyboard focus from games.

The countdown shows the next event prominently, with the remaining daily allowance below it. During a break, its remaining time stays available in the tray, including after a website redirects to a new tab. The tray menu lists running timers by budget name. Adding a restriction does not add an expiry warning: only the separately configured warning action is delivered. The save-time dialog remains available when enabled.

Turn off **Detailed RTSS countdown** in **Notifications** to show only the time until the next event in games. Desktop and tray counters keep their details.

Countdown appearance and position can be customized per target. Supported fullscreen games can use separately installed **RTSS 7.3.7 or later**; desktop rendering is used where available. Fullscreen compatibility depends on the game and renderer. Protected games have separate explicit consent controls; see the [anti-cheat guide](docs/ANTICHEAT.hu.md).

## What counts as activity?

Only foreground activity is measured. Reading, game menus and pauses count even without input. Background applications, launchers as game time, locked sessions and sleep do not count. Windows Explorer and shell screens are treated as idle and hidden from previous application statistics too.

The paired extension identifies public website domains and Brave's new-tab screen. An identified Brave new tab is idle. Other unclassified browser time is retained: older aggregate records cannot reliably separate a new tab from a site whose domain was unavailable. Website time is part of browser time, never extra time added on top.

Private tab domains, page titles and page contents are not recorded. Application and website measurement can be disabled; application exclusions hide past records and prevent new measurement. Game tracking and game exclusions remain separate.

## Browser extension

For Brave, Chrome and Edge:

1. Keep the monitor running and open **Activities → Websites → Browser connection**.
2. Open `brave://extensions`, `chrome://extensions` or `edge://extensions` and enable **Developer mode**.
3. Choose **Load unpacked** and select the `browser_extension` folder shown by the app.
4. Open the extension's options, paste **Copy pairing code** from the app, choose your browser and select **Save & connect**.
5. Repeat in each browser/profile you use. Keep the pairing code private.

After upgrading from an older version, **reload the extension** so the new block page and navigation permission take effect. It communicates with the monitor locally. To return from a block page, the original URL stays temporarily in browser session storage; it is not sent to the desktop app or statistics service. Disabling the extension stops website measurement and blocking. Restrictions are released if the monitor connection fails.

## Focus and statistics

**Focus mode** provides configurable work and break intervals. During work, selected websites are blocked and selected foreground applications are minimized. Pausing, stopping or taking a break releases those restrictions. A save allowance never overrides a separate active focus restriction.

**Statistics** shows games, applications and websites by day and computer, without double-counting browser activity. Optional computer linking combines history and supported settings from your own PCs. On the first PC, sign in with GitHub under **Computers & sync → Link computers**; use its connection code on the others. Keep the code private: it grants access to the shared data.

Synchronization encrypts data on the client before upload. The shared game budget and per-game limits count synchronized game time from linked computers; update every computer to this version for both sides to count it. Other activity budgets, restriction plans and save allowances stay local. Sync requests are at least ten minutes apart, with limits of 20 successful requests per UTC day and 600 per month. The other computer's latest time may be delayed or unavailable offline; local tracking continues offline.

![Game statistics from real recorded activity](docs/images/statistics-en.png)
*Recorded local game history, captured on 2026-10-30 with permission. No generated usage values.*

![Current focus timer](docs/images/focus-en.png)

## Data and help

Your profile is in `Documents\GameTimeMonitor\data`. Exit the monitor before copying the folder for a backup. Uninstalling preserves it. Local history is not encrypted. There is no advertising or general analytics telemetry; see [Privacy](PRIVACY.md) and [Security](SECURITY.md).

Update checks contact GitHub at most once a day and can be disabled. Updates are downloaded through your browser and installed when you choose. The README link above is the primary download.

Report bugs in [GitHub Issues](https://github.com/Blintboi/keep-improving/issues), without connection codes, tokens or profile databases. See the [MIT license](LICENSE), [third-party notices](THIRD-PARTY-NOTICES.md), [development guide](docs/DEVELOPMENT.md), [architecture](ARCHITECTURE.md) and [testing](TESTING.md).
