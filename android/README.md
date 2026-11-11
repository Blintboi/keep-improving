# Keep Improving for Android — 0.6.0

**[Download for Android 8.0+ (.apk)](https://github.com/Blintboi/keep-improving/raw/refs/heads/main/downloads/KeepImproving-Android.apk)** · [SHA-256](../downloads/KeepImproving-Android.apk.sha256) · [Magyar](README.hu.md) · [Windows application](../README.md)

Measure your phone use, see time and session counts, and set daily boundaries. The phone works independently and can share encrypted statistics and supported rules with your computers. Its version numbering is independent from Windows.

## Install and connect

1. Download the APK on your phone and open it. If prompted, allow that download app to install this package. Install over the existing app to retain your history and settings; do not uninstall first.
2. Open Keep Improving and enable **usage access** for measurement.
3. For responsive restrictions, enable **Settings → App covering**. This optional accessibility service uses application/window identity, not screen text, input or gestures. Permissions are explained before opening Android settings.
4. Grant notification access when requested. Android 12+ can also require **Alarms and reminders** for precise background deadlines; without it, timing is approximate.
5. Under **Settings → Devices & sync**, enter the same connection code as your Windows installation. This is different from the browser extension pairing code. Keep it private.

The app is distributed directly as an APK, not through an app store. Updates use the same signing key. Device power-saving policies can delay collection and reminders; force-stopping suspends Android receivers until the app is reopened.

## What you can do

- **Overview:** choose time or sessions, filter dates, device and activity type, search or sort, and export CSV through Android's file picker. It displays measured counts without minimum markers and preserves scroll position during refreshes.
- **Applications:** choose installed apps, classify games and exclude activities from measurement. The app's own interface and system screens are excluded from usage totals.
- **Budgets:** select apps or categories, active days, renewal time and an optional minute allowance. Add warnings, restrictions or breaks based on usage time, clock time or daily session count. A five-session allowance triggers on the sixth visit. Overlapping selections count an app once.
- **Focus:** use Pomodoro, pause/resume, short/long breaks and selected-app covering. Timers and completed rounds survive restarts.
- **Reminders:** configure clock-time, app-opening and daily focus-goal reminders, with sound, timeout and actions to start focus or open an app.
- **Devices:** display phone and PC budgets/reminders together, with device labels and filters. A rule can select one device, a named group or all linked devices. Each platform's apps must be selected explicitly.

The countdown is a quiet ongoing notification. It follows foreground app changes when protection is enabled; tap it to open Budgets. You can disable it under Settings. Home, settings, permission and dialer screens are exempt from covering. Protection is voluntary, not tamper-resistant.

The phone measures its browser as an application. Website history can arrive from paired PCs; phone browser tabs are not individually monitored or blocked. Windows opening-purpose questions, per-answer allowances and the **Break now** action are not yet available on Android.

## Sessions and synchronization

A session is continuous measured foreground use, assigned to its starting day. Moving between screens within the same app does not create a new session. Older history contains only the data that could actually be measured.

Only this phone's own usage is uploaded; imported computer data is not uploaded again. Snapshots are encrypted on the device using the existing connection code. Connection secrets use Android Keystore. Local history remains in the app's private database; it is not itself encrypted.

Visible devices check for changes periodically; edits request an earlier sync. Android batches background work, and service quotas or retry delays take precedence. Offline measurements and timers continue. Shared limits use the latest received totals, so disconnected devices can temporarily exceed a combined allowance. Sync status is visible in the app.

For an authorized USB-debugging connection, developers can run `build/venv-security/Scripts/python.exe android/usb_sync.py` from the repository. Both devices must already share a code and the Windows app must be running. The bounded encrypted exchange removes its temporary transfer files; it does not reset cloud quotas.

## Development and privacy

`android/build.ps1` runs unit tests, lint, APK build, Android/Windows encryption interoperability and signing checks. It uses JDK 21 and Android SDK 36. Signing credentials remain outside the repository; keep the original key for upgrades.

See [Privacy](../PRIVACY.md), [Security](../SECURITY.md), [test evidence](../TESTING.md) and [GitHub Issues](https://github.com/Blintboi/keep-improving/issues). Do not include connection codes, tokens or private usage databases in bug reports.
