# Validation record

October 10, 2026. All HA tests used simulated CNC data; no production equipment.

Public source snapshot `fe1d4eb` passed [GitHub Actions](https://github.com/hubertpi/fanuc-cnc-monitor/actions/runs/38034117108),
including Python tests, Linux image build, worker self-test and network-disabled
native library load/export verification. Adding the public repository URL to
the isolated Supervisor store installed `8393d05f_fanuc_cnc_monitor` successfully.
Its Ingress API and automatic MQTT credentials worked, and a new simulator
created one HA device with 17 live entities. This validates installation from
GitHub, not only the local development mount.

- 30 Python tests passed, including a real loopback MQTT broker, persistence,
  MQTT lifecycle, read-only allowlist and native-package integrity checks.
- Linux amd64 image built and installed by Supervisor 2026.09.3 with HA Core
  2026.10.0 and Mosquitto 7.1.1 in the isolated official development container.
- Two simulated machines produced one device and 17 live entities each in HA.
- Ingress API and automatic Supervisor MQTT credentials worked.
- Rename/readdress preserved device IDs, entity IDs and unique IDs.
- Disable/re-enable affected only the selected machine.
- Add-on, broker and HA restarts restored live states without duplicate entities.
- Deletion during a broker outage survived a collector restart, removed actual
  HA devices/entities after reconnection and drained the retained cleanup queue.
- Connected deletion removed both device and entities.
- Supervisor partial backup/restore recovered settings after a deliberate edit.
  Same-version image rebuild preserved settings and identifiers.
- Bundled FOCAS library loaded and resolved all 15 permitted exports in a Linux
  container with networking disabled. Native initialization succeeded; an
  unavailable container-local loopback endpoint returned EW_SOCKET (-16).

Reproduce HA lifecycle checks with `tools/ha_acceptance/`; see
[isolated HA procedure](isolated-ha-test.md). Native source, checksum and revision
are in `fanuc_monitor/native/provenance.json`. Project development history is
preserved locally; this public repository starts from the tested source snapshot.

Pending: real controller ABI/data correctness, hardware soak, controller-specific
feed/tool interpretation, cross-version migrations and independent retained-topic
inspection. Public binary redistribution terms remain unverified; its inclusion
does not assert a new FANUC license grant. See [hardware matrix](hardware-acceptance.md).
