# Isolated Supervisor and MQTT acceptance

Status: real Supervisor installation, Ingress API, MQTT device/entity lifecycle,
restart, backup/restore and same-version rebuild checks executed October 10, 2026.
See `validation.md` for versions and evidence. CNC data remained simulated.

## Local deployment and automated checks

`tools/start-ha-test.ps1` starts the Docker Compose harness in Ubuntu WSL and
keeps a WSL process alive while the test container runs. Open
`http://127.0.0.1:7123`. The official HA 2026.10 container serves HTTP on internal
port 80; port 8123 redirects there. Volumes preserve test data across restarts.
Stop only this environment with `docker stop fanuc-ha-test` in Ubuntu WSL.

Install runtime and development requirements separately as described in README.
For a **fresh isolated simulator configuration**, set these environment variables
in a terminal (use an admin access token from the test HA profile):

```powershell
$env:FANUC_HA_TEST_CONFIRM = 'isolated-simulation'
$env:FANUC_HA_TEST_TOKEN = '<test HA admin token>'
python tools/ha_acceptance/ha_acceptance.py
python tools/ha_acceptance/ha_lifecycle.py
python tools/ha_acceptance/ha_backup_test.py
```

Run in that order. These tests create, edit and delete simulator records, restart
the test add-on, broker and HA, then back up/restore/rebuild the test add-on.
They leave a `SIM Restore Test` machine for inspection. The first script rejects
nonempty configuration. The tools only accept localhost/127.0.0.1 port 7123 and
require explicit simulation confirmation; never forward production HA there.
Tokens are read from the environment, never committed. Results are written to
the ignored `tools/ha_acceptance/ha-acceptance-state.json` file.

## Environment

Use the official Home Assistant app development container, with a real
Supervisor and HA, so installation and Ingress can be tested. A plain Home
Assistant Core container cannot establish add-on installation acceptance.

The checked-in `.devcontainer/devcontainer.json` adapts the official configuration
and pins the resolved `6-apps` image index digest. Registry manifest resolution
succeeded, including its Linux amd64 entry; the image has now been run here.
HA and Supervisor versions selected at bootstrap must be recorded separately.

Prerequisites: a working WSL2 agent, Linux amd64 Docker engine, and VS Code with
the Dev Containers extension, or an equivalent devcontainer CLI launcher. Check
`uname -m`, `docker version`, and `docker info` before launching. Install missing
tooling only on the development machine, never on production HA.

The development container uses privileged mode for nested Docker/Supervisor,
as required by the official harness. It has dedicated named volumes and no
mount of the host Docker socket, production configuration, or CNC library.
The add-on itself does not request privileged mode. Do not replace the nested
engine with a production Docker socket. Use an isolated network with no CNC
route where possible, and keep collection mode `simulation` throughout.

Open this repository in the devcontainer, then run the **Start isolated Home
Assistant** task. Onboard the fresh instance at `http://127.0.0.1:7123` with
test-only credentials; do not restore a production backup. Install Mosquitto
from the test instance's store, start it, and configure the MQTT integration
using its discovered test broker. Do not enter production broker credentials.

The local app store should discover `fanuc_cnc_monitor` from this repository.
Install it, start it, and open its web UI through Ingress. Leave the hardware
gate disabled and mode set to simulation. Supervisor MQTT service discovery
should provide the test broker credentials automatically. The UI must report
broker connected and clearly label simulated data.

Official references:
- https://developers.home-assistant.io/docs/apps/testing/
- https://github.com/home-assistant/devcontainer/blob/main/apps/devcontainer.json
- https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery

## Acceptance sequence

Record source commit, image ID/digest, exact HA/Supervisor/Mosquitto versions,
timestamp and observed results. A checked box without evidence is not a pass.

1. Add two simulated machines using documentation addresses `192.0.2.20` and
   `192.0.2.21`: Test → Identify → editable suggested name → Save. Verify live
   details and independent read timestamps. No address is contacted in simulation.
2. In HA MQTT devices/entities, confirm exactly one device per machine, with
   sensor and binary_sensor entities only, including numeric units and structured
   alarm attributes. Verify there are no buttons/switches/command topics.
3. Rename a machine and change its documentation IP after retesting. Record
   device identifiers, entity unique IDs, and HA entity IDs before/after. They
   must remain stable, with no duplicate devices or entities.
4. Disable one machine. Its entities must become unavailable, while the other
   machine keeps updating. Re-enable and verify recovery. Test `offline.example`
   through the UI to observe failure and disabled Save; do not probe any real CNC.
5. Restart the add-on; restart HA; restart the broker. Verify recovery, retained
   discovery, fresh states, and no duplicate entities. While the broker is stopped,
   remove a machine, then restart the broker and verify retained cleanup completes.
6. Remove the final machine while connected. Verify its discovery/state retained
   topics are gone and entities are removed. Check the HA device registry for any
   empty leftover device: broker acknowledgement alone is insufficient evidence.
7. Back up the test add-on and restore into this isolated instance. Machine and
   installation IDs must survive. Test an upgrade/rebuild without losing settings.
8. Save evidence and update `docs/validation.md` and `docs/hardware-acceptance.md`.
   If any step fails, fix it and rerun the affected lifecycle checks.

## MQTT implementation

For each persisted CNC UUID the publisher retains one device-discovery config
under `homeassistant/device/fanuc_<installation UUID>/<machine UUID>/config`.
Its components reference state topics under
`fanuc_monitor/<installation UUID>/machine/<machine UUID>/signal/<signal hash>`.
HA receives this config and creates the device/entities; the user does not
maintain sensor YAML. Numeric readings retain units supplied by the collector.

State is published on changes, with periodic freshness refreshes before HA
expiry. Two availability topics must both be online: the service's LWT topic
and the machine's successful-read availability. A broker connection is not a
successful CNC read. The publisher subscribes only to `homeassistant/status`,
republishing after HA birth and broker reconnect. Removal queues empty retained
messages in a persistent journal until the broker acknowledges them. Schema
changes retain component removal markers. Full alarms are preserved as attributes.

This test validates actual HA discovery of **simulated data**. It does not
validate the proprietary native library, FOCAS ABI, or any real controller.
