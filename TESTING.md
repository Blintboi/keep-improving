# Testing

Use isolated temporary profiles and synthetic game installations. Never uninstall a real user game to test removal; mock the execution boundary.

## 2.10.0 verified account admission

All **320 application tests passed in 153.871 seconds** on CPython 3.13.16 /
OpenSSL 3.5.9. Native PKCE tests
use isolated loopback Auth fixtures and verify S256 exchange, random callback
paths, Host/Origin rejection, cancellation, sanitized provider/network failures,
redirect refusal, token whitelisting and DPAPI session/pending-code recovery.
Qt tests cover login-required creation, code-only linking, masked codes, declined
rotation, refreshed-token persistence after a deleted dialog and retention of
settings changed during a background request.

All 18 Node endpoint tests passed. The real PostgreSQL `service_role` passed
`account.sql` and `hardening.sql` transaction/rollback probes: verified provider
and live session ownership, closed/capacity/day gates, rotation/revocation,
owner quotas, bans, grants and exact storage counters. `signup.sql` checks hook
logic/column grants transactionally. Managed postgres cannot SET ROLE
supabase_auth_admin; a separate real Auth signup returned the configured hook's
403, created no Auth user and consumed no slot.

Live GitHub PKCE login succeeded with only profile/email scope, the unchanged
existing group was claimed by its verified owner, refresh and DPAPI persistence
passed, and a second temporary session was logged out then denied management.
The saved app session remained valid. The old 2.9.0 client continued encrypted
exchange with both original devices. No synthetic Auth user remains. Registration
is enabled within the ten-group/five-signup-daily/fifty-signup-total ceiling.
Email/password and anonymous providers are disabled; GitHub requires email.

