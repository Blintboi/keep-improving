# Testing

Use isolated temporary profiles and synthetic game installations. Never uninstall a real user game to test removal; mock the execution boundary.

```powershell
python -B -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File tests\install_smoke.ps1 -ReportPath test-reports\source-install.json
python -B -m unittest discover -s tests -p test_qt_ui.py -v
python -B tests/overlay_smoke.py test-reports/overlay
```

Tests cover metadata/multiple libraries, watcher races, foreground/background time, sleep/lock/clock changes, midnight, persistence, ID migration, shared budgets, alerts, native tray behavior and Hub foreign-file preservation. Windows tests use actual temporary directory notifications, process queries and mutexes.

Version 1.6 adds integrated Play preparation for Steam/Epic/Ubisoft/Riot/Minecraft and standalone games, original shortcut arguments, canonical launch-only URIs, changed-link rejection, explicit EXE persistence and transactional ID migration, stale-choice cleanup and background-worker shutdown. Real UI smoke covers search/source filters, duplicate-click suppression, queued launch execution, uninterrupted tracker identity/time, language switching and returning from Statistics to the Hub inside the same window. Game execution is mocked. A real mutex/subprocess check verifies `--hub` requests the Hub page in the existing profile instead of starting another monitor.

Version 1.4 adds hidden-row persistence/migration and independent history/tracking checks, fresh/legacy chess policy, validated Steam IDs, launcher fallback, exact-root MSI selection, registry command rejection, portable-file preservation and mocked interactive uninstall execution.

Version 1.5 adds English/Hungarian language persistence and placeholder parity, translated reminders/removal guidance, strict inclusive statistics date ranges, per-game/day totals, hidden/removed/orphan history and flush/reopen accounting. Average tests cover installation-day migration/persistence, idle days since installation, custom ranges and exclusion of pre-installation/future days. GUI checks cover immediate language switching, the daily breakdown, the installation-based average, translated date errors and preservation of the selected period across language changes. The bundled upgrade checks language/installation-date preservation and retention of the Gaming Hub icon after monitor removal.

The retained legacy GUI smoke creates real Tk windows with synthetic fixtures. Inspect dark widgets, settings, hidden/minimized-root notifications, hide → Show hidden → restore, and removal guide Cancel/Close behavior. The legacy source smoke checks install/upgrade/history/startup/background-single-instance/uninstall behavior.

`tests/bundled_install_smoke.ps1` tests the standalone payload using isolated paths and uniquely named startup/Installed apps registrations, checking fresh install, upgrade, runtime diagnosis, uninstall and preservation of history/foreign files. Check real Setup extraction/launch before release, too.

The 1.6 bundled test redirects desktop shortcut creation into its own temporary Desktop fixture, exercises the old separate monitor/Hub-folder shortcut migration and checks one shared app icon and owned-shortcut removal during uninstall. It does not create test shortcuts on the user's actual desktop.

## Fullscreen evidence

On 2026-10-18, Minecraft Java fullscreen on Windows 11 was tested with a hidden main window and isolated 20/30-second warning/limit. Alerts appeared at 20.228 and 30.392 seconds, visible/topmost and foreground after guarded Escape. The user confirmed both appeared over Minecraft. Production thresholds/history were separate.

This verifies that setup, not every exclusive fullscreen engine, display layout, privilege level or anti-cheat environment. Borderless mode may help. Do not claim universal overlays or enforced game termination.

## Before sharing

- Run relevant tests; record actual results rather than reusing an old count.
- Check fresh installation and upgrade with history/hidden rows, and chess policy migration.
- Check the frozen runtime without Python on PATH, including Qt platform/image plugins, icon and PowerShell bridge resources.
- Check startup entries, data location, uninstall and foreign-file preservation.
- Check real fullscreen gameplay using a temporary short limit; restore settings afterwards.
- Verify private visibility and absence of data/logs/installed manifests from archives.

The second physical PC, ARM64 and other games' fullscreen modes still require user testing. Preview installers are unsigned.

## 2.1 countdown validation

212 automated tests passed in 73.942 seconds. The 18 overlay tests cover opt-in legacy defaults, independent warning/expiry policies, actual tracker threshold crossing without Escape/popup/sound, retained delayed expiry popups, renderer-error fallback, shared-budget display interpolation without duplicate usage writes, hiding on process changes/other apps/exclusion/lock, hidden games/Hub, native no-focus/input flags, preview isolation, persisted placement/opacity/monitor choices, keyboard/drag placement and disconnected/negative-coordinate/small-screen fallback.

The separate `overlay_smoke.py` opt-in test passed seven checks with a real synthetic WinForms process: the visible translucent renderer retained the existing foreground, and native WindowFromPoint hit-testing through its center returned the other process's window. Normal/red timer and Hungarian settings captures were inspected. It does not force user focus or inject input. This verifies native window behavior, not real gameplay or exclusive fullscreen. The new overlay still needs a real Minecraft fullscreen/borderless trial and second-PC testing. The installer upgrade fixture also checks all overlay preferences survive.

