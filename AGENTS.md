# Version delivery

The user requires every new installable version to be available directly from
the GitHub repository's README. Publishing these updates is part of delivering
a version, not an optional follow-up.

For each new application version:

1. Update the application version, run the relevant checks, and build and verify
   the Windows installer from the matching source.
2. Update `downloads/GameTimeMonitor-Setup.exe` with that verified installer.
   Regenerate `downloads/GameTimeMonitor-Setup.exe.sha256` using the stable
   download filename.
3. Update the version shown at the very beginning of both `README.md` and
   `README.hu.md`. Keep their direct installer links visible at the top and
   pointing to the current file in `downloads/`. Use the full GitHub
   `/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe` URL. Do not use a
   relative installer link with `?raw=true`: it navigates through the blob page
   and the user has reported a GitHub error page during that download flow.
4. Commit the matching source, installer, checksum and README updates together,
   then push them to the GitHub default branch through the repository's allowed
   workflow. Verify that the remote README version and installer match.

The user has authorized these routine GitHub updates for future versions; do not
ask for the same authorization again. The user authorized public distribution
on 2026-10-21; keep the repository public and use the README download as the
primary distribution path. Do not substitute a local-only
installer or a Releases-page-only download. Preserve existing user history,
settings and per-game exclusions during upgrades.

Documentation-only changes do not require a new application version or installer.

# Resource usage

Keep CPU, memory, disk and network usage low, especially while the Hub is hidden
or minimized during gameplay. Prefer event-driven work and cached results;
poll fast only while work is pending or a visible countdown requires it. Preserve
foreground time accounting, warning/restriction responsiveness, synchronization
and upgrade durability when optimizing. Avoid repeatedly rebuilding unchanged
widgets or reading the catalog for a hidden window.

# Statistics service

Use the existing Supabase **Game Monitor** project `jtvdbqwmejrckjejjrdl` on its
Free plan. The user explicitly does not want Sites for this feature. Do not
create a replacement project, switch to paid hosting, or embed provider admin
credentials in the client. Server code and schema are in `sync_backend/`.
Preserve per-user code isolation, client-side encryption, local daily budgets
and history, and the server-only database grants when updating synchronization.
