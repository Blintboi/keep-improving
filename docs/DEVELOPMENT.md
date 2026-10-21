# Development and builds

The application targets Windows 11 x64. The desktop uses Python, PySide6/Qt and SQLite; the optional RTSS bridge uses the Windows .NET Framework C# compiler. Cloud server code and migrations are under `sync_backend/`.

## Run from source

Use a patched CPython 3.13 x64 installation. Release builds require at least Python 3.13.16 and OpenSSL 3.5.9. In PowerShell, from the repository root:

```powershell
$env:PYTHONUTF8 = '1'
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-runtime.lock
.\.venv\Scripts\python.exe -B main.py --data-dir .\data
```

An explicit data directory keeps development separate from the installed profile. Use synthetic games and temporary profiles for tests; do not test uninstall behavior on real games.

For a source-based installation, run `Install.cmd`; use `Launch.cmd`, `Verify.cmd` and `Uninstall.cmd` to launch, check or remove it. The prebuilt installer linked from the main README is the normal end-user download.

## Tests

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

See [Testing](../TESTING.md) for native fixture tests, source installation checks and bundled upgrade checks. The full Windows suite exercises native windows and tray behavior; another application taking focus can interfere with interactive tests.

## Build the installer

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes -r packaging/requirements-build.lock
.\packaging\build.ps1 -PythonPath .\.venv\Scripts\python.exe
```

The build generates `dist/GameTimeMonitor-<version>-Setup.exe` and its SHA-256 file. It includes a replaceable Qt runtime, the original bridge, project documentation and license notices. The release process verifies actual SFX extraction and installation before updating the stable `downloads/GameTimeMonitor-Setup.exe` file and README links.

`-SkipFreeze` repackages an existing, verified frozen runtime with documentation changes. Verify the runtime hashes before and after such a repack; it must not substitute for rebuilding changed application code. `-FreezeOnly` stops after creating the frozen runtime.

## Optional backend

The supplied shared service is operated on a limited Supabase Free project. Using or contributing to the desktop app does not require deploying a replacement backend. Do not put administrative keys into the client, a public issue or Git history.

See [Backend setup](../sync_backend/README.md), [Architecture](../ARCHITECTURE.md), [Security](../SECURITY.md) and the original SQL migrations before changing the protocol. Preserve client-side encryption, user isolation, local budgets/history and server-only database grants.
