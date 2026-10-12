# Architecture and read-only boundary

Each machine has an independent Python collector task and .NET worker process.
The worker owns one persistent FOCAS handle on one OS thread. Requests contain only
endpoint fields and fixed read-group names. Native calls run sequentially; errors
invalidate the session, and that machine reconnects with bounded backoff. EOF closes
its handle; hung workers are terminated after a two-second shutdown grace period.

The generated binding retains only the exact functions in
`fanuc_monitor/worker/allowlist.json`: four session/process functions and fourteen
reads. Source preparation verifies the immutable upstream SHA-256, resolves the
Linux ABI and rejects unrecognized imports or altered entry points. Tests require
worker calls and generated imports to match the allowlist exactly. Feed override
uses only `pmc_rdpmcrng` at fixed G12, one byte, with returned address/type validation.
No address or PMC operation can be supplied through an API request.

No CNC start/stop/reset/jog, spindle/feed commands, program transfer, parameter
writes or PMC writes are available through the binding. The underlying third-party
library contains other functions, but this application cannot import or dispatch
them. MQTT commands are restricted to the add-on's diagnostic boost, its duration,
and its fast read interval. Retained commands are ignored. There is no arbitrary
FOCAS function selector, code evaluation, or raw CNC command endpoint.

The Web UI uses Supervisor Ingress and CSRF protection; no host port is published.
Discovery is a bounded, user-started TCP scan. Saving a new endpoint requires a
successful FOCAS identity/read test, not merely an open port.

SQLite accumulates confirmed scheduled production/observed durations in minute
rows, with seven-day retention and current period counters. HA/MQTT availability
has no role in production classification. MQTT maintains latest retained states,
QoS 1 acknowledgement, HA birth/reconnect replay and durable deletion tombstones.
Both stores checkpoint periodically, with normal shutdown flushes.

Controller response latency can extend polling intervals. Network payload volume
and maximum client counts do not measure CNC CPU headroom. Faster reads and new
maintenance mappings require controller-specific comparison.
