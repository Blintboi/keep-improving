# Testing

Use isolated temporary profiles and synthetic game installations. Never uninstall a real user game to test removal; mock the execution boundary.

```powershell
python -B -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File tests\install_smoke.ps1 -ReportPath test-reports\source-install.json
python -B tests\gui_smoke.py --ui-only --report test-reports\gui.json
```

Tests cover metadata/multiple libraries, watcher races, foreground/background time, sleep/lock/clock changes, midnight, persistence, ID migration, shared budgets, alerts, native tray behavior and Hub foreign-file preservation. Windows tests use actual temporary directory notifications, process queries and mutexes.

Version 1.4 adds hidden-row persistence/migration and independent history/tracking checks, fresh/legacy chess policy, validated Steam IDs, launcher fallback, exact-root MSI selection, registry command rejection, portable-file preservation and mocked interactive uninstall execution.

Version 1.5 adds English/Hungarian language persistence and placeholder parity, translated reminders/removal guidance, strict inclusive statistics date ranges, per-game/day totals, hidden/removed/orphan history and flush/reopen accounting. Average tests cover installation-day migration/persistence, idle days since installation, custom ranges and exclusion of pre-installation/future days. GUI checks cover immediate language switching, the daily breakdown, the installation-based average, translated date errors and preservation of the selected period across language changes. The bundled upgrade checks language/installation-date preservation and retention of the Gaming Hub icon after monitor removal.

The GUI smoke creates real Tk windows with synthetic fixtures. Inspect dark widgets, settings, hidden/minimized-root notifications, hide → Show hidden → restore, and removal guide Cancel/Close behavior. The legacy source smoke checks install/upgrade/history/startup/background-single-instance/uninstall behavior.

`tests/bundled_install_smoke.ps1` tests the standalone payload using isolated paths and uniquely named startup/Installed apps registrations, checking fresh install, upgrade, runtime diagnosis, uninstall and preservation of history/foreign files. Check real Setup extraction/launch before release, too.

## Fullscreen evidence

On 2026-10-18, Minecraft Java fullscreen on Windows 11 was tested with a hidden main window and isolated 20/30-second warning/limit. Alerts appeared at 20.228 and 30.392 seconds, visible/topmost and foreground after guarded Escape. The user confirmed both appeared over Minecraft. Production thresholds/history were separate.

This verifies that setup, not every exclusive fullscreen engine, display layout, privilege level or anti-cheat environment. Borderless mode may help. Do not claim universal overlays or enforced game termination.

## Before sharing

- Run relevant tests; record actual results rather than reusing an old count.
- Check fresh installation and upgrade with history/hidden rows, and chess policy migration.
- Check the frozen runtime without Python on PATH, including Tk, icon and PowerShell bridge resources.
- Check startup entries, data location, uninstall and foreign-file preservation.
- Check real fullscreen gameplay using a temporary short limit; restore settings afterwards.
- Verify private visibility and absence of data/logs/installed manifests from archives.

The second physical PC, ARM64 and other games' fullscreen modes still require user testing. Preview installers are unsigned.

## 1.4.0 validation on 2026-10-18

150 automated tests passed in 58.746 seconds; 9 GUI checks, 18 legacy source-installer checks, and 14 bundled-runtime install/upgrade/uninstall checks passed. The Hub suite was rerun after its final directory-inventory change: 25 tests passed. All game-removal executions were mocked; no real games were uninstalled.

The standalone installer also preserves unrelated Windows startup values across fresh install, upgrade and uninstall. Final bootstrap was checked with paths containing spaces; the actual icon-branded Setup was installed on the development PC with its existing data.

## 1.5.0 validation on 2026-10-18

163 automated tests passed in 62.232 seconds after the installation-based average change. All 15 GUI smoke checks, 18 legacy source-installer checks and 18 bundled-runtime install/upgrade/uninstall checks passed. The bundled checks verify that the retained Hub icon matches the application icon byte for byte, and that Hungarian selection and the original installation day survive an upgrade. GUI screenshots were inspected in Hungarian and English. All game-removal execution tests used mocks.

The first bundled upgrade attempt was interrupted by an Explorer-launched test instance. The fixture was stopped and uninstalled, and the complete check passed with desktop shortcut creation disabled for that isolated test. Normal installation still creates the requested desktop shortcuts.