## 1.4.0 validation on 2026-10-18

150 automated tests passed in 58.746 seconds; 9 GUI checks, 18 legacy source-installer checks, and 14 bundled-runtime install/upgrade/uninstall checks passed. The Hub suite was rerun after its final directory-inventory change: 25 tests passed. All game-removal executions were mocked; no real games were uninstalled.

The standalone installer also preserves unrelated Windows startup values across fresh install, upgrade and uninstall. Final bootstrap was checked with paths containing spaces; the actual icon-branded Setup was installed on the development PC with its existing data.

## 1.5.0 validation on 2026-10-18

163 automated tests passed in 62.232 seconds after the installation-based average change. All 15 GUI smoke checks, 18 legacy source-installer checks and 18 bundled-runtime install/upgrade/uninstall checks passed. The bundled checks verify that the retained Hub icon matches the application icon byte for byte, and that Hungarian selection and the original installation day survive an upgrade. GUI screenshots were inspected in Hungarian and English. All game-removal execution tests used mocks.

The first bundled upgrade attempt was interrupted by an Explorer-launched test instance. The fixture was stopped and uninstalled, and the complete check passed with desktop shortcut creation disabled for that isolated test. Normal installation still creates the requested desktop shortcuts.

## 1.6.0 validation on 2026-10-18

179 automated tests passed in 61.245 seconds. All 24 GUI checks and 23 bundled install/upgrade/uninstall checks passed. Hungarian and English Hub screenshots were inspected. The packaged archive includes the new launch module. Read-only launch planning also resolved all 19 installed catalog entries on the development PC, without starting those games. Actual game execution in launch tests was mocked; launcher sign-in, updates and each game's own startup behavior remain publisher-controlled.

The desktop migration test used a temporary desktop directory. It checked a fresh shared app icon, conversion of the old Hub-folder link, removal of the old owned duplicate monitor icon, preservation of an unrelated file and removal of the integrated app shortcut during uninstall. History, hidden rows, language, installation day, unrelated startup entries and companion icon data survived the upgrade/uninstall checks.

## 2.0 Qt interface validation

The shared-controller refactor passed the existing 179 regression tests. Fourteen Qt integration tests cover card search/source/sort/keyboard selection, hide/restore versus exclusion, language/state preservation, settings validation, installation-based averages/day drilldown, real posted native tray activation, close-to-tray/Exit, existing-window Hub requests, queued launch preparation with mocked execution, removal-guide cancellation, independent topmost alerts with hidden/minimized main windows, guarded Escape/delayed delivery/presentation retry responsive 1000×700 layouts, corrupt optional-artwork recovery and pixel-level aspect-ratio checks for wide/portrait artwork. Synthetic tests never launch or uninstall real games.

Hungarian/English library, statistics and settings widget captures were inspected, including a copied local catalog and existing local artwork. The original profile was not used as a UI fixture. Real Minecraft fullscreen validation above belongs to the earlier Tk version; the Qt preview still needs a repeat gameplay trial and second-PC testing.

The final Qt suite passed all 14 cases (5.476 seconds); the existing 179-case regression suite passed after the controller refactor, and the combined 191-case run before the added image geometry case passed in 67.085 seconds. All 18 source-installation checks passed. The original 23 bundled install/upgrade/uninstall checks covered the CLI/runtime and were extended after testing the actual Qt window. The frozen archive includes Qt/controller modules and does not contain the legacy Tk UI or tkinter.

The first full Qt package exposed two issues that CLI-only installation checks could not detect: an unrelated ICU DLL collected from the build host PATH, and Windows STARTUPINFO hiding the first Qt window. Builds now isolate PATH and reject an app-local ICU runtime; Qt uses Windows 11’s system ICU. Opening the Hub explicitly restores its native window, including hidden startup launches. The standalone GUI was verified to open visibly from a background resident and reuse that process.

Bundled integration now opens the actual frozen Qt interface after a hidden/background launch, requests the existing Hub and checks graceful shutdown. Upgrade cases retire and back up only unchanged obsolete owned files, preserve edited files and reject obsolete paths escaping the application directory. This prevents old runtime DLLs from shadowing a new runtime after an upgrade.

Final packaging validation passed all 30 bundled checks, including the visible native Qt window from a hidden/background launch, single-instance Hub request, graceful stop, obsolete owned-file retirement, edited-file preservation and rejection of an escaping obsolete path. A fresh standalone GUI probe also confirmed that no app-local ICU is present. The final source-installer run passed all 18 checks.

## 2.0.1 icon scaling

All 15 Qt integration cases passed in 5.560 seconds. The added case reproduces a native Windows shell pixmap with DPR 256/96 and verifies that the icon still occupies the intended 80 logical pixels. Shell-image DPR is normalized before scaling, preserving proportions and preventing tiny icons on scaled Windows displays. The 2.0.0 packaging/startup and 30-case installer validation above remain applicable; this patch changes icon sizing only.
