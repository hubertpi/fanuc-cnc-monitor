# Fanuc CNC Monitor

Home Assistant add-on source with an Ingress machine-management interface,
independent read-only collectors, durable MQTT device discovery and diagnostics.
The UI supports **IP → Test → Identify → Suggested name → Save**, without
machine-specific YAML. Each machine has its own persistent identity and independent collector.

**Experimental testing build, Linux amd64 only.** Installed and tested in real
Home Assistant with simulated CNCs: MQTT discovery, independent availability,
rename/readdress, restarts, removal, backup/restore and same-version rebuild.
The bundled Linux FOCAS library loads and resolves all 15 allowed entry points;
native initialization and loopback connection failure were tested without
external networking. Real controller data and ABI compatibility are unverified.

## Install in Home Assistant

Requires Home Assistant OS or another Supervisor installation with the app/add-on
store, on an **x86-64/amd64** computer. HA Container alone and ARM/Raspberry Pi
installations are not supported by this build.

1. In an isolated test HA instance, install/start the **Mosquitto broker** app
   and configure the discovered **MQTT** integration under Settings → Devices &
   services. An existing compatible broker can also be configured manually.
2. Open Settings → Apps (called Add-ons on older versions) → app/add-on store.
   Open the three-dot menu → Repositories, and add:
   `https://github.com/hubertpi/fanuc-cnc-monitor`
3. Refresh the store, open **Fanuc CNC Monitor**, and select **Install**. HA
   builds the image locally; the first install downloads pinned dependencies
   and can take several minutes. Check Supervisor logs if it fails.
4. Keep `mode: simulation` and `hardware_testing_enabled: false`. Start the
   app and select **Open Web UI**. Optionally enable its sidebar entry.
5. Confirm MQTT is connected. Empty MQTT settings use Supervisor credentials;
   there is no separate sensor YAML or custom HA integration to install.

## First use

In the management UI, add `192.0.2.20` with port `8193`, select **Test
Connection**, review the simulated controller, choose a name, then save.
Simulation never connects to the address entered. Try `offline.example` to
exercise connection failure. Add another machine to test independent collection.

Look under Settings → Devices & services → MQTT for one device per machine,
with its sensor/binary-sensor entities. Details in the app show readings, source
names, freshness, errors and MQTT publication status. Rename/edit preserves HA
identifiers; disable marks that machine unavailable; remove clears discovery
and state, including deferred cleanup after a broker outage.

## Real FANUC testing

The Linux library is **included** in this repository and installed image.
After arranging an explicit hardware test, remove simulator records, select
`mode: focas`, enable `hardware_testing_enabled`, restart, and add the verified
CNC FOCAS IP/port. Leave `native_library_sha256` empty to use the bundled runtime.
Supplying a digest instead selects a matching library in `/share/fanuc/`.
Keep existing monitoring running until values have been compared with the CNC.
See [hardware acceptance](docs/hardware-acceptance.md) for the pending checks.

The FANUC binary is third-party software, outside this project's Apache-2.0
license. Its pinned source and checksum are in [native provenance](fanuc_monitor/native/provenance.json);
no additional license grant is asserted. Hardware control commands are not
exposed by this app. Controller-specific tool/feed-override readings remain raw.

## Isolated development preview

Use Python 3.10+ and .NET SDK 10.0.401. From this repository:

```sh
python -m venv .venv
# Activate the environment using the command for your shell.
python -m pip install --require-hashes -r fanuc_monitor/requirements.lock
python -m pip install -r requirements-dev.txt
python tools/test_broker.py
# In a second terminal using the same virtual environment:
python tools/run_simulation.py --data ./data/simulation
```

Open `http://127.0.0.1:8099`. The broker binds only loopback port 18883. The
simulator never connects to entered CNC addresses. Use `192.0.2.20` for success
or `offline.example` to exercise a failed connection test.

```sh
python fanuc_monitor/worker/prepare_binding.py
dotnet build fanuc_monitor/worker/Monitor.Worker.csproj
dotnet fanuc_monitor/worker/bin/Debug/net10.0/Monitor.Worker.dll --self-test
python -m pytest tests -q
docker build -t fanuc-cnc-monitor:dev fanuc_monitor
```

Binding preparation downloads pinned, SHA-256 checked upstream source and strips
imports outside the allowlist. The native runtime is bundled and hash-checked during builds.
Runtime wheels and base images are pinned by hashes/digests; Ubuntu packages use
a fixed snapshot. The supplied Linux CI workflow has not run locally.

## Documentation and validation

See [configuration and troubleshooting](fanuc_monitor/DOCS.md),
[upstream audit](docs/upstream-audit.md), [architecture](docs/architecture.md),
[validation](docs/validation.md), and [isolated HA tests](docs/isolated-ha-test.md).
This is a source-build testing draft, not a hardware-qualified release.