Security advisors report four informational RLS-without-policy findings for
intentionally service-only tables and a password-leak-protection warning. The
latter is a paid feature on an unused/disabled email-password login path, not
GitHub password handling. See [provider guidance](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
The service is still Free and private distribution is unchanged. Tests do not
establish DDoS resistance, code signing, operator MFA or absence of unknown bugs.

The 20 source-install/upgrade/uninstall checks passed with the account modules.
The signed-in Hungarian dialog was inspected with an isolated profile. The
actual self-extracting 2.10.0 installer passed all 37 bundled install/upgrade/
uninstall checks and the RTSS helper's 10 native shared-memory checks. The
frozen archive includes Auth/account/DPAPI modules. A final documentation-only
repack is checked against the tested runtime hashes and extracted payload.


## 2.9.0 security hardening

The full **311-test** application suite passed in **143.766 seconds** on the
final CPython **3.13.16 / OpenSSL 3.5.9** runtime. Credential, cloud, snapshot and
Qt regressions cover snapshot-only legacy migration, mixed cache revisions and
unadmitted codes. Tests use temporary databases and HTTP
fixtures: DPAPI roundtrip/tamper rejection, unchanged encrypted saves, another
Windows user's credential failure, active database/WAL plaintext removal,
lossless cache/history/revision migration, `Retry-After`, backoff and recovery.

All 12 Node handler tests passed: strict schema/ciphertext, size/deadline limits,
cancelled rejected uploads, admission before allocation, credential/group
isolation, trusted-last proxy hashing, bounded cache/concurrency/retry hints and
generic errors. `sync_backend/tests/hardening.sql` passed against the actual
PostgreSQL project, rolling back admission/isolation/replay/quota/kill-switch/
pagination/retention/accounting fixtures. The hourly retention job is active.

Live HTTPS checks passed for two synthetic encrypted profiles, existing user
connectivity, unknown group rejection, no-store responses, malformed credential,
schema, ciphertext and content type. Oversized HTTP probes stalled at the
provider ingress and hit the probe's network timeout; an HTTP 413 response was
not established live. Oversize rejection/cancellation is verified locally and
no probe allocated unexpected database rows. All synthetic groups/devices were
removed; the original group, two devices, 872 ciphertext bytes and exact storage
counters remained. No load/flood test was performed against the Free project.

Supabase security advisors reported no errors/warnings; four informational
RLS-without-policy notices describe intentionally service-only tables. The new
retention index has an informational unused-index notice on this tiny database.
See [the advisor explanation](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
The pinned Python dependency audit found no known vulnerabilities; SHA-256
locked Windows wheels were downloaded and verified before building. This does
not establish absence of unknown vulnerabilities, publisher signing, operator
MFA, public onboarding or DDoS resistance. See [launch status](SECURITY.md).

The Python distribution archive was checked against the official release
manifest SHA-256 before extraction. The build rejects an older Python/OpenSSL
baseline. Source installation has 20 passing checks on the new runtime. The
standalone smoke has 37 checks, including legacy credential/cache migration in
the actual frozen GUI, with synchronization disabled on its isolated fixture.

```powershell
python -B -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File tests\install_smoke.ps1 -ReportPath test-reports\source-install.json
python -B -m unittest discover -s tests -p test_qt_ui.py -v
python -B tests/overlay_smoke.py test-reports/overlay
```

Tests cover metadata/multiple libraries, watcher races, foreground/background time, sleep/lock/clock changes, midnight, persistence, ID migration, shared budgets, alerts, native tray behavior and Hub foreign-file preservation. Windows tests use actual temporary directory notifications, process queries and mutexes.

Version 1.6 adds integrated Play preparation for Steam/Epic/Ubisoft/Riot/Minecraft and standalone games, original shortcut arguments, canonical launch-only URIs, changed-link rejection, explicit EXE persistence and transactional ID migration, stale-choice cleanup and background-worker shutdown. Real UI smoke covers search/source filters, duplicate-click suppression, queued launch execution, uninterrupted tracker identity/time, language switching and returning from Statistics to the Hub inside the same window. Game execution is mocked. A real mutex/subprocess check verifies `--hub` requests the Hub page in the existing profile instead of starting another monitor.

Version 1.4 adds hidden-row persistence/migration and independent history/tracking checks, per-game exclusions in fresh/legacy profiles, validated Steam IDs, launcher fallback, exact-root MSI selection, registry command rejection, portable-file preservation and mocked interactive uninstall execution.

Version 1.5 adds English/Hungarian language persistence and placeholder parity, translated reminders/removal guidance, strict inclusive statistics date ranges, per-game/day totals, hidden/removed/orphan history and flush/reopen accounting. Average tests cover installation-day migration/persistence, idle days since installation, custom ranges and exclusion of pre-installation/future days. GUI checks cover immediate language switching, the daily breakdown, the installation-based average, translated date errors and preservation of the selected period across language changes. The bundled upgrade checks language/installation-date preservation and retention of the Gaming Hub icon after monitor removal.

The retained legacy GUI smoke creates real Tk windows with synthetic fixtures. Inspect dark widgets, settings, hidden/minimized-root notifications, hide → Show hidden → restore, and removal guide Cancel/Close behavior. The legacy source smoke checks install/upgrade/history/startup/background-single-instance/uninstall behavior.

`tests/bundled_install_smoke.ps1` tests the standalone payload using isolated paths and uniquely named startup/Installed apps registrations, checking fresh install, upgrade, runtime diagnosis, uninstall and preservation of history/foreign files. Check real Setup extraction/launch before release, too.

The 1.6 bundled test redirects desktop shortcut creation into its own temporary Desktop fixture, exercises the old separate monitor/Hub-folder shortcut migration and checks one shared app icon and owned-shortcut removal during uninstall. It does not create test shortcuts on the user's actual desktop.

## 2.8.0 automatic RTSS for tracked games

The full 301-test suite passed in 147.148 seconds. After the final startup throttle/status refinements, all 42 RTSS, automatic-routing and overlay regressions passed in 10.086 seconds. Seven new Qt cases exercise automatic routing for Steam, Epic, Ubisoft, Minecraft, Riot, manual and custom-root games without a selected EXE, reuse of existing artwork candidates, tracking/exclusion/foreground/lock guards, missing/unhealthy renderer fallback, preview isolation and saved global mode selection. Worker tests cover cached idle preparation, helper/client rejection, no idle bridge process, one server start per throttle interval including failures, unchanged profile bytes/mtime, SDK handle cleanup, child-only inherited privileges and current renderer receipts. The bundled upgrade fixture now also preserves an explicitly disabled automatic mode and the legacy EXE list.

The installed RTSS executable's elevation manifest was inspected. Its existing SDK mapping became available after a hidden launch using the monitor's current user privileges. No game was launched or injected into for that check. Tests use temporary profiles and mocked RTSS discovery/renderers; after correcting an initially escaped synthetic `fixture.exe` profile, that file was removed and a before/after comparison confirmed the real RTSS profile directory and global settings stayed unchanged throughout the complete corrected test run. This validates routing and component startup; actual rendering in every game, API, elevated process or anti-cheat environment is not established. Incompatible renderers keep desktop/popup fallback.

## 2.7.5 sidebar cleanup

All 35 existing Qt interface and resource regressions passed in 18.088 seconds. The redundant sidebar Hide to tray button was removed. Native integration checks still exercise the main-window close action hiding the Hub, reopening from the tray, continued hidden time accounting and explicit shutdown signaling. Both user guides describe the top-right X as the way to hide the window; the production close handler is unchanged.

## 2.7.4 lower idle resource usage

The full 291-test suite passed in 123.388 seconds. After the final transient tray-update retry guard, all 13 resource/tray regressions passed in 5.423 seconds. Coverage includes foreground accounting while hidden, deferred library queries, fresh totals/statistics on show and restore, adaptive result polling with hidden synchronization, launcher refresh visibility, countdown timer activation/idle shutdown, explicit shutdown signaling and retrying failed native tooltip updates. The RTSS worker regression verifies one clear on hide, no repeated idle IPC, fresh receipts after resume and prompt shutdown. Existing alert, restriction, artwork, cloud and legacy-controller regressions also passed. Game execution/input uses isolated fixtures and mocks.

An eight-second controlled idle trial used the same three-game temporary profile, synthetic foreground samples and native Qt event loop on each version, with synchronization disabled. Routine artwork queue polls fell from 73 to 8, overlay update calls from 47 to 8, library renders from 8 to 0 and SQLite SELECTs from 24 to 8. The remaining overlay calls come from the unchanged one-second tracker; its separate fast timer is stopped. This short scheduling check establishes reduced background work in that scenario; runtime CPU and memory depend on the catalog, renderer, display and activity.

## 2.7.3 uniform large artwork and image launching

All 54 focused tests passed: 27 Qt integration tests in 11.929 seconds, 14 artwork/client tests in 3.976 seconds and 13 restriction tests in 5.830 seconds. Regressions exercise the full image as a launch button, selection-only footer clicks, double-click suppression, disabled launch targets, footer menu targeting and unchanged busy/restriction guards. Pixel checks verify equal visible size for 32- and 256-pixel icons, large square cover crops without stretching, and readable native icons after asynchronous delivery. The bounded Minecraft fixture reads both the real square pack icon and title logo without extracting any archive entry; small image decoding retains the source resolution.

Hungarian and English native library captures were inspected at 1380×920 and 1000×700 with a temporary profile containing the existing local catalog and artwork. Discovery/Hub workers were inert, tracker/overlay timers were stopped and cloud synchronization was disabled in the fixture. No real game or launcher was started, no connection code was copied into the preview and the original profile was not changed.

## 2.7.2 computer origins and stable game cards

All 58 focused tests passed: 25 Qt integration tests in 10.620 seconds and 33 statistics/cloud/translation tests in 7.506 seconds. New regressions feed actual background discovery result queues repeatedly and check that card instances, artwork, selection, keyboard focus, scroll position and grid layout remain stable. Changed metadata updates the existing card, old artwork remains visible during replacement work, new artwork is delivered to that same card, and hiding/sorting still works.

Statistics regressions retain each computer's identity and name for matching games, check period/day totals, local and remote filters, name changes, duplicate computer-name disambiguation and group isolation, and verify local budgets remain unchanged. Hungarian and English native statistics captures at 1000×700 were inspected with synthetic profiles, both for a whole period and a selected day. No real game was started and no live cloud data was changed by these tests. Synchronization payloads, encryption and the backend are unchanged.

## 2.7.1 connection-code privacy

All 54 focused tests passed: 22 Qt integration tests in 9.260 seconds and 32 statistics/cloud/translation tests in 7.230 seconds. New regressions check that existing codes open masked, copying does not reveal the code, showing and hiding are explicit, reopening starts masked, leaving or hiding the window remasks a revealed code, and generating a replacement keeps it hidden. Cancel/reopen does not change the saved connection code.

Hungarian and English native Qt captures were inspected with a synthetic code in hidden and revealed states. The code field and all three buttons fit in the linking dialog. No real connection secret or clipboard contents were used in these tests. On 2026-10-20, the user separately confirmed that linking their two computers succeeded; the privacy update preserves that existing connection.

## 2.7 code-only internet statistics

The 2.7.0 self-extracting Setup was extracted without installing, and its three contained package files matched the built payload hashes. All 35 bundled fresh-install/upgrade/uninstall smoke checks passed, including the real frozen Qt window, single-instance reopening, history/hidden-state preservation, user preferences, backups, owned-file cleanup and foreign-file retention. The separate RTSS native self-test passed ten checks. The installer includes cryptography and its pinned dependencies and upstream license texts.

Hungarian and English linking dialogs and the statistics page were rendered with native Qt fonts and inspected at the minimum supported main-window size. A transactionally rolled-back PostgreSQL probe also verified 64-bit revision precision, known-version download suppression, the 20-computer cap, the global storage cap and request-rate enforcement without retaining test writes.

275 automated tests passed in 106.945 seconds. Five additional Node tests cover the deployed Edge Function request boundary, derived group isolation, exact 64-bit revisions, malformed/oversized requests, configuration/rate/quota errors and redaction of provider failures. Native Qt regressions verify the code-only dialog, connect/disconnect, rejection of short legacy codes, opt-in upgrade migration and unchanged local budgets.

On 2026-10-20, the actual Free-plan Supabase project `jtvdbqwmejrckjejjrdl` was migrated and `statistics-sync` deployed. A live HTTPS probe with three synthetic profiles verified same-code convergence, separate-code isolation, no re-export/double-counting, stale-revision rejection, cache persistence, and rejection of weak credentials. Real Postgres role queries verified RLS on all three tables and no client table/RPC grants; both a direct table request and RPC call with the project's publishable key returned HTTP 401. Performance advisors found no findings. The security advisor reports three informational [RLS enabled without policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) entries: this is the intended deny-by-default server-only design, with the RPC executable only by `service_role`.

These are separate profiles on one physical Windows computer using the real internet backend. A second physical computer still needs the same code entered by its user. Free quotas and provider inactivity pausing remain real service limits. Live synthetic records are scoped by random group hashes and removed after verification; actual user records are not used by the probes.

### Earlier 2.6 evidence

263 automated tests passed in 99.898 seconds. After the native UI review, two further regressions were added for cancelling a background sync group and closing an already-hidden linking dialog; all 29 targeted statistics/Qt tests passed in 8.607 seconds. Isolated profiles verify two-way convergence, repeated/out-of-order snapshots, separate users sharing a parent folder, per-computer filters, unchanged local budgets, title-based manual-game matching without paths, discovery ID migration, malformed-file cache retention, offline retries, settings validation and language switching. Hungarian/English statistics at 1000×700 and the linking dialog were rendered with native Qt fonts and inspected.

No real cloud folder was selected and no game execution was used for these tests. Actual provider delivery between two physical computers remains to be checked after selecting the same private shared folder and connection code on both machines. SQLite databases remain local; only explicit opt-in statistics snapshots are exchanged.

## Fullscreen evidence

On 2026-10-18, Minecraft Java fullscreen on Windows 11 was tested with a hidden main window and isolated 20/30-second warning/limit. Alerts appeared at 20.228 and 30.392 seconds, visible/topmost and foreground after guarded Escape. The user confirmed both appeared over Minecraft. Production thresholds/history were separate.

This verifies that setup, not every exclusive fullscreen engine, display layout, privilege level or anti-cheat environment. Borderless mode may help. Do not claim universal overlays or enforced game termination.

## Before sharing

- Run relevant tests; record actual results rather than reusing an old count.
- Check fresh installation and upgrade with history, hidden rows and per-game exclusions.
- Check the frozen runtime without Python on PATH, including Qt platform/image plugins, icon and PowerShell bridge resources.
- Check startup entries, data location, uninstall and foreign-file preservation.
- Check real fullscreen gameplay using a temporary short limit; restore settings afterwards.
- Verify private visibility and absence of data/logs/installed manifests from archives.

The second physical PC, ARM64 and other games' fullscreen modes still require user testing. Preview installers are unsigned.

## 2.1 countdown validation

212 automated tests passed in 73.942 seconds. The 18 overlay tests cover opt-in legacy defaults, independent warning/expiry policies, actual tracker threshold crossing without Escape/popup/sound, retained delayed expiry popups, renderer-error fallback, shared-budget display interpolation without duplicate usage writes, hiding on process changes/other apps/exclusion/lock, hidden games/Hub, native no-focus/input flags, preview isolation, persisted placement/opacity/monitor choices, keyboard/drag placement and disconnected/negative-coordinate/small-screen fallback.

The separate `overlay_smoke.py` opt-in test passed seven checks with a real synthetic WinForms process: the visible translucent renderer retained the existing foreground, and native WindowFromPoint hit-testing through its center returned the other process's window. Normal/red timer and Hungarian settings captures were inspected. It does not force user focus or inject input. This verifies native window behavior, not real gameplay or exclusive fullscreen. The new overlay still needs a real Minecraft fullscreen/borderless trial and second-PC testing. The installer upgrade fixture also checks all overlay preferences survive.

## 2.2 voluntary play restriction

223 automated tests passed in 80.974 seconds. Eleven restriction regressions cover opt-in defaults/numeric validation, actual tracker threshold crossing, the 200 ms delay, retry throttling without repeated Escape, cancellation after focus/identity/lock/exclusion/setting changes, midnight reset, hidden games/new process identities, failed Escape/minimization, both launch boundaries, independent saved thresholds, the accessible banner/buttons and reminder conflict suppression. Native guards verify exact executable path, process creation identity and unchanged interactive foreground before requesting minimization. No real game execution or input is used by those tests.

The native smoke now passes nine checks, including actual ShowWindowAsync minimization of its separate synthetic WinForms process while that process remains alive. A fixture foreground handle is explicitly supplied for that minimization test, avoiding forced user focus; actual foreground rejection is covered separately. Hungarian settings/banner captures were inspected. This does not establish fullscreen, elevated-game, online-pause or anti-cheat compatibility. The bundled upgrade fixture checks the restriction remains disabled by default and that enabled/custom overlay and restriction settings survive upgrades. Use synthetic windows and mocked input for short-limit tests; never enable a short restriction in a fixture that discovers the user's real games.

## 2.3 launcher clients and local artwork

236 automated tests passed in 86.734 seconds. Thirteen new regressions cover client deduplication, rejection of game-specific shortcut arguments, executable-only opening and missing-client handling, background client discovery/fallback, a translated launcher page available under play restriction, artwork ranking, exact-product hashed Steam caches and standalone app IDs, bootstrapper rejection, corrupt/oversized image fallback, bounded depth/drive/reparse handling, one fixed Minecraft image entry without extraction, refresh/retired-result handling and work off the GUI thread. All client/game launch boundaries use mocks in tests.

A copied-profile preview discovered Steam, Epic, Riot, Ubisoft and Minecraft Launcher without opening any client. Its local artwork pass found an image or game icon for each of the 19 installed catalog entries. This includes the hidden redistributable/catalog entries, so it is not a claim of 19 visible game covers. Hungarian library/client and English client captures were inspected. The copy's tracker and overlay timers were stopped before processing events, and it used inert discovery/Hub fixtures; no test action affected real gameplay or shortcuts. Actual client sign-in/update behavior remains controlled by the publishers. Artwork may be unavailable in proprietary/encrypted packs and is not downloaded or fabricated.

## 2.3.1 asynchronous icon sizing correction

The user-reported tiny VALORANT icon came from the asynchronous shell-icon fallback replacing a normalized icon with an uncropped native bitmap. The actual shell bitmap was 256×256 at DPR 256/96, with the visible mark occupying only 43×43 pixels. The shared normalizer now crops transparent bounds and resets DPR for initial icons, asynchronous results and launcher cards. A regression exercises the actual result-queue path with that bitmap geometry, checks the cropped size/DPR and measures a readable card mark instead of the former tiny dot. A fresh copied-profile VALORANT card capture was inspected; no real game was started.

## 2.5 optional RTSS renderer

All 249 automated tests passed in 92.656 seconds. Ten added regressions cover per-executable opt-in, white/red ARGB text, native signed edge anchors, preservation of global/performance settings and saved position, current/stale/changed-identity receipts, absent RTSS, desktop fullscreen fallback, preview isolation and Alt-Tab cleanup. The helper's isolated native shared-memory self-test checks ten conditions: missing hook, foreign-slot preservation, reserved slot zero, renderer acknowledgement, actual render-resolution reporting, own-slot release, busy-lock skipping, foreign-lock preservation, malformed array bounds with lock release, and a dead mapping. A fresh random mapping keeps these tests independent of real games. The clock-jump restriction fixture starts at noon so running at 23:xx does not cross into the next day.

RTSS 7.3.7 was installed separately on the development PC from the official Guru3D mirror specified by Microsoft's WinGet manifest. The archive SHA-256 matched the manifest and the installer Authenticode signature was valid. SDK queries confirmed Global detection 0 and Stardew Valley detection 1. The bridge opened the real server mapping, published into its own slot and released it. The game's OpenGL hook then acknowledged OSD frames at 1920 × 1080 while Windows reported exclusive fullscreen.

The user confirmed the timer was visible in Stardew Valley exclusive fullscreen. Its initial text-coordinate placement was offset. The final renderer uses RTSS native per-game position properties, signed edge anchors and full-framebuffer coordinates instead of absolute hypertext layers. The user then confirmed the saved top-right position was correct. The title/menu screen was tested; gameplay beyond the title screen, other games and the second physical PC still need verification. No game display mode was changed. Window captures did not reliably include the RTSS text, so screenshots alone are not treated as visibility evidence. The repo/release remains private.

Hungarian/English RTSS settings captures used a copied SQLite profile, inert discovery/Hub fixtures and stopped tracker/overlay timers. Source-install and bundled-install fixtures include the compiled helper's native self-test and preservation of selected RTSS executables across upgrades. The source installer passed 20 checks and the bundled installer passed 35 checks. Each release reruns its bundled fixture against the final payload before deployment.

The bridge is built automatically from its C# source using the Windows .NET Framework 4 compiler. Run `gametime/rtss_bridge.exe --self-test` for the native fixture. Setup includes the compiled helper, with no RTSS product/SDK binaries. Source archives compile the helper during installation. No universal anti-cheat/elevated-game compatibility is claimed.

## 2.4.1 save/quit grace

All 239 automated tests passed in 88.617 seconds, including 13 restriction regressions. The threshold-crossing case verifies no Escape or minimization at 9.999 seconds, first action at ten seconds, the retained 200 ms Escape/minimize separation, and a fresh ten-second grace before a retry without repeated Escape. Other cases cover returning after focus/identity/lock changes, a stalled monitor, sleep, clock jumps, disabling the restriction, failed minimization, hidden games, new process identities and launch blocking. Time is advanced through synthetic samples; all game-input and execution boundaries remain mocked. No real game was started, minimized or closed by these tests.

## 2.4 minimal interface and text-only countdown

All 58 focused Qt, local-artwork/client, overlay and restriction tests passed in 27.900 seconds after the final card alignment and text-opacity changes. Existing persistence checks now include 100% text opacity; invalid values above 100% remain rejected. The overlay still changes color at the configured shared-budget warning threshold, preserves independent expiry popups, and uses the same input/focus guards.

The native overlay smoke passed all nine checks with its separate synthetic WinForms process. An isolated renderer check measured maximum text alpha 255 at 100% and 64 at 25%, with transparent corners and no panel pixels; white and red states were captured and inspected. Hungarian library/statistics/settings and English client/library captures were inspected, including the settled 1000×700 layout and Play aligned beside each game name. The profile preview used a database copy with inert discovery/Hub fixtures and stopped tracker/overlay timers. No real game or launcher was started, and these checks do not add real-game fullscreen evidence.

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
