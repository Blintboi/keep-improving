# Architecture

The app combines a Qt Widgets interface (PySide6 Essentials) with the existing standard-library tracker and native Windows APIs. QApplication owns UI state on its main thread. Workers communicate through queues; the native tray callback must never invoke widgets directly. CLI diagnostics/configuration commands do not import Qt.

| Module | Responsibility |
| --- | --- |
| `main.py` | CLI, per-profile mutex, logging, diagnostics and lifecycle; frozen builds separate writable data from program files. |
| `model.py` | Stable IDs, path matching, helper blocking, exact EXE rules and tracking policy. Legacy internal `Kézi` source values display as Manual. |
| `store.py` | SQLite WAL, configuration/history, overrides, visibility and discovery merges. Schema v2 adds `game_preferences` idempotently. |
| `discovery.py`, `ubisoft.py`, `riot.py`, `minecraft.py` | Local metadata readers; only successful scans retire installations. |
| `service.py` | Debounced file/registry watches, retries and repair scans. |
| `tracker.py` | Foreground intervals, shared daily totals, late classification, checkpointing and threshold/process-session alerts. |
| `win32.py` | Native process/session identity, file/registry watches, queued tray events, instance mutex and guarded Escape/topmost behavior. |
| `hub.py`, `hub_links.ps1` | Shortcut planning/COM, root ownership, locking, hashes and safe retirement of unchanged owned links. |
| `launch.py` | Read-only launch preparation on a lazy worker, canonical game-launch URIs, preserved shortcut arguments and explicit EXE choices; execution follows Play on the GUI thread. |
| `qt_ui.py`, `qt_widgets.py` | Default Qt library/settings, responsive painted cards, local artwork, independent alerts/removal dialogs and lifecycle. |
| `controller.py` | Shared UI-neutral tracking/discovery/tray/launch actions; all callbacks use the GUI scheduler. |
| `ui.py`, `statistics_ui.py` | Retained Tk regression fixtures; not imported by the production entry point or collected into the binary. |
| `i18n.py` | English/Hungarian presentation catalog; language is a saved setting and never changes IDs or paths. |
| `statistics.py`, `qt_statistics.py` | Inclusive date-range history summaries, zero days, daily chart, drilldown and per-game shares. All recorded rows remain eligible, regardless of current visibility or installation state. |
| `removal.py` | Side-effect-free removal plans and explicitly confirmed execution; no raw registry command execution or direct game deletion. |
| `packaging/` | Frozen runtime build, per-user bootstrap and owned-file uninstaller. |

Visibility is a stable-ID preference, independent of tracking and Hub eligibility. Manual/pending entries becoming launcher entries migrate history, rules, overrides and visibility. Removed entries with today's history remain viewable unless hidden.

An alert is marked delivered only after it becomes visible. Its independent window avoids minimized-parent withdrawal. Foreground identity guards Escape; failed presentations remain queued. New profiles count chess; legacy settings missing `exclude_chess` retain the prior exclusion policy. Upgrades preserve user thresholds and Hub location.

There is no server, administrator service, kernel hook, injected game overlay or multi-PC synchronization. Unknown standalone games outside known roots require explicit assignment rather than a whole-drive EXE scan.

The first page is the integrated Gaming Hub; search and source filters affect presentation only. Play does not depend on optional shortcut-folder synchronization or tracking exclusions. `settings` rows named `launch_exe:<game ID>` store explicit executable choices, validated against the exact tracking rule. Rule removal/reassignment clears a stale choice; discovery merges transfer it transactionally. The launch worker never invokes widgets, SQLite or game execution, and closing the app cancels preparation. Launch requests are executed by the GUI thread after rechecking installation state. Protocol links are canonicalized to launch actions; original `.lnk` arguments are preserved and file hashes are rechecked before opening. The `--hub` entry point requests `show-hub.request` when another instance owns the profile, returning to the Library page in that instance. Setup migrates the former folder shortcut and removes only the old owned duplicate monitor desktop shortcut. A redirected desktop folder supports isolated installation tests.

Language switching rebuilds the main widgets on the GUI thread and finalizes retired Tcl variables there. It preserves the current statistics dates and does not restart tracking. The visible statistics page flushes pending measurements before querying SQLite at most about every 10 seconds. Historical days use the same local date keys already recorded by the tracker. Averages use the intersection of the selected range with the profile's installation day through today, including zero-activity days. `settings.tracking_started_on` is stored separately from the user configuration and preserved on upgrade. Legacy profiles use the earlier available filesystem creation day or first recorded usage; restored earlier history can move the marker backwards. The installer stores the Hub shortcut icon in retained user data rather than relying on a program file that disappears during uninstall.

Qt notifications are unparented topmost dialogs, avoiding hidden/minimized parent suppression. They use the existing guarded Escape and native foreground presentation, and remain queued if presentation fails. Qt timers service the tracker and dispatch native tray events without toggling an already-open window. Local artwork loading is staggered; Qt pixmaps and shell icons are created only on the GUI thread. Cover images fit completely inside a consistent art area using aspect-ratio-preserving scaling; unused space keeps the dark background. Icons preserve their own aspect ratio too. Source labels, filtering and sorting do not change catalog IDs or measurement policy.
