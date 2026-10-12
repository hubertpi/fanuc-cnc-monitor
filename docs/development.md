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
