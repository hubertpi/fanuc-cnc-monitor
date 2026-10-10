# Installation, configuration and diagnostics

## Installation

Add `https://github.com/hubertpi/fanuc-cnc-monitor` under the Home Assistant
app/add-on store's Repositories menu. Install **Fanuc CNC Monitor**, leave the
defaults in simulation mode, start it, and open its Web UI. Requires Supervisor
and Linux amd64. HA builds from source; installation can take several minutes.

Install/start Mosquitto in the test HA instance and accept its MQTT integration
discovery. The monitor obtains broker credentials from Supervisor automatically.
Use an isolated instance initially. Actual Supervisor install, Ingress API,
MQTT lifecycle and backup/restore have passed using simulated machines.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| mode | simulation | Simulation performs no CNC networking; focas requires hardware gate |
| hardware_testing_enabled | false | Separate explicit hardware step; never auto-enabled |
| native_library_sha256 | empty | Empty uses bundled runtime; nonempty selects /share/fanuc override |
| mqtt_host | empty | Empty uses Supervisor MQTT service discovery |
| mqtt_port | 1883 | Explicit broker port |
| mqtt_username/password | empty | Explicit broker credentials; not exposed in diagnostics |
| mqtt_tls | false | Verify TLS using system trust; no insecure TLS option |

Simulation still publishes to the configured MQTT broker. Use an isolated test
broker and HA instance for validation. The add-on does not require a second
broker for normal deployment. Supervisor service unavailability is retried;
manual broker failures use bounded reconnect delay.

## Machine management

Enter an IP or DNS name, default FOCAS port 8193, and bounded timeout. Test
connection, inspect returned controller information, edit the suggested name
and save. Successful endpoint tests expire after five minutes. Live native
resolution currently requires IPv4. Per-machine interval is 1–60 integer seconds,
default 1; actual sweep period includes read time. Edit or disable one machine
without restarting other collectors. Details show source, units, read timestamps,
errors, retries, and MQTT acknowledgement. Discovery acknowledgement confirms
broker delivery, not proof that HA created an entity.

Remove requires UI confirmation and queues durable retained-topic tombstones.
Cleanup completes after broker acknowledgement. Broker outage is not deliberate
machine removal. Unsupported native groups are shown separately from transport
failure; raw diagnostic codes are not falsely labeled tool numbers or percent.

## Hardware step (not authorized or performed)

Only after explicit authorization, provide the verified CNC FOCAS IPv4/port,
controller/model/options, segmented network reachability and applicable SDK
license. The bundled Linux library is selected when the digest option is empty. For
an override, supply `libfwlib32-linux-x64.so.1.0.5` under `/share/fanuc/`, compute
its SHA-256 and configure the digest. Select focas mode and enable hardware testing
only during that agreed step. Missing gate/library, incorrect digest or architecture fails
closed. There is no fallback that reports simulated reads as real hardware.
See ../docs/hardware-acceptance.md for the pending matrix.

## Persistence and recovery

`/data/machines.json` stores schema version 1 and machine UUIDs/revisions.
`/data/mqtt-journal.json` stores installation identity and desired retained topics.
Back up and restore these together using the add-on backup mechanism; partial backup/restore
was verified on isolated Supervisor with simulated machines. Keep IDs during upgrades.
Unknown/corrupt schema fails closed rather than resetting identities. Offline
startup clears previous state until fresh reads. Do not manually delete the
journal to repair a broker issue: that could orphan discovery under old IDs.

Export diagnostics from the UI for errors and timestamps. Diagnostics exclude
passwords/tokens, but contain machine addresses and observations. Protect backups
and exports as local operational data. This add-on has no CNC command API.
