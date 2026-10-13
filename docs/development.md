# Development

Use Python 3.12 and .NET SDK 10.0.401. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r fanuc_monitor/requirements.lock
pip install -r requirements-dev.txt
python fanuc_monitor/worker/prepare_binding.py
dotnet build fanuc_monitor/worker/Monitor.Worker.csproj --configuration Release
dotnet fanuc_monitor/worker/bin/Release/net10.0/Monitor.Worker.dll --self-test
pytest tests -q
npm ci --ignore-scripts
node --check fanuc_monitor/web/app.js
node --check fanuc_monitor/web/preferences.js
npm run test:frontend
npx playwright install-deps chromium
python tools/install_test_browser.py
# Use the printed UI_CHROMIUM_EXECUTABLE path for the next command.
UI_CHROMIUM_EXECUTABLE=/path/printed/by/installer npm run test:ui
```

For a local UI preview, run `python tools/test_broker.py`, then in another terminal
run `python tools/run_simulation.py --data ./data/simulation`. Open
`http://127.0.0.1:8099`. The preview broker binds loopback port 18883. Simulation
makes no CNC connections. `offline.example` exercises an unavailable machine.

GitHub Actions also builds the Linux image and verifies native exports without
network access. See [validation](validation.md) for the distinction between
software tests and hardware qualification. Older HA lifecycle helpers remain under
`tools/ha_acceptance/` for development, not normal installation.

Pinned upstream binding/runtime provenance and licensing information remain in
`fanuc_monitor/worker/upstream.lock.json`, `fanuc_monitor/native/provenance.json`
and `NOTICE.md`. Review any newly allowed native function before adding it.

## Prebuilt image releases

The validation workflow tests every change. Push a prepared release to a
`release/VERSION` branch to build/test/publish its versioned amd64 image to GHCR, without
exposing that version in the HA store yet. The publish job uses its repository's
`GITHUB_TOKEN` with package-write permission; no personal token is required.

The first GHCR package defaults to private. Set the package to Public once, then
run `python tools/check_image.py ghcr.io/hubertpi/fanuc-cnc-monitor:VERSION` to verify
anonymous download access. Advance `main` to the validated release commit only
after this check passes. HA uses `config.yaml`'s image/version to download it.
Branch-creation pushes validate code but do not publish. Advance the prepared release
branch with a normal push whose configuration version matches its branch suffix.
Both staging and main publishing require successful anonymous image access.
Existing version tags are immutable: republishing another commit under the same
version fails, so bump the version for any later change.
