# Hardware acceptance — pending, no CNC connection performed

An MTConnect agent address is not necessarily a CNC FOCAS endpoint.
No automatic subnet scanning is performed.

Before the separate explicit test step, obtain the actual FOCAS IPv4/port, machine
model, controller series/version/options, SDK license/provenance and segmented
network reachability. Leave Windows monitoring running for comparison/fallback.
Do not cut over until evidence supports acceptance.

| Gate | Evidence required | Current result |
| --- | --- | --- |
| Linux native load/ABI | Licensed .so loads and correct structures returned | Linux load/export resolution passed; controller ABI not run |
| Connection/controller | Exact CNC endpoint, sysinfo and state valid | Not run |
| Execution/mode/estop | Values match operator/controller displays | Not run |
| RPM/spindle/axis loads | Per-channel scale and units verified | Not run |
| Feed rate | Inch/metric and decimal metadata match display | Not run |
| Feed override/tool | Controller-specific percent/selected tool mapping | Unresolved; raw codes only |
| Program/comment | Number and bounded directory comment match | Not run |
| Alarms/messages | Multiple alarms, code/type/axis, clearing/truncation | Not run |
| Isolation | Offline target cannot interrupt healthy second machine | Simulation only |
| HA installation/Ingress | Isolated Supervisor installs and UI base path works | Passed with simulator via real Ingress API |
| MQTT device creation | Actual HA creates exactly one device per machine | Actual HA: two devices, 17 entities each; simulation |
| Lifecycle | Rename/readdress/restarts/removal leave no ghosts in HA | Actual HA rename/readdress/restarts/removal passed; simulation |
| Reliability | Sustained soak, failures, recovery, stale state and shutdown | Partial simulation only |
| Release rights | Binding/native license and image notices approved | Unresolved |

Record timestamp, image/source digest, library digest, controller identity,
observed/reference values and failures for each real test. No row may be marked
passed solely because the simulator returned a plausible value.
