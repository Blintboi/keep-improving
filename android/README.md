# Keep Improving Android – preview 0.1.0

**[Download Android installer — 0.1.0 preview (.apk)](https://github.com/Blintboi/keep-improving/raw/refs/heads/main/downloads/KeepImproving-Android.apk)** · [SHA-256 checksum](../downloads/KeepImproving-Android.apk.sha256) · [Magyar](README.hu.md)

The phone is an independent device with its own usage history and the existing
encrypted statistics protocol. Requires Android 8.0+. [Hungarian setup and design notes](README.hu.md).

Build with `android/build.ps1` (JDK 21, SDK/Build Tools 36, project Python environment).
The verified, signed APK and SHA-256 are written to `dist/KeepImproving-Android-0.1.0.apk`.
On your phone, use the download link above and open the APK to install. Android
may ask you to allow installation from the application opening the file. Grant
usage access inside Keep Improving, then enter the
desktop statistics connection code under **Statistics → Devices and sync**.
The browser extension pairing code is different. Sync the PC after the phone's upload.

The preview measures foreground app/game time, keeps local daily history, shows
native phone icons and supports all-device/device/category/date filters. It syncs
on app launch and manually, respects the existing ten-minute guard and group
quotas, and keeps cached statistics offline. A scheduled local Android job collects
events at a minimum fifteen-minute interval; it does not poll the server.
No foreground service, accessibility service, screen capture, root or admin keys.

Phone budgets/blocking, per-website phone tracking, reminders, remote preference
editing and new-code creation are not implemented yet. Desktop website statistics
are viewable; phone browsers are measured as applications. Android may delay local
jobs or discard old events; missing intervals are not estimated. Split-screen
accounting follows the last resumed application.

Only the phone's own history is uploaded. The protocol uses separate code-derived
HMAC-SHA256 authorization and AES-256-GCM encryption keys, matching the existing
Supabase Game Monitor Free service. Connection codes are protected by Android
Keystore; backups/device transfer are excluded to avoid cloning a device identity
without its key. Disconnect keeps local usage.

Updates must retain the package name and signing key; install over the prior APK.
The build creates a persistent private signing key outside the repo at
`%LOCALAPPDATA%/KeepImprovingAndroidSigning`, with a DPAPI-protected credential.
Preserve it for future updates. Nothing is published by the build.

Validation includes local ledger/permission/storage tests, bounded/tamper-resistant
cross-runtime crypto, real phone-store import into an isolated desktop profile,
deduplication and no re-export, HU/EN native graphics renders and Android lint.
The Gradle wrapper checksum is pinned. Production uses only Android platform APIs;
JUnit, JSON and Robolectric are test-only pinned dependencies.

A physical-phone installation and manufacturer background behavior still need
testing. This host lacks emulator acceleration and software emulation failed;
UI/storage/API checks use Robolectric and native graphics, not a running emulator.
The preview is distributed as an APK from the repository, not through an app store.
