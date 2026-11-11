# Testing

## 2.46.1 — opening-choice reconnect regression

- Reproduced a short desktop-connection failure in disposable Brave: the old
  fallback navigated both foreground and background choice-budget tabs to a
  cover page. Reconnecting then reloaded their original URLs.
- Offline choices now wait in the existing document. Choice-status and content
  injection failures remain local to that tab. Independent limits, focus rules
  and daily allowances retain their normal enforcement.
- 91 targeted Python tests and 77 browser unit tests passed. The real-browser
  reconnect fixture repeatedly interrupts activity, control and continuity
  requests and checks document identity, unsaved input, viewport, scroll,
  background tabs and the accepted visit token. It also exhausts the limited
  choice while retaining the unlimited choice. HU/EN waiting screens were
  inspected at wide and narrow sizes. Local-site coverage includes reconnecting
  without navigation and independent restrictions for local ports.
- The local installer passed all 102 installation/upgrade checks. The actual
  desktop and running Brave worker were upgraded to 2.46.1; history, credentials,
  settings and choice counts were preserved, and the temporarily paused rule
  was restored. Reports stay in `test-reports/session-reload/`.
- Publication uses the same tested application and extension, with updated
  bundled guides. Public installer verification and delivery evidence stay in
  `test-reports/publication-2461/`.

## Public delivery preparation — Windows 2.46.0 / Android 0.6.0

- Rewrote the main and Android READMEs as current usage guides in HU/EN.
  Sixteen current Qt captures use an offline demonstration profile with synthetic
  usage/session data. Only public game artwork metadata was reused.
- Release checks found an unnecessary snapshot revision change for idle/paused
  focus timers. Stable inactive timestamps now preserve cached ciphertext; running
  timers still carry their wall-clock anchor. A paused/resumed snapshot regression
  and the existing HTTP reuse checks pass. Focus coverage now compares timestamps
  so mixed local/aware wall-clock inputs do not fail at a completion boundary.
- Android: all 96 tests, lint, encrypted interoperability and signature checks
  passed. Upgraded the user's RMX2002 in place to 0.6.0, preserving UID and first
  installation time. Before/after encrypted USB exchange verified imported usage,
  sessions and the earlier corrected habit count; usage/protection permissions
  remain enabled. The app was opened after installation.
- Publication reports: `test-reports/publication-2460/` (kept local).
- All 1,195 distinct Python checks passed after the fixes; large Qt groups were
  run in isolated module processes. All 82 browser regressions and the ten-check
  real Brave local-website integration passed. GitHub-rendered README previews
  loaded all seven linked images without horizontal overflow at 1280/420 pixels.
- Final Windows installer: 47,874,048 bytes, SHA-256
  `52bfd423b2509ef8542ae63b4d3717271ad89ff87d6eb1b260bfa680933d17fb`.
  Source/payload audits, Defender scans, SFX extraction comparisons and 102
  isolated installer checks passed. The actual local installation was updated
  from that package after a complete profile/program backup; all 20
  preservation/version/payload checks passed after startup.

## Explicit local websites — Windows 2.46.0 local work

- Added port-specific loopback website identities, aliases, opt-in observation,
  exact local DNR rules, local tab grants and offline history. The control bridge
  stays excluded. Old extension workers receive public-only rules until reload.
- 64 distinct Python checks and 73 browser regressions passed. Coverage includes
  address normalization, private URL removal, separate ports, explicit tracking,
  continuity, compatibility and existing public-site behavior.
- Real headless Brave with disposable servers/profiles passed ten integration
  checks: native-saved local member, in-page opening choice, exhausted time limit,
  localhost/IPv6 aliases, actual DNR rules, other-port isolation, unconfigured-port
  exclusion, bridge exclusion and restoration of the original URL.
- Native picker renders at 720/820 pixels in HU/EN and the browser choice overlay
  were inspected. Alias deduplication, separate ports and native save passed.
  Reports: `test-reports/local-websites/`. Local delivery only.
- Installer: 47,824,896 bytes, SHA-256
  `35930ef2b025af15c1d7e30fc08056172be06447bdfdcd24f96332447aaed8ca`.
  Source/payload audits, Defender scans, extraction hashes and all 102 isolated
  installer checks passed, including local-port preservation. Installed locally
  after a complete profile/program backup; all 20 preservation/version/payload
  checks passed and the updated Hub opened at 1396×959. Public downloads unchanged.

## Break action placement — Windows 2.45.1 local work

- Removed the floating HUD companion window. The action is in native and
  extension budget rows; the extension popup and tray action remain available.
  The saved opt-in is preserved and no longer mentions the countdown.
- 61 Python checks and 69 browser regressions passed. Native integration covers
  starting after leaving the target application, disabling during the break,
  retaining row widgets and avoiding refreshes while hidden. The HUD creates no
  extra top-level window. Existing full-break/renewal behavior remains covered.
- Real headless Brave checked both popup and budget-list actions, full break,
  renewed usage interval, preserved daily allowance and the editor checkbox.
  Native HU/EN renders at 1000/1280 pixels and browser row layout were inspected.
- Reports: `test-reports/break-placement/`. Local delivery only.
- Installer: 47,820,800 bytes, SHA-256
  `8d37a9d4d80fee27ebc2e65412f8eb45af17e3eb3e6e45850977dc53324f44da`.
  Source/payload audits, Defender scans, extraction hashes and all 101 isolated
  installer checks passed. Installed locally after a full profile/program backup;
  all 20 preservation/version/payload checks passed and the updated Hub was opened.
  Public download hashes remained unchanged.

## Early breaks — Windows 2.45.0 local work

- Optional usage-time break setting, countdown companion button, browser popup
  action and tray action. Full configured breaks renew their own usage interval;
  daily allowance and recorded usage are preserved. Restart and day renewal,
  disabled/stale actions, existing restrictions and mixed targets are covered.
- 153 distinct targeted Python checks and 69 browser regressions passed. The
  real headless Brave integration uses disposable profiles and verifies the
  authenticated popup action, full five-minute break, website restriction policy,
  fresh fifteen-minute interval, preserved daily allowance and editor opt-in.
- Native HU/EN layouts at 1000/1280 pixels and the 380-pixel browser popup were
  inspected using own-widget renders and headless screenshots. The HUD remains
  click-through; only its companion button accepts input without activation.
- Local reports: `test-reports/early-break/`. No public download changes.
- Verified installer: 47,820,800 bytes, SHA-256
  `d108e22d84115cf56603fbf37afbdb48548d21ba7e04a17e7321d5d2bc8f9ebd`.
  Source/payload audits, Defender scans, SFX extraction/hash checks and all 101
  isolated installation checks passed, including early-break opt-in preservation.
  Installed locally on 2026-11-11 after a complete profile/program backup. All 20
  data/settings/version/payload checks passed both before and after restart;
  the updated installed Hub was observed open. Public installer/manifest hashes
  remained unchanged.

## Member selection and website choices — Windows 2.44.1 local work

- 124 targeted Python checks passed, including the detached-window regression,
  preserving maximized targets, browser choice idempotency and shared ledger,
  allowance exhaustion, native/website routing and existing budget actions.
- Live selected members were checked in HU at 720×650 and EN at 820×650,
  including filtering, removing a hidden match, adding a custom site and applying.
- The headless real-Brave integration uses a local synthetic website and a
  disposable desktop/browser profile. It verifies unchanged viewport, scroll,
  URL and unsaved input after acceptance; two allowed visits, disabled depleted
  choice and continued unlimited access. HU/EN captures were inspected.
- Reports are in `test-reports/member-selection/`. Public downloads are unchanged.
- 55 bridge/focus/continuity checks and 48 browser regressions passed. Browser
  worker recovery retains the active visit and removes stale overlays; same-domain
  tabs share a visit, and private tabs and stale/subframe choices are rejected.
- Final installer: 47,812,608 bytes, SHA-256
  `cbc415d6990702b9c97304e5d1adc708151896aca771662b5327d50e9bdbbe87`.
  Source/payload audits, Defender scans, SFX extraction/hash checks and all 100
  isolated installer checks passed. Installed locally on 2026-11-11 after a full
  profile/program backup; all 20 preservation/version/payload checks passed.
  Config matched exactly immediately after setup; after startup the only additions
  were explicit all-days/global-renewal metadata, preserving the prior behavior.
  The updated installed Hub was observed open. No publication or security exclusion.

## Opening choices — Windows 2.44.0 local work

- 172 targeted Python checks passed, including choice validation, two-use
  exhaustion, unlimited answers, idempotency, restart, renewal, renaming,
  identity remapping, normal-limit priority, native scope and editor roundtrip.
- 54 browser model/background/blocked-page checks passed. An offline choice
  step requests the desktop rather than consuming aggregate session counts.
- Native interaction used a disposable profile and `FixtureRestriction.exe`:
  two accepted limited visits were recorded; the exhausted answer is disabled
  while the unlimited answer still restores the target. Test artifacts are in
  `test-reports/session-choices/`. Public download files remain unchanged.
- After the focus-recovery and rendering fixes, 28 affected checks and the final
  12 choice checks passed. The real Brave extension integration passed, including
  editing/saving the opening question and per-answer allowance. HU/EN native
  forms and enabled/exhausted choices were visually checked.
- The subsequent shared/per-member option passed all 16 dedicated choice
  checks, including two website allowances, mixed member aggregation, switching
  modes without resetting history, subdomain identity and schema migration. The
  real browser integration was rerun with the separate allowance selected.
- Final scoped installer: 47,800,320 bytes, SHA-256
  `c98a5b440a8d61fc513ed443b3e3ec1bd035e190e26096a02dcdfe0c36746aa7`.
  Source/payload secret audits, Defender scans, actual SFX extraction and all
  100 isolated installer checks passed. Version 2.44.0 was installed locally
  on 2026-11-11 after a full profile/program backup. All 18 preservation,
  version and complete installed-payload checks passed again after startup;
  the updated Hub was observed open. No Defender exceptions or public upload.

## Daily session limits — Windows 2.43.0 / Android 0.6.0 local work

- Budgets replaces Time budgets / Keretek replaces Időkeretek. Action timing
  accepts daily session counts (1–10000); five sessions are allowed and the sixth
  triggers warning, restriction or break. Repeating breaks rearm after the same
  number of new measured visits, and counters follow each budget's renewal.
- Local measured ledgers include pending samples and deduplicate overlapping
  app/game/site representations. Origin-owned shared counts are synchronized
  without re-exporting remote counts. Browser fallback retains session counts
  and the current visit across handoff, restart and renewal.
- 100 targeted Python checks, 17 browser-model checks, real browser save/navigation
  flows and 96 Android tests passed. Android lint, ciphertext interoperability
  and APK signer checks passed. HU/EN Windows and phone forms were inspected.
- On 2026-11-11 the corrected matching-source Windows installer passed source
  secret auditing, frozen-payload and installer Defender scans, verified SFX
  extraction and all 100 isolated installation/upgrade/uninstall checks. Defender
  intelligence was 1.463.236.0, with protection enabled and no new exclusions.
  The user's actual installation was upgraded to 2.43.0 after a consistent profile
  backup and a separate copy of the old program. All 17 preservation/version/hash
  checks passed; the updated native Hub opened and its resident process remained
  running. The earlier Microsoft submissions do not constitute clearance.
- Android 0.6.0 APK is verified but not installed: the user requested a computer-only
  upgrade and deferred the phone. Public downloads and GitHub are unchanged.

