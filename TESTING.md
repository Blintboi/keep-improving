# Testing

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
