# Configuration and troubleshooting

## Add-on options

| Option | Default | Purpose |
| --- | --- | --- |
| mode | simulation | `simulation` makes no CNC connections; `focas` reads real machines |
| hardware_testing_enabled | false | Required explicitly for FOCAS mode |
| native_library_sha256 | empty | Empty uses the bundled runtime; nonempty verifies a library override in `/share/fanuc/` |
| mqtt_host | empty | Empty uses Supervisor's MQTT service |
| mqtt_port | 1883 | Port for an explicit broker |
| mqtt_username/password | empty | Credentials for an explicit broker |
| mqtt_tls | false | TLS with system certificate verification |

For the Mosquitto add-on, leave the broker fields empty or use `core-mosquitto`.
Ensure the Home Assistant MQTT integration is configured to see discovered devices.
Simulation still publishes to MQTT; use a separate test broker when experimenting.

## Machines and discovery

The scanner checks a user-selected IPv4 subnet, at most /22 (1,024 addresses), with
16 concurrent TCP probes and a 500 ms timeout. It runs only when requested. Already configured IP/port pairs are skipped,
including disabled machines; a different port on the same IP remains a candidate.
Results also hide machines added while a scan is running. An open
port is a candidate, not proof of a FANUC controller. A successful FOCAS test of the
exact IP/port/timeout is required before adding or readdressing a machine; the test
expires after five minutes. IPv4 DNS names and manual/custom-port entry are supported.

Per-machine settings: fast interval 0.1–60 s (default 0.25), status interval 1–60 s
(default 1), diagnostic/program interval 5–600 s (default 60), boost fast interval
0.1–1 s (default 0.1), and boost duration 1–60 min (default 10). During boost, status
reads use at most 0.5 s and slow reads at most 5 s. HA exposes a boost switch and
numeric duration/fast-interval settings. These are local scheduler settings only.
Changing HA numeric settings applies to the next boost. UI edits restart only the
selected machine's collector and cancel its boost.

The Details view and diagnostic export include sources, last-read times, units,
unsupported reads, read duration, errors, reconnect attempts and MQTT acknowledgements.
MQTT acknowledgement means broker receipt, not proof HA created an entity.

## Shared shift schedule

Open **Shift schedule** in the Web UI. Configure 1–8 named shifts, start/end times,
working days (shift start days), timezone and up to 12 breaks per shift. Breaks use
start time and duration in minutes. An end earlier than its start means next day.
Shifts and breaks cannot overlap; breaks must fit inside their shift. Sunday-to-Monday
and daylight-saving boundaries are handled in the configured timezone.

Settings are shared by all machines and stored in `/data/schedule.json`. Upgrades
from 0.2.0 keep the existing two-shift Chicago schedule without resetting machine
IDs or counters. Edits take effect when saved, not retroactively. A bounded set of
configuration revisions preserves the historical planned-time denominator for the
current calendar month/week and rolling day. This is configuration metadata, not
additional machine history. Timezone changes adjust the calendar boundaries of
future periods. Existing shift sensor identities follow their numbered slots;
removed shift entities are removed from MQTT discovery.

## Reading interpretation

- `spindle_rpm` preserves the original CNC-selected spindle reading. Individual
  `spindle_N_rpm` entities use specified-spindle `cnc_acts2` reads.
- Feed override selects the documented software-panel field and converts valid
  codes 0–20 to 0–200%. Unsupported or invalid values create no percent sensor.
- `tool_code` formats the modal T code with at least four digits. On a lathe it can
  contain both tool and offset; it is not universally the physical tool number.
- Axis overtravel derives from axis-qualified OT alarms, not generic alarm presence.
- Temperature mappings: diagnostic 308 motor, 309 encoder, 403 spindle motor.
  Power mappings: 4901 servo, 4902 spindle. Diagnostic existence and data type are
  checked before reading. Confirm meanings/units against the controller manual.
- Unsupported readings create no placeholders. Failed optional readings are removed
  until a valid reading returns. Slow readings retain their actual acquisition time.

## Persistence and outages

Back up the add-on's `/data` directory as a unit:

- `schedule.json`: shared schedule, edit revision and effective setting revisions.
- `machines.json`: stable UUIDs, revisions and polling settings.
- `mqtt-journal.json`: installation identity, latest retained states and cleanup.
- `utilization.sqlite`, with its SQLite sidecars: minute totals and period counters.

Minute history is pruned to seven days every minute; deleted pages are reused. The database
stores durations, not raw 100 ms samples. Current shift/week/month counters are small
fixed records per machine. Counters and the MQTT journal checkpoint every 15 seconds;
a sudden power loss may lose the latest uncommitted interval, reducing coverage.
A normal stop flushes them. Do not delete the journal to fix a broker issue: doing so
can orphan MQTT discovery identities.

HA Core and MQTT are independent of CNC collection. The add-on starts in Supervisor's
services stage; MQTT availability is retried. Utilization and coverage remain visible during CNC outages; live CNC readings become unavailable.
Monitoring gaps count as unknown time
and do not add production. Breaks are excluded from numerator and denominator.
Rolling 24-hour values have minute-level boundary accuracy. Week/month ownership
follows the shift start day. Removing a machine also removes its local statistics.

## Common problems

- **No update shown:** refresh the app/add-on store, then reopen the add-on page.
- **Hardware disabled:** choose `focas`, enable the hardware option and restart.
- **Connection error:** check the CNC's actual FOCAS IP/port and Ethernet options.
  An MTConnect agent IP is a different endpoint.
- **Missing sensors:** inspect unsupported reads. Different CNC models/options
  provide different functions; a successful connection does not validate every field.
- **Missing second spindle RPM:** check whether the load read reports that spindle
  and whether its specified-spindle `cnc_acts2` read succeeds.
- **Slow responses:** inspect read duration, increase intervals and check for other
  FOCAS clients. Native requests do not overlap on one CNC.
- **MQTT offline:** collection continues. Check broker credentials and the HA MQTT
  integration; latest totals and retained states are republished on recovery.

Diagnostic exports omit broker credentials but contain machine addresses and data.