Follow-up on 2026-11-10: the user confirmed five allowed visits / action on the
sixth and requested a computer-only upgrade. Defender security intelligence was
updated from 1.463.222.0 to 1.463.223.0. The unchanged installer then passed fresh
installation, diagnostic execution, GUI launch and shutdown, but the later
legacy-upgrade fixture was blocked by the same behavior detection. The test also
found an extension-version mismatch; manifest 2.43.0 and the remaining old budget
wording were corrected in source. Repacking stopped at the Defender gate because
the frozen executable was now blocked on read. The previous installer remains an
analysis sample, not a verified delivery. The user explicitly approved Microsoft
review; the exact tested installer and the prepared description (shortened to the
portal's 1900-character limit) were submitted on 2026-11-10. Microsoft confirmed
submission `ec09a622-099d-4e1a-9244-5fd7a084650c`; its final determination is Pending,
with no analyst comments yet. Details are at
https://www.microsoft.com/en-us/wdsi/submission/ec09a622-099d-4e1a-9244-5fd7a084650c
and in `test-reports/session-limits/microsoft-review.json`.
No user installation was changed, and the phone upgrade is deferred at
the user's request. Removing the failed fixture's own startup registrations and
shortcuts was rejected by automatic policy review; that command did not execute.
A subsequent read-only inspection confirmed that the test autorun, legacy Startup
shortcut and uninstall registration were already absent after Defender remediation.

Further check on 2026-11-10: refreshing the Microsoft submission revealed a
Completed case. The analyst found no positive scan or telemetry indicators and
requested current security intelligence plus Defender diagnostic data if local
detection continued; this did not resolve the runtime issue. The unchanged
installer was retested with intelligence 1.463.226.0, then 1.463.227.0 obtained
directly from MMPC. Both isolated tests reached diagnostics but GUI launch was
blocked as `Trojan:Script/Conteban.A!ml`. See
`installer-after-microsoft-review.json`, `installer-after-mmpc-227.json`, and the
matching Defender event reports. Protection stayed enabled and the actual
2.42.3 installation kept running. No arbitrary rebuild or quarantined-file
restore was attempted. The user authorized elevated local collection of the
Microsoft-requested support diagnostics. The user then gave separate informed
consent to upload the 21,539,067-byte archive and the supplementary description
to Microsoft. The follow-up references the original submission and requests
removal on 2026-12-11. After the user completed the CAPTCHA and clicked Submit,
Microsoft confirmed receipt as `1dab8fac-83d8-4b98-affb-de4399611f57` at the displayed
time Nov 10, 2026 16:44:27. Case status is Submitted; final determination is Pending.
The private archive and confirmation screenshot remain outside the repository.
At that point the runtime block was unresolved, so the actual upgrade was withheld.

Local delivery on 2026-11-11: the user explicitly authorized an application-specific
Defender workaround. Before applying any exception, a fresh build incorporated the
pending extension/version corrections and passed the full installer checks with
the current Defender intelligence. No security settings were changed, no file was
restored from quarantine, and no exception was needed. This observation does not
isolate whether the changed artifact or the newer intelligence resolved the block.
The original submitted installer remains intact for provenance. The verified local
installer is `dist/session-limits-local-20261111/GameTimeMonitor-2.43.0-Setup.exe`;
its size is 47,771,648 bytes and SHA-256 is
`feeb3c23f214b9313cdf4b4041e085e77b0960ff0d53150eefb736c939f730de`.
See `installer-20261111.json`, `installer-provenance-20261111.json` and `upgrade.json`
under `test-reports/session-limits/`. The installer test accepts an optional fresh
fixture directory within TEMP, making the tested executable path explicit while
retaining the existing scan and cleanup checks. No publication was performed.

Evidence and artifact hashes: `test-reports/session-limits/upgrade.json`,
`installer.json`, and `defender-runtime-block.json`.

## Plain measured counts — local Windows 2.42.3 / Android 0.5.3

All session totals, tables, charts, legends and tooltips show the recorded count
as a plain number, including older history. Zero recorded sessions display as 0
and sort numerically. Coverage metadata and the counting/synchronization logic
remain unchanged. Existing desktop, browser-model and Android fixtures exercise
the revised formatting with partial history and HU/EN layouts. The Windows
installer is verified with a temporary profile before the local profile upgrade.

Android also retains the scroll container during refresh and anchors overview
positions to stable section identities. A reproduced regression moved the chart
635 pixels when a synced focus card appeared above it; appearance and removal
now preserve its screen position. Regression checks cover scrolling momentum,
chart filters, live totals, navigation and activity recreation. Refresh startup
keeps an already loaded overview usable instead of rebuilding it for a temporary
loading indicator.

## Selectable chart measure — local Windows 2.42.2 / Android 0.5.2

The existing Show activity list selects both category and time/session measure.
Column and segment heights, scales and labels follow the chosen measure; the
choice survives restart. Hover details retain original time and session counts.
Older empty days do not mark later fully tracked activities as partial. Actual
usage on the first tracking day or earlier, and legacy devices without counts,
retain the conservative ≥/— notation. No historical counts are inferred from
accumulated time. Tests verify geometric ratios, switching and persistence,
category/device filters, complete/partial counts and HU/EN screenshots in
desktop, real browser and Android. Delivery uses temporary installer profiles,
profile backups and verified in-place local upgrades.

## Session boundaries and charts — local Windows 2.42.1 / Android 0.5.1

Android activity pause/resume callbacks inside one package no longer split an
application session when the OS records an immediate internal transition. A
different foreground package, screen lock/off, reboot, covered interval or an
unexplained gap still separates sessions. The ordinary foreground-session rule
is unchanged. On first collection, retained OS events from the last three days
repair matching old boundaries; the original session rows remain in a local
backup table. Usage time, budgets and history are never replayed by this repair.

The desktop, browser and phone charts show daily session counts. Desktop blocks
also expose activity/device counts on hover, with compact labels where space
permits. Phone blocks and legends include counts. Missing/partial historical
counts keep the existing —/≥ notation and sessions belong to their starting day.

Regression fixtures reproduce 62 internal screens, real app switches, collection
boundaries/restarts, lock/shutdown and covered intervals. An upgrade fixture
checks historical correction without recrediting usage. Chart checks cover
separate activities/devices/dates, partial counts and HU/EN layouts. All fixtures
use temporary profiles; installers and real profile upgrades are verified before
local delivery. No public downloads or GitHub publication are changed.

## Activity sessions — local Windows 2.42.0 / Android 0.5.0

Statistics show per-activity and total session counts, with ascending/descending
sorting by count or time. A session is connected measured foreground use;
switching away and returning starts another. Counts belong to the starting day.
Daily rollover, periodic flushes and browser recovery do not duplicate sessions.
Legacy history is unknown (—); a selection crossing the first measured day or an
older device shows a lower bound (≥). Daily counts use the existing encrypted
snapshot; interval timestamps remain local. No backend/schema/plan change.

- 191 focused Python tests passed (8 session-ledger, 25 statistics UI, 18 sync,
  18 focus, 21 browser control, 13 statistics/i18n, 19 renewal, 53 core and 16
  browser continuity), plus 4 JavaScript statistics-model tests.
- 82 Android tests, lint, APK signature and encrypted interoperability passed.
  Migration tests preserve versions 1/2/5 profiles; new session tests cover
  midnight, replay, covered intervals, old counts, categories and numeric sorting.
- Real Brave with a disposable browser/profile passed statistics/device/category
  filtering and numeric session sorting. Synthetic data is isolated from actual
  foreground sampling. Native desktop, browser and phone HU/EN screenshots at
  representative sizes were inspected (`test-reports/sessions/` and Android's
  local build UI reports).
- Windows source, frozen payload and installer audits/static Defender scans
  passed; the extracted installer passed all 100 runtime checks. No Defender
  1116/1117 events appeared during this verification or the real local upgrade.
- Windows 2.42.0 was installed over the actual 2.41.1 installation and reopened.
  A consistent SQLite backup and installer's own backup were retained. Integrity,
  game/app history, focus completions, settings, tracking rules, game exclusions
  and synchronization credential presence were checked after upgrading.
- Android 0.5.0 (code 10) was installed in place on RMX2002 and started. Its UID
  and original installation timestamp remained unchanged; no crash was logged.
  The phone was locked, so visual checks used isolated representative UI fixtures.
- No GitHub push or public download replacement. Local installer SHA-256:
  `401dace454500d820bd1874c3140f5be63ab46159a7ed392fbd33d8f470e3824`.
  Local APK SHA-256:
  `141d40d5895ec4ffdccfdd6f4921bb5c12f651dab2ca1588d152e5e0bd430ee9`.

## Statistics colors — local Windows 2.41.2 / Android 0.4.5

Applications use a canonical executable basename for color assignment, so versioned
installation directories keep the same color. Website www aliases share a color.
Windows stores assignments locally across restarts; the browser statistics use the
same desktop allocator. Android migrates existing colors without deleting their
preferences and combines matching app versions in its chart/ranking, preserving
all recorded time. Devices and different activity types retain separate identities.

- 24 Windows statistics usability tests passed, including two dates/different app
  paths, unchanged totals, alias colors and persisted assignments.
- 78 Android tests, lint, encrypted protocol interoperability and APK signature
  checks passed. HU/EN screenshots at representative desktop/phone sizes were
  inspected. Android 0.4.5 was installed in place on RMX2002; the original install
  timestamp and profile were retained.
- Windows 2.41.2 source/payload/static Defender checks passed, but the actual
  isolated installer runtime was blocked by `Behavior:Win32/Persistence.A!ml` at
  16:12–16:13 on 2026-11-05. Unlike the previous corrected builds, this test did
  not pass. The working real 2.41.1 installation was not updated. No exclusions,
  quarantine restoration or Defender setting changes were made. Investigation
  evidence and installer SHA-256 are under `test-reports/stable-colors/`.

No public download or GitHub publication was changed.

## Local 2.41.1 / Android 0.4.4 — responsive companion and navigation

- Python checks: Qt UI 50, responsive sync/exclusions/focus/paired startup 4, activity library 12,
  focus 18, companion 11, statistics transport 12, statistics sync 18 and browser
  control 21 passed. Node blocked-page/restriction checks: 35 passed.
- Android: 75 tests, lint, ciphertext interoperability and APK signer verification
  passed. Installed 0.4.4 over the real 0.4.3/0.4.2 profile on the USB-connected
  RMX2002; first-install timestamp, pairing and history remained intact.
- Real phone: Settings Back returns to Overview; compact menu and aligned header;
  Settings/Notifications buttons absent from Overview. USB exchange delivered
  today's existing PC completion (displayed as 1) and cached remote website icons.
  Cloud sync also succeeded against the existing Game Monitor project.
- HU/EN screenshots checked for excluded-app restore controls and the blocked
  website screen without any saving allowance. No misleading allowance/footer
  text remains. Remote focus tests cover elapsed, paused, finished and stop states.
- The quota SQL fixture passed in rollback transactions before the applied policy
  migrations. Owner accounting and server-only RPC grants were preserved; the
  existing account accepted requests beyond the retired 20/day allowance.

The first Windows installer passed static Defender/source/payload scans, but its
isolated runtime installation triggered `Behavior:Win32/Persistence.A!ml` at
12:15 on 2026-11-05. Defender quarantined only the temporary fixture executable
and its startup registrations. The real Windows installation remained 2.40.4.
This runtime result invalidates that installer test; a clean static scan alone
is not sufficient. No exclusions or protection changes were made. Setup now
uses one Run entry and retires its own redundant Startup-folder shortcut, with a
backup and ownership checks. The rebuilt 2.41.0 installer passed all 100 isolated install/upgrade checks and had
no new Defender detection. The real profile then exposed an initialization-order
error with an existing browser pairing. Version 2.41.1 initializes shutdown state
before enabling that bridge; both unit and bundled upgrade fixtures now cover a
paired browser. All real profile integrity/settings/history checks passed.
The final 2.41.1 installer passed all 100 bundled install/upgrade checks,
including the pre-existing pairing fixture. It was installed over the real profile
and restarted successfully. Integrity, existing settings, focus settings, pairing,
per-game preferences/exclusions and usage/focus history all passed the before/after
comparison. The server confirmed two recently synchronized devices. Defender
real-time and behavior protection remained enabled, with no new detection during
the two corrected installer tests or real upgrades. This does not retroactively
certify the first behavioral alert as a false positive.

Local evidence is under `test-reports/companion-241/`; no public files were updated.

## Android 0.4.2 — unified rules and settings navigation

The phone and PC budgets/notifications now share their respective feature pages.
Device labels and filters preserve rule ownership; shared IDs collapse multiple
copies without merging independent rules that happen to have the same name or
native ID. Tombstones suppress stale remote copies. Lists render at most 40 rules
at once, with Show more. PC editor saves still queue a command for the exact PC.

Synchronization, connection management and device groups are in Settings.
General/focus PC settings and delivery status remain under Linked devices there.
The hamburger menu has six entries; legacy links to Computers open Settings.
Temporary-profile tests cover these paths, shared-rule deduplication, targeted
editing, unchanged local rules, saved filters and retained scroll positions.
HU/EN native captures use 393 × 851 and 320 × 640 logical pixels.

Main pages use concise labels; optional measurement, privacy and synchronization
details open separately. Accessibility consent remains before permission setup.
Nested PC settings open one level at a time, with 40-item pagination instead of
a flattened text dump. A temporary-profile test opens the 45th entry, checks its
value, and returns to the preserved list.

Local verification: 68 Android tests pass, lint passes, encrypted Android/Python
interchange passes, and the APK verifies with the existing signing certificate.
The signed 0.4.2 (code 6) was installed with `adb install -r` on the connected
Realme RMX2002. The original first-install timestamp, connection and measurement
setting remain; the updated Hungarian Settings screen was checked on-device.
No public download was replaced.

## 2.40.4 / Android 0.4.1 — scroll position and visible local usage

Android checks cover chart selection, consecutive redraws before layout, page
navigation, activity recreation and fresh local usage appearing without moving
the page. Hidden activities do not run the visible refresh. The full Android
suite, lint, APK signature and encrypted Python/Android interchange are checked
by `android/build.ps1`.

Desktop regression cases retain the budget/notification list position after
edits and toggles, activity list selection after refresh, and the chart position
when choosing a day. `tests/browser_panel_smoke.cjs --scroll` uses isolated Brave
and desktop profiles to check selections, asynchronous refresh and returning to
a page at 1000- and 600-pixel widths. Add `--language` for HU/EN visual checks.
Usage refreshes every 15 seconds only while the relevant Android page is visible;
it does not request cloud sync or scan the installed app catalog.

Local delivery passed 57 desktop regressions, 64 Android tests and 98 extracted
installer checks. The Realme RMX2002 kept the chart at the same position after
changing its coloring; a 65-second calculator trial changed today's measured
usage from 22 to 23 minutes without moving the page on return. Android 0.4.1
was installed with the original signing key and `adb install -r`. Windows
2.40.4 was installed into the real local installation and verified running in
the background, with profile settings, credentials, history and usage preserved.
Two encrypted USB exchanges succeeded. HU/EN native screenshots and isolated
Brave checks are under ignored `test-reports/scroll-*`; this is local delivery.

## 2.40.3 — upgrades restart in the background

Upgrades restart the existing installation with `--background`, retaining startup
notifications without opening a Hub behind them. Fresh installations still open
the Hub. Temporary-profile notification checks cover editing durations, starting
focus, closing and Escape with a hidden/minimized Hub. The installer smoke check
also verifies the restarted resident's background launch and graceful shutdown.

## 2.40.2 / Android 0.4.0 — local shared rules and managed updates

Shared-rule checks cover device/group selection, origin-only counters, repeated
imports, edits and deletion, stale drafts, custom daily renewal, covered time,
and Python/Android encrypted interchange. Preferences keep unchanged snapshots
free of database writes. Desktop selectors are rendered in Hungarian at
1000 × 700 and English at 1280 × 850 with disposable profiles.

Android tests exercise the single ongoing budget notification in both running
and paused states; its countdown uses the system chronometer. The APK build
runs the Java/Robolectric suite, lint and persistent signing-key verification.
Shared totals use the last successful exchange while offline; they are not an
online reservation service and simultaneous disconnected use can exceed a cap.

Updater checks cover truncated/oversized/invalid downloads, checksum mismatch,
cancellation, HTTPS redirect restrictions, verified cache reuse, unsaved drafts,
and failed installer startup without closing the app. The bundled installer
smoke test upgrades a running resident in an isolated installation, retains its
custom profile without a repeated DataDir argument, and verifies history and
runtime file preservation. Public download files remain unchanged.

## 2.40.0 browser continuity without duplicate accounting — local verification

The paired extension keeps browser usage, Pomodoro and web budget enforcement
working while the desktop is stopped. Durable ordered records and native
coverage intervals reconcile missing time once; mixed browser/site groups also
count once. Timer generations reject stale controls. Receipt and counter writes
commit together, including completion and warning/break state. A failed local
storage write rolls back controls and one-time allowances.

The 67 focused Python checks, 107 additional regressions and 60 JavaScript checks pass. Coverage includes
lost replies, repeated batches, multiple streams, large catch-up, transaction
rollback, native overlap, midnight, lock/private exclusions, timer completion,
stale commands, chunk persistence and storage failures. Additional restriction,
control and budget tests are recorded under `test-reports/browser-continuity-2400/`.

A real Brave test uses isolated browser and desktop profiles: stop the desktop,
finish a Pomodoro and enforce a website limit, restart the extension worker,
use offline start/pause, restart the desktop, then replay the imported batch.
Totals and completed rounds stay unchanged on replay. HU/EN offline panels are
visually checked at 1000 × 700 and 1280 × 850. The full existing panel/popup smoke
also passes navigation, drafts, timers, hidden-idle and reconnect checks.
Public download artifacts remain unchanged pending a publication request.

## 2.39.36 dismiss a notification after starting Pomodoro — local verification

Successful Pomodoro actions close their source notification immediately and release the popup slot while the timer continues with the selected timing and existing blacklist. An already-running timer, invalid duration or save failure leaves the notification and its error visible for correction. Application-launch actions retain their current behavior.

All 43 notification-rule, scheduled-notification, single-session and focus tests pass. Temporary-profile mouse-click checks also cover error recovery, a following notification and Hungarian/English captures at 1000 × 700 and 1280 × 850. Evidence is under ignored `test-reports/pomodoro-dismiss-23936/`. Public download artifacts remain unchanged.

## 2.39.35 browser language menu and stable switching — local verification

The language menu uses bundled HU/EN flag images in both the trigger and options, with keyboard selection, selected-state semantics, Escape/outside-click dismissal and viewport-aware opening direction. Selecting the active language does not write settings; failed saves restore the saved selection. Language changes preserve scrolling, keep drafts, and serialize against live polling/stale state responses.

Statistics reuse a bounded, pairing-scoped cache while refreshing, and period changes keep the old result until its replacement arrives. Game artwork also reuses bounded thumbnails across language/tab changes. Temporary-profile Brave checks delay responses and sample every animation frame to verify statistics/artwork do not disappear during switches; late responses cannot overwrite another page. Both languages and 760/1000/1280-pixel widths are captured under ignored `test-reports/language-picker-23935/`. Public Windows/Android downloads are unchanged.

## Android 0.1.0 — local preview, 2026-11-03

The independently versioned Android app builds as a locally signed, non-debuggable APK (minimum API 26, target/compile API 36). All 18 Java/Robolectric tests pass: foreground switches, late pauses, screen lock/off, unexpected restart, midnight/DST, checkpoint deduplication, permission revocation, paused/locked collection, SQLite reopen, bounded/authenticated cross-runtime encryption, validation, browser/site deduplication and a phone plus two independent desktop devices. HU/EN native graphics were inspected at 393 × 851 and 320 × 640 dp. Android lint reports zero errors; three notices concern newer available build/test dependencies.

Python decrypts the Java export and imports an actual Android PhoneStore snapshot into a disposable desktop database. Repeated imports do not add time, and imported time never enters a local upload. Tests use synthetic connection codes and do not call the live statistics endpoint or read the user's profile. The existing backend and Windows installation are unchanged.

APK v2 signing verifies with the persistent private local RSA-3072 key. The copied `dist/KeepImproving-Android-0.1.0.apk` is 50,610 bytes, SHA-256 `a840ed50590ac33ccc3ed28b946658aa70566f3187f993bd281b08bd5965a532`; its adjacent checksum matches. Packaging confirms the expected application ID, version, launch activity, permissions, disabled cleartext and backup, with no debuggable flag. Evidence and UI renders are under ignored `test-reports/android-010/`.

No physical phone was attached. Hardware emulator acceleration is unavailable and software emulation failed; runtime UI/API/storage checks use Robolectric, not a booted emulator. Actual-phone installation, Android Keystore behavior, live phone-to-service exchange and manufacturer background scheduling remain device acceptance checks. No public APK/GitHub delivery was performed.

## 2.39.34 browser activity icons and budget save visibility — local verification

Application and website images use the existing desktop icon provider and favicon cache in the browser's activity lists, focus lists, budget members and selectors. Custom notification images are projected from saved notification definitions. Requests accept known identities only, resolve executable paths from local inventory, and return bounded thumbnails. Visible browser views have separate five-second loading leases, so a hidden Hub does not stop an open browser view; hidden/closed browser views release pending work. Icon requests and in-memory caches are bounded, and reads do not launch applications or change user settings.

The native budget overview shows Save changes only for an unapplied draft. Editors retain their save action, and deletions/enabling remain explicit draft changes. Isolated tests cover hidden-Hub loading, cached images, unknown identities, separate browser leases, cancellation, draft visibility and shared-budget values matching the desktop configuration. Real Brave checks cover decoded app/site icons, focus and budget rows, selectors, both languages, hidden-view idling and the existing dashboard flows. Installer and profile-preservation evidence is under ignored `test-reports/activity-icons-23934/`.

## 2.39.33 popup focus shortcut — local verification

The current-website card omits “Block during focus” when the desktop focus list already covers the domain, a parent domain, a selected website group or all websites. Adding a site hides the action after the save succeeds; removing its coverage makes it available again on the normal revision refresh. Read-only effective rules come from the existing desktop focus model. The website and budget shortcut remain visible. Temporary-profile browser captures and installer/profile-preservation evidence are under ignored `test-reports/popup-focus-23933/`.

## 2.39.32 browser statistics and library — local verification

Browser statistics default to all linked computers and preserve each computer's daily segments, names, aliases and desktop colors. The detail list includes computer/type columns, independent computer filtering and optional matching-name grouping. Website-only queries use the desktop category; imported-history revisions invalidate cached reports. Tiny activities retain proportional height without a minimum pixel per entry.

The library uses current discovery metadata and the desktop's installed-or-used-today visibility rule. Retired records remain available to history, while separate installed copies show their source. Artwork batches accept known historical games so one retired entry cannot reject all visible images. Image retries remain bounded and stop when hidden.

Temporary-profile checks compare all four statistics categories and both computer scopes against the native report, exercise mixed current/retired image batches, and run real Brave with two computers, forty tiny activities, a retired duplicate and decoded images. HU/EN captures at 1000/1280 pixels and installer/profile-preservation evidence are under ignored `test-reports/statistics-library-23932/`. No publication is part of this local delivery.

## 2.39.31 centralized settings and browser pairing — local verification

General activity measurement, fullscreen display, RTSS detail and game-folder settings live in Settings. The other pages omit repeated settings shortcuts; computer linking remains on the Statistics main page. Measurement edits support save/cancel and retain history. Display permissions retain their explicit confirmation and immediate revocation. Browser permission changes keep a settings draft's revision guard and do not discard other unsaved fields. The browser linking page returns to Statistics and retains input during background refresh.

The real Brave test starts with an unpaired disposable profile and follows the README flow from the popup, pasting the temporary desktop pairing code into the connection form. It verifies persisted pairing, bidirectional controls, settings navigation, linking return and drafts, display-permission cancellation and revocation, and live timers. Native settings, navigation, display, notification, statistics, activity and browser-control checks use temporary profiles. HU/EN visual and installer/upgrade evidence is under ignored `test-reports/settings-navigation-23931/`.

## 2.39.30 simpler popup — local verification

Removed the explanatory ordering caption above the live popup timers in both languages. The existing disposable-profile browser checks and HU/EN captures cover countdown behavior and layout. Installer and profile-preserving local upgrade evidence is stored under ignored `test-reports/popup-caption-23930/`.

## 2.39.29 live popup timers — local verification

The extension popup shows all relevant non-focus timers, earliest event first, with restriction precedence for equal deadlines. Focus retains its separate controls. The popup refreshes names, event labels, remaining time and secondary budget text from the lightweight live API while open. Unchanged controls and timer cards are reused; hidden popups stop polling, and disconnected popups clear stale timers and reconnect automatically. Live projections use the current wall clock even when the last foreground sample is older.

Temporary-profile browser-control tests cover fresh timestamps and translated timer payloads. The real Brave dashboard/popup test checks multiple timers, ticking without DOM replacement or full-state reads, reordered events, running breaks, save allowances, zero-time restrictions, inactive usage budgets, timer removal, hidden polling suspension and reconnect. Hungarian and English popup captures cover 380- and 340-pixel widths, including a scrolling multi-timer layout. Installer and local profile-preserving upgrade evidence is stored under ignored `test-reports/popup-timers-23929/`.

## 2.39.28 desktop and browser visual consistency — local verification

The browser dashboard follows the desktop navigation, typography, colors, activity cards, statistics, budget rows, notification rows, compact focus controls and four settings sections. The Settings item and language selector sit at the bottom of the sidebar. The one-click popup remains available; the worker clears legacy toolbar badge text even while offline or unpaired. Game artwork is requested only for visible cards, restricted to catalog IDs and bounded batches, cached at thumbnail resolution, and cancelled on navigation or hidden tabs. Visible activity counts refresh without rebuilding cards.

All 35 focused Python checks and 34 JavaScript checks passed. They cover notification controls and actions, local browser authentication and edits, game-quota summaries, bounded catalog-only artwork, restriction recovery and automatic upgrades. Real Brave tests use disposable desktop and browser profiles and verify populated statistics, navigation, creation and saving, zero-break focus, drafts and language switching. Automatic dashboard and covered-page restoration passed in a disposable browser.

Native pages and browser pages were visually compared in Hungarian and English at 1280 × 850 and 1000 × 700. The native notification icon picker now has equal-width, full-row choices and a compact custom-image button; the browser picker uses the same arrangement. Installer and local-upgrade verification are recorded under ignored `test-reports/extension-parity-23928/`. Public download files and README release headers remain on the published version until publication is requested.

The verified 2.39.28 installer passed all 92 temporary-profile install/upgrade checks and the 22-check RTSS self-test. Extraction verified all 310 packaged files. The local upgrade preserved all 21 database tables and settings, verified the installed payload, and reopened the Hub. Brave registered and started the updated 2.39.28 worker automatically. Installer SHA-256: `4857e50ed397c40249524c7ac6ffd04c773837357ce594dcd8e38796896e8e90`.

## 2.39.27 browser dashboard — 2026-11-02

Sixteen temporary-profile control tests cover the authenticated loopback API, extension-origin and host checks, body limits, GUI-thread dispatch, conflict detection, idempotent commands, atomic validation, full-path activity exclusions, budget and notification CRUD, zero-break focus sessions, local icon uploads and explicit application/removal actions. Account sessions remain redacted, reads and previews do not launch applications, native unsaved settings survive, and existing desktop forms reload after browser saves.

The real Brave dashboard test uses a disposable browser and desktop profile. It verifies HU/EN navigation and layouts at 1280 × 850 and 1000 × 700, populated seven-day/today statistics, budget creation and domain normalization, notification triggers/buttons/manual closing, draft recovery, global day-start changes and focus save/start/stop. Run `node tests/browser_panel_smoke.cjs <browser.exe> <python.exe>` with the build Python environment; output goes under ignored `test-reports/browser-panel`.

The 33 JavaScript tests cover restriction recovery and local upgrades, including same-tab dashboard restoration and draft preservation. `node tests/browser_auto_update_smoke.cjs <browser.exe> --dashboard` independently verifies an actual automatic Brave reload alongside a covered website. The dashboard refreshes only while visible and pauses countdown painting when hidden. No live account sign-in, code revocation, application launch or uninstall is executed by these tests.

The installer passed all 92 temporary-profile install/upgrade checks and the 22-check native RTSS self-test. Extraction verified all 306 payload files. The real local upgrade preserved all 21 database tables and configuration, verified the installed files and reopened the 2.39.27 application. Brave's installed worker automatically reached 2.39.27. Visual checks used disposable profiles; automatic inspection of the real Brave window was unavailable.

Broader regression testing also caught a countdown-editor issue: language refresh emitted an unchanged position and marked an untouched game's inherited appearance as edited. Unchanged effective values now leave its saved profile intact. All 41 consent, customization and budget-countdown tests pass with this fix, which is included in the final verified installer. Legacy tests now verify separate weekday budgets and explicit draft discard; the test that manually replaces the whole UI retires its old draft event filter first.

All 1,078 discovered Python tests passed across module runs and targeted reruns, with no skips or uncovered tests. Remaining modules ran in fresh processes to bound Qt test memory use. The public installer, stable checksum, release manifest and both README version headers were checked for agreement.

## 2.39.26 focus group members and countdown clarity — 2026-11-02

Temporary-profile tests verify live focus-group membership, mixed game/application/website groups, deduplication with direct entries and multiple source groups, group edits and removals, inherited-entry removal guards, excluded games, cached activity inventory and newly observed members. Unchanged visible refreshes do not rebuild lists or query the catalog/database. Projection leaves saved rules, history and enforcement unchanged.

Countdown tests cover equal displayed seconds, different fractions that round to the same second, zero/negative values, longer durations and unequal event/budget values in both languages. The RTSS integration retains the main caption and suppresses only the duplicate secondary budget line. The notification editor's Enabled control is aligned at the top right of its first card. Hungarian and English layouts were inspected at 1000 × 700 and 1280 × 850. All 84 targeted tests passed.

The verified installer passed all 89 temporary-profile install/upgrade checks and the 22-check native RTSS self-test. Local delivery preserved all 21 profile tables and settings, verified 292 installed files, and reopened the installed 2.39.26 Hub. The paired Brave worker automatically reached 2.39.26. Public download artifacts remain unchanged.

## 2.39.25 single focus sessions and application selection — 2026-11-02

Temporary-profile tests exercise different work lengths, every zero/positive short-break, long-break and round combination, pause/resume, restart, completed-state persistence and restriction release. Disabled breaks wait for the next explicit start; zero rounds ends a single session without any break. Daily completion accounting remains unchanged. Focus settings and notification editor/popup tests verify zeros, visible validation without silently replacing input, draft recovery and synchronized timer preferences.

Application-picker tests cover detected/registered local executables, deduplication, missing and remote paths, searching, cancellation and explicit selection without launching. Discovery runs only when the picker opens. Installer upgrade checks retain zero values and a completed 00:00 timer alongside the existing profile-preservation checks.

## 2.39.24 configurable notification triggers and buttons — 2026-11-02

Temporary-profile tests cover time/startup/daily completed-Pomodoro triggers, persistent daily receipts, the global day boundary, deferred display, deletion and edits of pending rules. Startup rules fire once per process, never merely on save or day change. Cached completed-round totals avoid repeated history queries. The unified editor retains drafts and all rule fields across navigation and restart, including editable legacy presets.

Popup tests cover explicit/manual closing, survival through day changes and bedtime, preset icons, application launch only after an explicit click with literal executable arguments, missing files, editable Pomodoro timing, blacklist preservation and protection of running focus timers. Notification actions/paths stay local. Hungarian and English editors were inspected at 1000 × 700 and 1280 × 850, along with the interactive popup. Qt test teardown now disposes retired main windows before subsequent suites reapply the stylesheet.

Installer verification checks embedded payload hashes and temporary-profile upgrades, including notification trigger/icon/action/duration fields, legacy preset overrides, drafts, history and credentials, before updating the real local installation. Public download artifacts are unchanged during local delivery.

## 2.39.23 automatic local extension upgrades — 2026-11-02

The authenticated activity response announces the installed application version. The worker reuses its existing synchronization cycle to reload matching local extension files, after persisting covered-page recovery data. Covered tabs briefly use a static loopback handoff page because Chromium closes extension-owned pages on reload; opaque recovery tokens stay in fragments and never reach the server. Tests cover no-click upgrades, restart recovery, pairing preservation, normal idle operation without manifest reads, incomplete file replacement, storage/reload failures, bounded retries and loop prevention. A real Brave instance with a disposable profile verifies automatic upgrades and the legacy one-time bootstrap, retaining tab IDs, positions, pairing and original URLs, then restoring released websites. Legacy action-protocol compatibility remains covered. Temporary-profile installer checks precede the real local upgrade.

## 2.39.22 notifications, focus groups and browser recovery — 2026-11-02

Temporary-profile tests cover creating, editing, deleting and restoring built-in and scheduled notifications, unapplied drafts across restart, cancellation, failed validation and suppression of removed reminders. Focus tests cover application/site/game groups, changing budget membership, exclusions, pauses, breaks and the persistent total of completed rounds. The Activities game summary retains the daily game allowance independently of bedtime.

One global day-start control lives in Settings. Migration retains existing usage, warning receipts and one-time save grants while unifying legacy budget renewals. Regression checks cover overnight clock actions, computer periods, draft navigation and HU/EN layouts at 1000 × 700 and 1280 × 850.

The actual browser scripts run against mocked Chromium APIs: persistent original URLs, restored covers with changed tab IDs, automatic return after renewal or monitor disconnection, reused tab IDs, incognito exclusion and migration before extension reload. Installer smoke uses temporary fresh and upgrade profiles and checks notification drafts, focus groups and unified renewals alongside history, credentials and per-game preferences.

## 2.39.21 local budget drafts and fixed weekday selections — 2026-11-01

Temporary-profile tests exercise durable, unapplied budget drafts across back navigation, failed validation and application restart. General settings remain outside draft storage. Budget actions, active weekdays, renewals and member countdown appearance survive; successful Save clears the draft and explicit Discard remains cancellable. Idle flushes do not rewrite unchanged data. Budget members are shown in full, including unvisited websites beyond the fourth entry.

Each budget has one settings set and its own active-day selector. Independent computer periods retain their own names, timing, renewal, warning ledgers and weekday coverage. Legacy weekday schedules are presented as separate fixed budgets without changing applied settings until Save. Tests compare old and migrated overnight behavior and daily game limits, and verify nonblocking overlap warnings. Existing timing, restriction, zero-budget, preference, activity and countdown tests cover compatibility.

The optional detailed RTSS setting persists and uses the same selected next event in compact mode. Desktop and tray detail stays available. HU/EN interface captures and the native fullscreen fixture verify presentation. All 285 targeted tests and 86 bundled installer checks passed. Both native fullscreen RTSS modes passed five checks each. The verified installer upgraded the actual local installation before publication was requested; 26 profile-preservation checks passed and the updated application opened successfully.

## 2.39.20 next-event countdowns and persistent tray timers — 2026-11-01

The desktop and RTSS counter project the next configured warning, break or restriction, with the full daily allowance on a smaller second line. Tests cover repeating breaks, equal-time restriction precedence, clock deadlines, save allowances, disabled targets, redirected browser tabs, independent member appearances and foreground changes. Running breaks remain in the tray tooltip and named timer menu after leaving the activity. The native tooltip stays within its UTF-16 limit and hidden-window work reuses the existing accounting sample.

Restriction-only custom budgets no longer emit an implicit expiry notification. Explicit shared/game action plans suppress the old expiry/session popups, while their configured warning steps and the visible legacy early-warning card remain independent. Regression tests also retain website blocking, one-time save dialogs and explicit sound/popup delivery.

HU/EN captures verify the desktop counter and position picker. A real fullscreen Direct3D fixture verifies the RTSS counter, including Hungarian accents and visibly different text sizes. Its bounded sprite cache writes labels and digits only when appearance changes; countdown ticks only update ASCII image tags. The same fixture confirms connection without a startup delay. Temporary-profile installer and upgrade checks precede the local installation update.

## 2.39.19 daily clock actions and active budget days — 2026-11-01

Temporary-profile tests cover clock-only website, individual-game and shared budgets, independent renewal times, overnight selected days, disabling the minute cap even when its stored value is zero, no selected days, warning/closure boundaries, once-daily clock breaks, renewal and persistent save grants. Usage-based breaks and zero-budget blocking retain their behavior. UI tests verify save/reopen/cancel, computer-period day selection, finite countdowns and optional caps. Existing restriction, weekly schedule, wellbeing, focus, preference, navigation and budget-editor suites pass; HU/EN captures verify both window sizes and scrolled action controls.

The authenticated browser bridge negotiates the action protocol. A cached old worker gets temporary blocking compatibility without activating dormant focus lists or changing modern grants. Packaged extension pages compare the local manifest and reload an outdated worker at most once per version pair, preserving pairing; Node tests exercise the actual script. Installer smoke includes selected weekdays, the disabled usage cap and a clock action in its preserved upgrade profile.

## 2.39.18 browser compatibility for zero budgets — 2026-11-01

Zero-minute website budgets also populate the original browser blocking protocol, including its lease, so a still-loaded 2.31.1 worker blocks an already-open website without adding an action or reloading the extension. An active focus list retains its rules; an inactive list is not accidentally activated. Saving publishes the updated budget state immediately. Tests use the authenticated loopback bridge and the archived worker from `6522494`, plus the current browser worker. Action-target checkboxes now name their warning, break or restriction behavior, with HU/EN visual checks.

## 2.39.17 zero-minute daily budgets — 2026-11-01

`test_zero_budgets.py` verifies zero-minute shared, individual, weekday and mixed budgets: validation and persistence, implicit immediate blocking, native cover/mute and site-only isolation, browser policy, renewal/restart, save-grant cancellation, restoring a positive limit, exclusions, and preference synchronization. All profiles are temporary. Installer smoke also retains an enabled zero-minute website budget without a saved action plan.

## 2.39.16 actions for selected member types — 2026-11-01

Each card shows only the native application/game and website types present in its budget. Mixed cards have separate warning flags, break modes and lengths, restriction actions and save allowances, with a shared use threshold. Existing unedited plans keep their behavior and durable identifiers. Target projections isolate warning delivery, break deadlines, action priority and redirects. Temporary-profile checks cover independent settings, disabled types, membership changes, save/cancel, strict validation and runtime warning routing. Hungarian and English captures cover single-type and mixed cards at 700 and 1100 pixels. Installer upgrade checks preserve the nested target configuration. This delivery also includes the closure save-time work described below.

## 2.39.15 save time for every application closure — 2026-11-01

The existing per-budget one-time save allowance is editable on explicit close cards and closing breaks as well as restrictions. Native closure offers the configured allowance before closing; zero remains immediate, and browser-tab closure is unchanged. Isolated checks cover persistence, exact process identity, one-time use, expired breaks, renewal, cancellation and automatic closure after the granted interval. A requested save-and-close interval survives a shorter break and still closes its original process at the promised deadline. Non-closing breaks remain ineligible for save time. Hungarian and English captures verify the additional controls.

## 2.39.14 explicit restriction descriptions — 2026-11-01

Restriction cards separately explain application/game closure and website overlays, including the one-time save allowance and zero-minute behavior. Existing legacy actions retain accurate descriptions and unchanged execution. Hungarian and English screenshots cover site and mixed budgets at 700 and 1100 pixels wide with zero and positive allowances; the existing action-editor suite checks saving and compatibility.

## 2.39.13 redirect breaks in mixed budgets — 2026-11-01

Redirect breaks cover and mute native application/game members while retaining website redirects and the empty-address new-tab behavior. Temporary-profile checks cover both target types in the same budget, browser-process isolation for website members, timed release, recurrence, restart/day rollover, overlapping break priorities and uninterrupted restriction save time. Hungarian and English action cards are visually checked at 700 and 1100 pixels wide.

## 2.39.12 plain numeric and time inputs — 2026-11-01

Number and time inputs consistently omit step buttons. A local geometry workaround preserves the styled Qt 6.12 text editor without invisible clickable button areas. Temporary-profile checks cover keyboard decimal and time-section editing, saving, resizing, text visibility and clicks at the former button position; Hungarian and English screenshots verify the padded input appearance.

## 2.39.11 restore spacious action cards — 2026-11-01

Restores the earlier action-card field arrangement at the user's request while retaining individual group countdown settings. Hungarian and English captures and the existing action-editor checks verify the reverted presentation.

## 2.39.10 compact action fields and individual group countdowns — 2026-11-01

Hungarian and English action cards were inspected at 700 and 1100 pixels wide. Temporary-profile tests cover scoped group target lists, mixed members, separate styles and RTSS settings, switching targets without losing drafts, persistence, and cancellation without losing another budget's edits. The installer checks individual activity appearance preservation too.

## 2.39.9 unified website restriction and budget countdowns — 2026-11-01

Temporary-profile tests cover the single website restriction choice, numeric zero in both languages, immediate app closure with zero allowance, reopening after a consumed allowance, cancellable budget appearance drafts, shared and individual RTSS settings, renderer selection, and preservation of activity-specific overrides. Budget countdown changes are checked independently from unfinished restriction edits. Hungarian and English editor captures use disposable profiles.

## 2.39.4 simpler budget details and browser connection — 2026-11-01

Temporary-profile Qt tests cover direct budget usage and the actual custom day-start time, the browser connection dialog from the website activity list (including an empty list), language changes, cancellation and existing restrictions. Browser policy tests pass. Budget and website pages were inspected in Hungarian and English at 1000 × 700 and at a larger window size.

## 2.39.3 persistent Overview view — 2026-11-01

Temporary-profile Qt tests cover immediate and debounced view persistence across app restarts, name grouping, activity, relative and custom periods, both computer filters, selected day and search, invalid input, save failure, unavailable computers, unchanged settings drafts, language changes and no view-preference writes during refresh. The installer upgrade fixture checks the separate view record. Hungarian and English screens were inspected at 1000 × 700.

## 2.39.2 existing restrictions in the action list — 2026-11-01

Temporary-profile tests cover removing existing activity and individual-game restrictions from the action list, cancelling edits, preserving the game limit and its alert, adding new actions, language changes and legacy behavior. The editor was inspected in Hungarian and English at 1000 × 700.

## 2.39.1 breaks within the daily budget — 2026-11-01

Temporary-profile tests check that repeating breaks start only before budget expiry, do not start at or after the limit even after restart, that an exhausted bedtime cap prevents a new break, and that a break already underway finishes normally.

## 2.39.0 usage-based actions — 2026-11-01

Temporary-profile tests cover a single action button, absolute active-use thresholds before and after the budget, repeated breaks and release across restart/day changes, legacy timing preservation and explicit conversion, save allowance before expiry, closing consent, chronological order, cancellation and the scheduled-period action chooser. Hungarian and English action cards were inspected at 1000 × 700.

## 2.38.0 rebuildable budgets — 2026-11-01

Temporary-profile tests cover deleting and rebuilding the shared game budget and computer-use period, independently removing and adding computer-period warning/minimization blocks, old profile defaults, and compatible synchronization of per-day warning settings. The creation dialog and computer-period editor were inspected in Hungarian and English at 1000 × 700.

## 2.35.0 staged restrictions and current screenshots — 2026-10-30

- 832 Python tests across 62 modules pass. Modules run in isolated processes to
  avoid accumulating native Qt objects between suites. Existing preview,
  notification and wheel fixtures now exercise the current dialogs and the
  non-injecting notification behavior; asynchronous capture uses a bounded wait.
- 15 Node tests pass, including the real browser background script with mocked
  Chrome APIs: scoped return grants, denied grants, navigations racing a block,
  background tabs, block-page recovery and later tab close.
- 11 Defender-gate regression checks pass, including single-file enumeration
  under PowerShell strict mode. Missing scan receipts, altered files, disabled
  protection and matching detections all stop delivery.
- A Defender-scanned disposable WinForms process verifies exact-target muting,
  EOF/crash audio restoration, rejected process identity reuse and forced close.
  The packaged windowed audio helper passes the same pipe/mute/restore probe.
- A separate native screen probe shows the opaque cover, requests its one-time
  allowance, checks that the countdown leaves focus with the target, and confirms
  closure after the deadline. No real user application is closed by the probes.
- The four README screenshots use the current English interface and the
  maintainer's authorized, actually recorded game history. A separate profile
  copy disables synchronization; no usage values are invented, and no account
  session, pairing code or private browsing list appears in the images.

Reports remain in ignored `test-reports/` and `build/restrictions-235/` folders.
Platform checks do not establish compatibility with every game, exclusive audio
mode or anti-cheat implementation. Exclusive fullscreen uses the documented
minimize fallback for interactive restrictions.

## Defender release preflight

Run `tests/defender_scan_checks.ps1` for the release gate. It covers completed
clean scans, detected and remediated threats, removed/changed files, absent or
unrelated completion records, interrupted scans and disabled protection.
The gate also receives a real Defender scan of a benign fixture. Do not create
or execute a malicious fixture: a previously blocked release may be inspected
as data, but must not be launched to test the gate. Build and bundled-install
preflight failures preserve the user's existing installation and profile.

## 2.31.2 activity, synchronization and statistics

Temporary profiles cover application and website measurement, exclusions,
focus restrictions, settings synchronization and encrypted per-computer
activity snapshots. Qt tests cover daily stacked computer sections, all
activities, computer color legends even when only one computer has data,
custom calendar ranges, nested scrolling and draggable scrollbars. The
source-install smoke test checks reinstall, startup and profile preservation;
local delivery verifies the bundled installer and preserves the real profile.

## 2.28.2 uniform game-card grid — 2026-10-24

All visible cards share the height required by the most detailed visible card.
The grid stays compact without time details and expands uniformly for daily
usage or per-game allowances, including when a cap is added or removed. The
existing render pass computes the shared height; unchanged values do not alter
widget geometry. Temporary-profile captures check mixed capped/uncapped games,
both metadata rows and shrinking after filters or settings changes. Local
delivery verifies the installer, matching frozen source and profile preservation.

## 2.28.1 compact game cards — 2026-10-24

The artwork launch highlight has a straight lower edge; its top corners retain
the card outline. Cards reserve a compact 56-pixel title area and add space only
for visible time details. Mixed-height grid rows align at the top. Temporary
profiles exercise the Qt library, game limits and background resource behavior.
Nine visual renders cover narrow/wide cards, wrapped titles, hover, selection
and both time-detail rows. Local delivery verifies the installer, frozen UI
source and profile preservation before reopening the installed application.

## 2.28.0 per-game limits — 2026-10-24

Isolated-profile cases cover shared and per-game consumption, smaller overlay
allowances versus the shared Hub counter, both desktop and RTSS rendering,
preexisting usage, custom reset times, bedtime caps, restarts, strict validation,
excluded games, game-scoped alert deduplication, discovery merges and local-only
preferences. Qt cases exercise save, cancellation, storage failures, language
changes, multiple game drafts, empty inventories and unrelated unsaved settings.
Restriction fixtures retain the foreground grace, recheck changed settings and
focus before delayed minimization, and preserve protected-game consent gates.
Temporary-profile Hub/editor captures check Hungarian/English layout and the
remaining-time line at the minimum card width. Installer delivery checks the
extracted payload hashes, matching frozen modules, fresh install, upgrade and
uninstall, including preservation of game limits and existing profile data.

## 2.26.2 rapid foreground and preview transitions — 2026-10-23

Temporary-profile Qt sequences count actual Show/Hide events through repeated
Alt–Tab, game A/B switches, preview on/off, preview cancellation, late receipts
and rapid compositor-guard callbacks. Same-renderer preview changes retain the
same HWND and never clear/restart RTSS. Worker barriers reproduce A/B/A and
hide/resume with identical states, old healthy replies/errors and resumption
during removal. A negative control running the new cases against the preserved
2.26.1 frozen modules reproduces six failures without harness errors.
The private native mapping self-test verifies unchanged probes preserve the
entire visible OSD slot while a separate heartbeat requests fresh receipts.
These tests neither run real games nor modify the user's RTSS process.

## 2.26.1 countdown renderer handoff — 2026-10-23

Isolated Qt and worker tests cover hiding the desktop before publication,
pending/stale RTSS receipts, cancellation during IPC, delayed/failed removal,
preview and mode changes, and stable desktop fallback without repeated RTSS
publication. Pending handoffs cannot suppress warning popups. The native bridge
self-test uses a private named mapping and verifies frame-consumed removal,
helper restart recovery and duplicate owned-slot cleanup while preserving
foreign slots and the primary OSD. No real game or user RTSS process is used by
these tests. Local delivery also verifies the frozen source, installer payload,
temporary-profile install/upgrade/uninstall and preservation of the real profile.

## 2.26.0 public update notices and Windows version properties — 2026-10-23

The **200-test targeted regression run** passed in **249.061 seconds**, covering
Qt, tracking, schedules, bedtime caps, resource use, quiet background recovery,
custom messages and protected-game notification behavior. The final **31-test
updater/resource run** passed in **14.486 seconds**, including all **23 updater
cases**. Synthetic release responses cover numeric version ordering, no
downgrades, fixed URLs, schema/hash/size checks, response bounds, deadlines,
redirect rejection, missing manifests, unavailable services, lazy workers,
closed-result discard, restart-persistent cadence, manual retry limits,
preference/draft preservation, dismissal, browser failure and tray navigation.
Update results are asserted not to download, execute, focus or show a popup.
Temporary-profile Hub/settings captures were inspected. Direct App fixtures
disable external checks; the production entry point explicitly enables them.

A copied IExpress installer remained byte-identical after extraction following
the addition of Windows version resources. The bundled suite checks runtime
file properties, fresh automatic-check defaults and preservation of an opt-out
through upgrade. It disables checks before automated GUI startup to keep tests
off the public endpoint. A separate read-only live check confirmed that the
first public manifest has not yet been published; it is generated locally and
must accompany the next explicitly authorized GitHub publication.

## 2.25.0 optional bedtime budget cap — 2026-10-23

The **236-test targeted regression run** passed in **179.521 seconds**, covering
tracking, weekly plans, custom messages, bedtime boundaries, desktop/RTSS HUDs,
resource use, the full Qt interface and protected-game notification safeguards.
The final **25 bedtime-budget tests** passed in **3.973 seconds**. Fixtures cover
23:00 → midnight with an unused two-hour quota, quota-first expiry, paused play,
midnight/resume boundaries, after-midnight and overlapping per-day plans,
native local UTC-offset changes, opt-out/old profiles, strict validation, saved
and failed edits, custom remaining tokens, palette selection and identical HUD,
Hub and tray values. Hidden opted-in windows do not query/rebuild the catalog.
Measured history keeps its calendar-day split; exclusions and local sync
isolation remain intact. Hungarian Hub and settings captures were inspected
using a temporary profile. The bundled installation suite additionally checks
that fresh installations opt out and that upgrades preserve an explicit opt-in.

## 2.24.2 quiet background recovery — 2026-10-23

The **129-test targeted regression run** passed in **59.951 seconds**, covering
discovery, tracking, installation availability, Windows directory watchers,
Hub updates, translation and hidden-window resource scheduling. Deterministic
failure fixtures cover partial metadata, failed scans, dead/denied directory
and registry watchers, shortcut failures, bounded backoff, overlapping issues,
recovery, and successful background work preserving user-action feedback.
Persistent notices require repeated failures spanning at least 60 seconds;
tests advance a fake clock rather than waiting or modifying real installations.
Paths and exception details are asserted to remain absent from the Qt status.
The final **72-test source run** passed in **51.678 seconds**, including the full
Qt interface and resource suites and the added full-scan recovery case for a
previously failing individual group. All 16 background-status regression cases
pass with temporary profiles and no real game/account operations.

Use isolated temporary profiles and synthetic game installations. Never uninstall a real user game to test removal; mock the execution boundary.

## 2.24.1 installed-game selectors — 2026-10-23

All **129 targeted regression tests** passed in **61.325 seconds**, covering
availability, discovery/tracking, stored preferences, customization, previews,
consent/protected games and resource scheduling. The final **58-test core and
availability run** passed in **3.399 seconds** after adding explicit removed-game
selection and retired-rule replay protection.

Fixtures reproduce a removed manual game's retained catalog entry with saves
and history. It is absent from countdown settings; its history, EXE rule and
saved palette/size remain intact. Open editors update after manual EXE deletion,
reinstallation and launcher discovery while the Hub is hidden. Drafts survive
removal/reinstallation; an empty inventory hides edit/save/preview controls.
Opening a removed game's settings cannot silently select another game. No real
game is uninstalled, and no new polling loop or directory scan is introduced.

## 2.24.0 competitive-game notifications and consent — 2026-10-23

All **229 targeted regression tests** passed in **288.343 seconds**, covering
competitive-game notifications, both consent namespaces, hard anti-cheat gates,
Qt/Tk notification delivery, restrictions/bedtime, customization, image previews,
RTSS, the Qt UI and weekly schedules. The focused safety run also passed all
**76 tests** in **45.582 seconds**.
The editor tests check that mode, color, monitor, position, size, image, preview,
reset and save controls are hidden before consent and after revocation, and
reappear after acceptance. Switching games or language preserves permission
visibility and unsaved drafts; viewing a blocked game leaves its stored
preferences intact. Hungarian snapshots of blocked, accepted and revoked states
were rendered using an isolated test profile and visually reviewed.

All **31 native smoke checks** passed using a synthetic Form and temporary
profile. The protected fixture keeps its native foreground focus beside a real
nonactivating popup; the fullscreen branch requests sound without creating a
window. The same fixture cannot be forcibly minimized until the independent
minimization consent is set. Capture, preview activation/revocation, click-through
and casual-game minimization checks remain passing. No real protected game,
online account or actual game-input injection is used.

Failure checks retain queued alerts after popup/audio errors, throttle audio
retries, defer muted fullscreen reminders, prevent duplicate windows and preserve
normal casual-game behavior. Protected Escape stays blocked after either kind
of consent. Uncheckable known-game installations and anti-cheat helpers remain
blocked, including lower-level/native entry points. Hungarian minimization
consent was visually reviewed with an unchecked checkbox and disabled enable
button. Fresh installer diagnostics require both consent namespaces to be empty.

## 2.23.0 explicit overlay risk consent — 2026-10-23

All **110 targeted regression tests** passed in **80.660 seconds**, covering
consent storage/UI, anti-cheat defaults, both image editors, overlay routing,
customization and RTSS. A final **36-test consent/RTSS run** passed in **8.597
seconds** after adding queued-preparation revocation protection and the final
notice copy. It includes revocation of opaque executable names and shutdown
draining, so stale queued configuration cannot silently re-enable a revoked hook.

Consent is denied by default. Tests verify an unchecked acknowledgement and
disabled enable button, rejection on Enter/cancel, explicit checkbox plus button,
database failure, current notice version, game/root binding, restart persistence,
local-only storage, and independence from unsaved countdown drafts. The runtime
tests cover desktop/image permission, stale window revocation, continued Escape
blocking, exact RTSS paths and same-name protected games including exclusions.

All **25 native overlay smoke checks** passed against a synthetic Form and
temporary profile. Its protected classification first blocks capture/preview;
explicit test-profile consent allows a native game-window snapshot; revoking
permission blocks the same window descriptor again. No real protected game or
online account is used. Visual review of the Hungarian confirmation checks
readable notice text and visible, initially disabled acceptance controls.

The installer suite checks that fresh risk-consent records are empty. The real
local upgrade preserves all profile tables and does not grant any consent for
the user. Publisher protections are not disabled or bypassed, and the notice
is not presented as a legal or anti-cheat compatibility guarantee.

## 2.22.0 automatic anti-cheat protection — 2026-10-23

The full suite executed **469 tests** in **444.770 seconds**. Three customization
fixtures still assumed the previous default-on RTSS setting. They now explicitly
enable RTSS for those scenarios. The final **99-test targeted run passed** in
**61.232 seconds**, covering those failures, the complete new safety suite,
countdown customization, both image editors, native guards and RTSS routing.

The safety tests cover renamed protected games, installation markers, unreadable
and network roots, bounded/cached inspection, anti-cheat helper exclusions,
both globally/per-game enabled countdowns, capture/activation/Escape rejection,
continued tracking/popups, cached-profile and basename bypasses, prior RTSS
profile revocation and revocation failure. Fixtures preserve global/FPS settings
and verify that denied RTSS actions never launch a server or bridge.

All **23 native overlay smoke checks** passed. An ordinary synthetic Form still
supports the allowed screenshot/preview flow. Reclassifying only that Form as a
protected catalog entry blocks capture and preview activation/presentation.
No real protected game or online account is used to test injection or input.

The installer suite additionally checks that fresh profiles default RTSS off.
Saved RTSS choices, history, exclusions and synchronization credentials remain
subject to the existing isolated-profile upgrade checks. The local delivery also
backs up actual RTSS profiles before the updated app revokes known protected
hooking/OSD profiles. See [the review](docs/ANTICHEAT.hu.md) for official sources
and the limits of automated recognition; these checks are not publisher approval.

## 2.21.3 game-image monitor identity — 2026-10-23

All **44 game-preview and overlay regression tests** passed. They cover actual
painted pixels in both global and per-game position editors, explicit refresh,
capture caching across language changes, identity/focus guards and bounded capture
workers. Native HMONITOR mapping is tested with identical friendly monitor names,
a negative display origin, mixed DPI and a disconnected display.

All **21 native overlay smoke checks** passed with a synthetic game and temporary
profile. The suite now checks rendered game pixels, not just a populated capture
field, and verifies that a native capture device resolves to the correct QScreen.

A read-only check against the user's already running Minecraft Java window
reproduced the mismatch: Qt reported `24G1WG4`, while Windows reported
`\\.\DISPLAY1`. Offscreen editors using the real capture then displayed game pixels
at all 49 sampled positions in both editor modes. The check did not modify the
real profile, activate/minimize the game or save its image. This validates that
running window's capture and editor rendering, not all renderers/fullscreen modes.

Installer verification uses the existing isolated-profile install/upgrade suite,
payload hashes and source/installer secret scans before updating the local app.
The real upgrade backs up and compares profile tables and reopens Gaming Hub.

## 2.21.2 Qt security update — 2026-10-23

All **450 regression tests** passed in **415.839 seconds** with Qt/PySide6/
Shiboken **6.12.0**, Python 3.13.16 and OpenSSL 3.5.9. The locked Windows wheel
hashes match official PyPI metadata, `pip check` succeeds, and a fresh advisory
query returned no entries for the twelve pinned runtime/build package versions.
The Qt upstream advisories were checked separately from the Python package index.

Visual inspection caught Qt 6.12 collapsing styled `NoButtons` editors to one
pixel despite their values remaining correct. The application now retains the
normal editor layout and hides only the step button controls. A regression test
checks text geometry and actual rendered glyphs for number/time fields at two
window widths, alongside existing editing, wheel and translation checks.

All **19 native overlay smoke checks** passed with a synthetic game and temporary
profile: game-window capture, placement background, color, passive focus/input
behavior, explicit game activation, cancellation on return, and minimized-game
restoration. The first background run correctly reported Windows denying focus;
the harness now establishes its own foreground Hub before simulating a Preview
click. The synthetic game's activation grants foreground permission to the test
parent. No input is injected into other applications.

The privacy notice now documents capture on opening the countdown editor or
refreshing its game image, memory-only preview use and no image saving/upload.
Qt component notices and source links match 6.12.0. Release verification compares
the packaged application code with the current source, its Qt files with the
pinned wheel installation, and the bundled privacy notice with the repository.
The installer smoke suite uses a separate profile before upgrading the real
installation; the latter upgrade backs up and compares all profile tables.

## 2.21.1 notification icon stability — 2026-10-23

All **449 regression tests** passed in **405.166 seconds**. After including
the executable location in the icon identity, all **37 focused tray, RTSS,
resource and process-inspection checks** passed in **8.220 seconds**.

New tray cases verify stable per-profile GUIDs across window recreation and
path casing, distinct profiles and moved binaries, 120 changing tooltips without icon replacement,
no duplicate writes for unchanged text, Explorer recovery with the same GUID,
and no resurrection after close. Native HWND callbacks, legacy clicks, menu
cancellation and the Tcl subprocess message-loop regression remain exercised;
UI fixtures mock only the Shell notification boundary to avoid moving the
user's real notification icons during repeated app creation/cleanup.

RTSS cases verify that an available SDK skips enumeration/startup, a running or
uninspectable process blocks duplicate startup while the mapping is absent,
a confirmed process exit permits a new start, and checks/failures are throttled.
Native process lookup verifies the current image, missing images, session
isolation, another installation, denied inspection and snapshot-handle cleanup.
The development PC's existing RTSS was also inspected read-only: its process
was recognized, and a simulated absent mapping did not invoke startup.

## 2.21.0 game-backed countdown preview — 2026-10-23

All **436 regression tests** passed in **421.507 seconds**. After the final
restore/activation guard, **69 focused tests** passed in **48.272 seconds**, and
the **12 preview cases** passed again in **5.030 seconds** after isolating their
renderer boundary. All **19 native smoke checks** passed, including restoration
from minimization and cancellation after the fixture yields foreground.

The new regression cases cover independent per-game color inheritance,
validation and durable saves, draft switching/cancel/reset/translation, outgoing
statistics isolation, RTSS preview text, expiry returning to real usage and saved
colors, single activation and Alt+Tab cancellation, identity/HWND reuse guards,
stale snapshots, no recapture during language changes/hidden ticks, and a blocked
capture worker with bounded shutdown and no replacement thread.

The native smoke uses an isolated profile and a separate synthetic Windows Form.
It checks client-only capture and monitor-relative placement, in-game preview
activation and colors, HUD input transparency, unchanged passive foreground,
return-to-Hub cancellation, restoration from minimization, and unchanged profile,
history and alert keys. The fixture grants only its test parent foreground
permission; no real game is launched or minimized and no input is injected.
Hungarian/English editor captures were inspected at normal and compact sizes.
GPU/protected/fullscreen screenshot support and actual RTSS injection still depend
on the particular game; mocked RTSS routing is covered by integration tests.

The isolated bundled upgrade fixture preserves nested per-game colors alongside
all existing schedule, sound, history, exclusion and credential settings. Local
installation is upgraded only after the matching installer passes verification.

## 2.20.0 weekly day selection and settings groups — 2026-10-23

All **427 regression tests** passed in **373.157 seconds**. After the final
shared-message grouping and explicit copy-button wording, **85 focused weekly,
customization, personal-message and Qt tests** passed in **46.066 seconds**.
The eleven weekly cases cover all seven weekdays, invalid plans, legacy weekend
fallback and conversion, independent/group edits, mixed numeric/checkbox/time
values, typing an already displayed value, explicit unification, empty selection,
translation without losing drafts, failed writes and localized day errors.
Daily warning keys, history/exclusions and overnight Sunday/Monday overlap are
verified, with no schedule settings included in outgoing statistics snapshots.

The editor updates drafts on interaction and writes only through the existing
Save action. Group edits preserve every untouched field and day; unrelated saves
do not materialize or replace schedules. Legacy weekend values are expanded into
the seven effective plans before their switch is retired on an edited save.
Existing tracker, restriction, desktop/RTSS and bedtime paths share the weekday
resolver and retain their existing timers and foreground-accounting rules.

Hungarian/English previews were inspected at 1000×700 and 1160×960 window sizes,
including identical/mixed/weekend selections, section day captions, separate
message settings and horizontal rules for countdown position, colors and preview.
The bundled fixture checks the empty daily-plan default and preserves a Tuesday
override alongside legacy weekend, sound, game, history and credential settings.
Real-profile comparison permits only the new empty daily-plan key, retaining all
previous values and tables; the installer is verified before the local upgrade.

## 2.19.0 sounds, weekend schedules and per-game countdowns — 2026-10-23

The full **415-test** regression run passed in **301.124 seconds**. After the
final overnight-overlap and layout refinements, **197 focused tests** passed in
**105.335 seconds**, including all **16 customization cases**. Coverage includes
weekday/weekend resolution without mutating the normal plan, Friday/Saturday
and Sunday/Monday bedtime boundaries, overlapping next-day reminders, retained
minimization grace across midnight, warning/limit keys, conserved daily time,
current budget agreement between the library, restrictions, desktop and RTSS,
legacy defaults, persistence and discovery ID migration.

Sound tests mock Windows playback and check silent popups, asynchronous aliases,
custom WAV flags and fallback on missing files. UI tests check unsaved drafts,
language changes, cancellation, failed writes, two-game edits, restoration of
global defaults, independent visibility, precise position/size previews and RTSS
preparation restricted to games with an enabled countdown. Personal settings and
sound paths stay outside statistics snapshots. These changes add no timers or
background playback process. RTSS routing remains mocked; no new real-game
fullscreen compatibility claim is made.

Hungarian/English sound panels, weekend dialogs, game countdown editors, reminder
popups and countdown controls were rendered with isolated profiles and inspected.
The bundled fixture verifies compatible fresh defaults and preservation of sound,
saved WAV path, weekend plan and game overrides alongside existing profile data.
Real-profile upgrade checks allow only default values for the new keys and compare
all existing settings and tables against a stopped-profile database backup.

## 2.18.1 editable defaults and reminder layout — 2026-10-23

All **168 focused personal-reminder, bedtime, core, RTSS, Qt interface and
overlay tests** passed in **48.498 seconds**. Editable defaults retain live time
tokens in both languages, including non-integer daily limits. Untouched defaults
and restored defaults remain automatic after Save; editing one message stores
only that message. Language changes translate untouched defaults while retaining
personal drafts and their selections. Existing long-message scrolling, save
failure, cancellation, timing, history and alert-delivery checks remain green.

Isolated Hungarian/English captures of all four reminder kinds, the message
editor and 25/48 pt countdown controls were rendered and inspected. Popups use
an icon header and a bordered message panel without the redundant caption;
the preview state selector shares the preview button row below opacity.
The installer fixture continues to use temporary profiles before upgrading
the real installation with a database backup and per-table preservation checks.

## 2.18.0 personal messages and countdown colors — 2026-10-23

The full **398-test** regression run passed in **242.247 seconds**. After the
final remaining-minute token corrections, **89 focused core, bedtime, personal
reminder and RTSS tests** passed in 6.250 seconds. Earlier focused overlay and
Qt runs also passed all 30 and 47 cases. Nine new cases cover legacy defaults,
invalid/oversized input, store reopen, unknown/literal braces and HTML-like text,
actual warning/limit/session thresholds and keys, zero remaining time after the
limit, current local game minutes in bedtime text, drafts, cancellation, failed
writes, defaults, translation, long multiline messages and acknowledgement access.

UI previews preserve budgets and alert ledgers and never send Escape or minimize
a window. Draft text stays literal across language changes; message Save retains
other unsaved controls. Pixel checks verify actual desktop colors in both states;
RTSS assertions verify matching ARGB/FNT output. Palette cancellation/reset/save,
unchanged swatch icons on translation, history/exclusion preservation and absence
of personalization in outgoing statistics snapshots are covered. Hungarian/English
message editors, personalized warning/bedtime popups and countdown controls were
rendered with isolated profiles and inspected. RTSS routing/profile tests remain
mocked, so this adds no real-game fullscreen evidence.

The installer fixture checks the original white/red colors and empty messages
on a fresh profile, then preserves custom normal/warning colors and two custom
messages through upgrade alongside existing size, position, history and secrets.
Real-profile comparison permits only the new default keys; all existing settings
and every other table remain subject to the previous preservation/hash checks.

## 2.17.1 static countdown help — 2026-10-23

All **30 overlay** and **47 Qt interface tests** passed. This presentation-only
change removes hover help from the position miniature and coordinate fields;
one wrapped, permanently visible label explains dragging, the display origin,
1 px/Shift-10 px movement and preview/save behavior. Isolated Hungarian/English
renders were inspected at 25/48 pt. The preview fixture also checks that the
miniature and fields have empty tooltips after each language change and that
the translated static explanation remains visible. Existing drag, exact position,
size, persistence, focus and wheel-scrolling regressions remain green.

## 2.17.0 precise countdown and text size — 2026-10-23

All **389 automated tests** passed in **200.511 seconds**, including 30 overlay,
14 RTSS and 47 Qt interface cases. Pixel editors match the actual desktop HUD
position, dragging updates the fields, arrow keys move 1 px and Shift + arrow
moves 10 px. Tests cover negative-origin and portrait monitors, changed display
sizes, clamping, untouched-axis precision, size-dependent bounds and literal
keyboard entry. Interior pixel positions and edge anchors survive resizing.
The new 8–72 pt setting rejects invalid values, defaults to the old 25 pt size
for legacy profiles, survives store reopen and leaves budgets/history intact.

Preview updates position/size without taking focus, crediting play time,
acknowledging alerts or publishing to RTSS. Unsaved edits survive translation;
wheel scrolling leaves coordinates and text size unchanged. Hungarian/English
controls at 25/48 pt and standalone text at 8/25/72 pt were rendered with isolated
profiles and inspected. The miniature uses the same font metrics and placement
as the desktop HUD; font metrics stay cached until size or DPI changes.

RTSS tests verify matching FNT height, scaled interior placement, unchanged edge
anchors, legacy four-field positions and profile-write caching. RTSS routing and
profile I/O use mocks; these changes do not add a real-game fullscreen trial.
The bundled upgrade fixture saves a non-default 48 pt size and verifies it after
upgrade, alongside existing coordinates and profile preferences. Real-profile
comparison allows only the new default 25 pt key, preserving every existing
setting value, credential, history/exclusion row and connection preference.

## 2.16.0 stable language changes and cached UI — 2026-10-23

All **382 automated tests** passed in **228.763 seconds**, including 47 Qt
interface cases and 19 artwork/client cases. New regressions check repeated
language changes without rebuilding the central widget, querying the catalog,
reading shell icons or requesting artwork. Existing pixmap identities, focused
cards, pending artwork tokens, flag icons, filters, date ranges, error states,
unsaved limits/paths/overlay controls and open rename-dialog input survive.
A simulated language-save failure restores both the selection and saved language.
Filtering back to a game uses its cached pixmap before the event loop runs;
source-name searches stay valid across languages. Unchanged launcher results
reuse cards/icons; a moved client updates only its own card and launch target.

Statistics refreshes retain date/legend/table items and selected rows while
updating actual time changes. Language changes format cached percentages and
computer/source labels without querying history, even with an invalid date edit.
Isolated Hungarian/English library, statistics, settings and rename-dialog
renders were inspected. Translated combo boxes resize for longer text; user
names and paths remain literal. These fixtures never launch real games.

The local delivery workflow verifies extracted installer hashes, runs the
bundled install/upgrade/uninstall checks with a temporary profile, then backs
up the real profile and compares every table and installed-file hash before
reopening the updated application.

## 2.15.1 rename any computer — 2026-10-23

All **42 Qt interface tests**, **13 statistics sync tests** and **13 history and
translation tests** passed. The rename dialog lists every known computer and
preselects the current filter. Linked-computer names are local preferences keyed
by hashed connection label and device ID. Tests retain them after incoming name
changes and database reopen, isolate different connections, preserve duplicate
computer identities and colors, and reject unknown targets, failed writes and
saves after the connection changes. Aliases never enter outgoing snapshots or
change remote revision counters, source metadata, local settings or budgets.

The isolated installer upgrade fixture verifies both the own computer name and
a linked computer's local alias. Hungarian/English previews cover the new selector.

## 2.15.0 computer renaming — 2026-10-23

All **41 Qt interface tests**, **11 statistics sync tests** and **13 history and
translation tests** passed. New isolated UI tests cover offline renaming,
whitespace/cancel handling, the 80-character limit, accented/HTML-like names,
failed writes, persistence after database reopen, unchanged settings/device
identity/history/local budgets, retained filters/selection/colors, and name
updates in the chart, dropdown and table. Enabled sync queues the name through
the existing guarded event without signing in or bypassing the ten-minute wait.

Hungarian/English page and rename-dialog previews use an offline fixture.
The installer upgrade fixture also checks that a saved computer name survives.
The language selector's local flag SVGs are rendered in both
languages and included by the existing icons-directory packaging rule; the
final Qt run includes their language-switching state-preservation check.

## 2.14.1 tooltip typography — 2026-10-23

Game and computer rows in daily chart tooltips use regular weight, including
the segment under the pointer. The date and daily total retain their heading.
The existing statistics Qt tests and an isolated rendered tooltip check verify
that colors, durations, shares and day selection remain intact.

## 2.14.0 color-coded statistics — 2026-10-23

All **371 application tests passed in 197.821 seconds** on CPython 3.13.16 /
OpenSSL 3.5.9, including the remembered-launcher changes. After the final legend
layout adjustment, the 39 Qt interface tests and the visual previews were rerun.

Isolated Qt regressions aggregate the same game across computers without
double counting, switch stacked bars between games and computers without a
database read, and verify matching legend/table colors through filtering and
language changes. Actual mouse clicks select a day's breakdown. Tooltip checks
cover daily shares, escaped game/computer names, empty dates and a dense 366-day
period with fractional recorded time. Period totals and local daily budgets
remain unchanged. Hungarian and English previews use synthetic offline history;
the minimum window size is also inspected.

## 2.13.1 remembered launcher clients — 2026-10-23

Launcher regressions cover persistence across database reopen, an empty saved
list, malformed cache fallback, lazy first-page loading, repeated navigation,
language changes and absence of timed rescans. Manual refresh replaces and saves
the list; failed refresh preserves the last successful result. Cached paths are
validated without filesystem or registry discovery and revalidated when opened.
The isolated bundled upgrade check also preserves the remembered launcher list.

## 2.13.0 additional game clients — 2026-10-22

Publisher fixtures cover EA app/Origin, Battle.net, GOG Galaxy/offline installs,
Xbox, Rockstar Games Launcher and Amazon Games without installing those
clients or executing their programs. The **22 publisher integration tests**
cover registry views, custom locations, deduplication, move/uninstall behavior,
read-only SQLite and bounded protobuf indexes, partial writes, protected Store
containers, visible package application selection, launcher/helper exclusions,
structured launch arguments, offline GOG play tasks, launch-only URI rebuilding
and preservation of history, assignments, hidden state and exclusions.

The current machine also provides an installed Xbox application and Solitaire
package for a read-only native discovery check. Missing publisher clients do
not create cards. Windows Shell's native shortcut test allows its existing
30-second bridge timeout plus event debounce; fresh synthetic EXEs can take
longer to resolve than a warm installation. Automated fixture tests precede
the verified local upgrade; GitHub publication waits for the user's request.

## 2.12.1 interface corrections — 2026-10-22

All **343 application tests passed in 179.397 seconds** on CPython 3.13.16 /
OpenSSL 3.5.9. The settings regression sends actual Qt wheel events over numeric,
time, monitor and opacity controls, both focused and unfocused: the page scrolls
while values stay unchanged. Open combo popups, keyboard editing and slider
dragging remain usable. Sync tests cover guarded connection saves, truthful
waiting/busy labels and the timestamp of the last successful exchange. Menu
tests exercise the explicit tracking actions on the selected game; statistics
tests check the displayed start of the actual averaging period.

Position-picker regressions reject drags started outside the drawn monitor and
keep the full timer rectangle inside landscape, portrait, ultrawide and tall
previews, including corner drags and keyboard movement. Hungarian and English
screens were inspected at the minimum window size; the three README screenshots
were regenerated with an isolated offline profile and demonstration usage.

The bundled install/upgrade regression now also seeds and verifies a per-game
tracking exclusion. Its existing checks cover history, hidden games, connection
codes, cached statistics, language, overlay/bedtime preferences, startup entries
and an unchanged runtime DLL held open during upgrade. Installer verification
compares actual self-extractor output with the packaged inputs and checks every
payload-manifest hash before running that isolated regression.

## 2.12.0 event-driven statistics sync — 2026-10-22

All **338 application tests passed in 158.719 seconds** on CPython 3.13.16 /
OpenSSL 3.5.9. All **24 Node endpoint tests passed**. New regressions cover
startup-only idle behavior, foreground gameplay transitions, one-shot event
coalescing, the shared ten-minute guard, restart/code-change persistence and
persisted Retry-After without automatic error retries. Transport tests retain
v1 ciphertext compatibility while sending the v2 event policy and test the
upgrade-required response. Existing linked-code, history, local budget and
exclusion tests remain passing.

All **nine PostgreSQL probes passed** against the hosted Free project's actual
engine, rolling back fixture users, ciphertext and quota writes. The new probe
checks durable device cooldowns, no tuple updates on rejected requests, separate
computer access, daily/monthly group AND owner caps, rotation-safe owner ledgers,
UTC-day reset, missing-copy repair and server-only grants. The other eight
security/account/Auth/storage probes were rerun successfully. Node tests reject
legacy requests before body/SQL work and ensure a device cooldown cannot block
another computer in the same linked group. No request flood was sent.

## Public distribution preparation — 2026-10-21

The 2.11.0 runtime is unchanged from the combined release below. Publication adds
MIT licensing, privacy and development documentation, an English backend guide,
English-named source-install entry points and three English UI screenshots.
Screenshots use an isolated offline profile, real local game artwork and synthetic
history. Native tracking, launch, overlay, sound and minimization actions were
disabled in that screenshot fixture.

Gitleaks 8.30.1 scanned all 36 existing commits and the staged publication changes.
Its only historical match was an intentionally invalid JWT/refresh-token test
fixture; the reviewed exact fingerprint is recorded in `.gitleaksignore`.
No real credential was found. An additional review covered 630 historical text
blobs for private keys, provider secrets and personal path/identity patterns.
Upstream attribution email addresses remain intact. No historical Actions runs,
artifacts or issue content existed at preparation time. This is a targeted
publication audit, not a guarantee that unknown vulnerabilities do not exist.

All 20 isolated source install/upgrade/uninstall checks passed after renaming the
entry points. The documentation-only installer repack preserves every previously
recorded runtime/dependency file hash. Actual self-extractor output is compared
with the packaged inputs, the integrity manifest is verified, and all 41 bundled
install/upgrade/uninstall checks pass, including the ten-check RTSS helper
self-test. The installer contains the matching MIT/privacy notices and screenshots.
Local documentation links and the stable installer checksum are checked before
publication. No application or backend behavior changed, so the full runtime
suite recorded below was not repeated for this documentation delivery.

## 2.11.0 combined release: sync security and capacity

All **335 application tests passed in 160.093 seconds** on CPython 3.13.16 /
OpenSSL 3.5.9, including the integrated bedtime feature and the manual-sync
cooldown, visible/background cadence and server-retry regressions. All 22 Node
endpoint tests passed, including varied-credential/IP throttling, early cooldowns
and verified-owner management limits. SQL tests use bounded fixtures and roll
back all writes; no traffic flood was sent to the public endpoints.

The eight PostgreSQL probes cover account/identity isolation, persistent quotas,
retention, signup and token gates, fair capacity, saturated-counter tuple
stability, the total code registry, metadata and combined OAuth state bounds,
global/fair upload churn budgets and rotation-safe upload counters.
The bundled upgrade regression holds an unchanged runtime DLL open against writes,
reproducing a resident RTSS helper. Setup hashes and retains identical files;
replacement targets reject leaf reparse points as well as parent junctions.
Live GitHub PKCE login, Auth-hook invoker permissions, metadata-free JWT claims,
refresh, unchanged ownership and logout passed using a temporary session; the
installed app's saved primary session was untouched. Source and installed-app
history, codes and exclusions are verified separately during delivery.

The new controls are application/storage safeguards. They do not establish
distributed DDoS resistance, unlimited Free capacity or absence of unknown bugs.
The capacity examples in SECURITY.md are request arithmetic, not load-test
results. Custom Auth-table triggers require revalidation after provider upgrades.

## 2.11.0 integrated bedtime reminder

All 13 bedtime tests passed: default opt-in, input/order validation, custom and
cross-midnight schedules, morning release, once-per-cycle durable reminders,
cached reads, missed-minute/lock/sleep/clock changes, ten-awake-second cadence,
independent browser minimization without keyboard injection, preserved history
and exclusions, scoped one-time task handover, translated Qt controls and popup.
The Hungarian settings card and popup were rendered and visually inspected.
A real self-closing Windows fixture was acquired in the foreground and minimized
through the new native path; its actual iconic state was verified.

The 20 isolated source install/upgrade/uninstall checks passed with the new
modules and migration script. Source checks ran with `PYTHONUTF8=1` so native
PowerShell output retained the accented checkout path.

```powershell
python -B -m unittest discover -s tests -p test_bedtime.py -v
```

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
- Verify intended repository visibility and absence of data/logs/installed manifests from archives.

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

The user confirmed the timer was visible in Stardew Valley exclusive fullscreen. Its initial text-coordinate placement was offset. The final renderer uses RTSS native per-game position properties, signed edge anchors and full-framebuffer coordinates instead of absolute hypertext layers. The user then confirmed the saved top-right position was correct. The title/menu screen was tested; gameplay beyond the title screen, other games and the second physical PC still need verification. No game display mode was changed. Window captures did not reliably include the RTSS text, so screenshots alone are not treated as visibility evidence. The repository was private during that validation.

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
# Secret exposure regression checks

`packaging/build.ps1` now audits current source and the final Windows installer
before reporting a successful package. It downloads the pinned Gitleaks ZIP
once into the ignored build directory, verifies its SHA-256 before extraction,
and re-extracts the executable from those verified bytes on every use.
`-FreezeOnly` audits the frozen directory too. Archive or scanner errors fail
the build; the audit never runs an installer or bundled application.

```powershell
& build/venv-security/Scripts/python.exe -B -m unittest discover -s tests -p test_payload_security.py -v
```

The regression fixtures cover a secret introduced as a compiled constant in a
compressed PyInstaller PYZ module, binary/UTF-16 credentials, administrative JWTs,
nested `.env` and SQLite profiles, archive traversal, invalid frozen archives,
public publishable keys, and redacted findings. Use a build environment with
PyInstaller installed. Audits are detection evidence, not a proof that no future
secret or vulnerability can exist.
