# Controller checks

Real 0i machines have returned controller/status/feed/load/program/alarm/message
readings. Packet captures on October 12, 2026 verified persistent TCP sessions and
clean shutdown. This establishes connection behavior, not correctness of every
measurement or a sustainable 100 ms polling rate.

For each controller, compare these against its display/manual:

| Area | Check |
| --- | --- |
| Fast readings | Actual feedrate and per-spindle RPM, units/scaling and freshness |
| State | Automatic/MDI/manual, active/hold/stop, emergency stop |
| Maintenance | Axis/spindle loads, diagnostic existence/type, temperatures and power units |
| Tool/override | Modal T-code meaning; software-panel feed override matches display |
| Program | Current/main program and comment |
| Alarm/message | Axis-qualified OT, multiple alarms, message length and clearing |
| Load | Response latency, errors, screen responsiveness and repeated cycle timing at chosen rates |
| Recovery | CNC restart/disconnect, add-on stop, MQTT/HA outages and reconnect |

Only the default FOCAS path is read. The pinned layouts currently bound readings
to four spindles/eight axes. Software/fake-library tests do not qualify additional
controller models or options.
