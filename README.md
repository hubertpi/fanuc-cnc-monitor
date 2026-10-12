# Fanuc CNC Monitor

Read-only FANUC CNC monitoring for Home Assistant, with a local machine-management
interface, MQTT discovery, maintenance readings and shift utilization. Requires a
Supervisor installation on **Linux amd64**. Machines need an enabled FOCAS Ethernet
interface; the default port is **8193**.

## Install or update

1. Add `https://github.com/hubertpi/fanuc-cnc-monitor` to the Home Assistant
   app/add-on store's repository list.
2. Install **Fanuc CNC Monitor**, or refresh the store and update an existing install.
3. Configure MQTT. Empty broker settings use Supervisor's MQTT service automatically.
4. Set `mode: focas` and `hardware_testing_enabled: true` for real machines, then
   start the add-on and open its Web UI. Simulation mode is available for previewing
   the interface without contacting CNCs.
5. Add a machine manually, or scan its subnet for port 8193. Test FOCAS, review the
   controller identity, choose a name and save. Custom ports remain supported.

Home Assistant creates one MQTT device per machine. Existing machine UUIDs and
sensor identities survive updates. Updates download a prebuilt image from GitHub Container Registry; HA does not
compile the add-on locally. HA Container without Supervisor and ARM hosts are unsupported.

## Polling and diagnostic boost

Each CNC has one persistent connection and sequential read requests. It does not
push a continuous stream. Default polling targets are:

| Read group | Normal | Diagnostic boost |
| --- | --- | --- |
| Feedrate, RPM, execution, mode, emergency stop, alarm flag | 250 ms | 100 ms |
| Spindle/axis loads, tool code, feed override, alarm details, operator message | 1 s | 500 ms |
| Program number/comment, supported temperatures and power | 60 s | 5 s |

Intervals are configurable per machine. Slower native calls can extend these
periods; missed deadlines are skipped rather than queued. The boost expires after
10 minutes by default, with configurable duration and fast interval. Start/stop it
in the Web UI or Home Assistant. HA controls change **only the add-on's polling**.
A restart cancels active boosts. No CNC controls or write functions are exposed.

Only successful, validated readings create measurement entities. Unsupported
functions appear in diagnostics. Zero RPM, feedrate, load, power and override remain
valid. Zero-only temperature sensors are suppressed; a previously validated
temperature becomes unavailable if it later returns 0°C.
Every reported spindle gets an individual RPM reading when `cnc_acts2` is supported.
The CNC-selected, unnumbered RPM sensor is removed when numbered RPM readings
are available; otherwise it remains as a fallback.
Additional motor/encoder temperatures and motor power depend on controller support.
The current reader uses the default FOCAS path, up to four spindles and eight axes.

Program numbers use `Oxxxx`. Tool codes preserve the controller-reported number:
`T`/`TT`/`MT` controllers use at least four digits, and `M`/`MM` use at least two.
Separate mill offsets are not combined into the tool code. Feed override reads
the fixed, active-low PMC G12 byte; unsupported or malformed reads are not
converted into a fabricated 0%. Compare the reading with each CNC’s actual knob.

## Production utilization

The add-on measures confirmed **automatic execution with actual feedrate > 0**.
Spindle warmups and MDI do not qualify. This is feed-motion utilization, not the
full availability × performance × quality OEE formula; air moves may count, while
stationary cutting, dwell and tool changes do not.

Open **Shift schedule** in the Web UI to adjust the shared timezone, working days,
shift count (1–8), names, start/end times and breaks. The initial defaults remain
America/Chicago, Monday–Friday:

| Shift | Hours | Breaks |
| --- | --- | --- |
| First | 06:00–16:00 | 08:30–08:40, 11:00–11:30, 13:30–13:40 |
| Second | 16:00–02:00 next day | 18:30–18:40, 21:00–21:30, 23:30–23:40 |

The default shifts each have **550 planned minutes** after breaks. Overnight shifts belong to
their starting workday, including Friday's shift ending Saturday. In-progress
percentages use elapsed planned time. HA exposes percentage sensors named
**1st Shift OEE**, **2nd Shift OEE**, **OEE** (rolling 24 hours), **OEE Week** and
**OEE Month**. Additional configured shifts get their corresponding numbered OEE
sensors. Duration and coverage accounting remain internal and in diagnostic exports;
obsolete helper entities are removed automatically. Existing entity IDs are preserved.
Monitoring gaps remain in planned time but add no confirmed production.

Collection and local counters continue during HA Core or MQTT outages, provided
the add-on and CNC remain running. Reconnection publishes current totals; it does
not backfill every raw observation into HA Recorder. Historical duration detail is
limited to **seven days**. Small current-period totals survive beyond that to keep
month calculations intact. Schedule edits take effect when saved; earlier planned time is preserved using
bounded schedule-setting revisions. Removed shifts have their HA entities cleaned
up automatically. Configuration and data live in `/data` and are included
in add-on backups.

## Support and development

See [configuration and troubleshooting](fanuc_monitor/DOCS.md),
[architecture and safety](docs/architecture.md),
[FOCAS mapping audit](docs/focas-mapping-audit.md),
[validation and remaining hardware checks](docs/validation.md), and
[development](docs/development.md).

Real 0i controllers have supplied data and packet captures verified connection
reuse and clean shutdown. Newly added readings and faster polling still need
comparison on each controller; low network traffic is not proof of negligible CNC
processor load.

The bundled FANUC library is third-party software. See [NOTICE](NOTICE.md) and
[native provenance](fanuc_monitor/native/provenance.json); this project's license
does not grant additional FANUC SDK rights.
