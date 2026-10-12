# Validation

## 0.3.1 — October 12, 2026

Local validation: **65 Python tests passed**, .NET Release build and both worker
self-tests passed. Tests cover fixed G12 address/type/length, genuine zero and
above-100% override decoding, malformed/reserved response suppression, MT tool
and O-number formatting, numbered RPM replacing the selected-spindle fallback,
zero-temperature handling, persistent temperature capability migration, and OEE
helper removal with stable percentage identities. JavaScript syntax and diff
whitespace checks passed. The binding still exposes four session functions and
fourteen reads, replacing the software-panel read with the fixed PMC read.

The staging workflow validates the full container and publishes the image before
promotion to main. Override values and temperature meanings still require
comparison with each installed CNC; these are software tests, not live hardware
qualification.

## 0.3.0 — October 12, 2026

Local validation: **63 Python tests passed**, including schedule validation,
overnight/week-boundary overlap, daylight-saving elapsed time, prospective schedule
edits, restart persistence, optimistic revision checks, timezone changes without
losing current totals, and discovery filtering for configured/custom-port endpoints.
The JavaScript syntax check passed. The native read/session allowlist is unchanged.

The release branch builds and publishes the prebuilt image only after the complete
validation/container checks pass. Anonymous GHCR access must pass before promotion
to main. See the workflow run for current registry/build status.


## 0.2.0 — October 12, 2026

Local validation: **48 Python tests passed**, .NET Release build passed with no
warnings/errors, and both worker self-tests passed. Checks include:

- Python tests for onboarding, stable IDs, partial read groups, boost settings and
  expiry, bounded discovery/cancellation, shift breaks, overnight ownership,
  conservative gaps, restart persistence and seven-day retention.
- A real loopback MQTT broker for retained discovery, HA birth replay, outage,
  deletion and reconnect. Its outage fixture closes accepted transports and
  listeners before restarting, fixing an intermittent address-in-use failure.
- A Release .NET worker build and session/mapping self-tests.
- The real worker against a fake native library: specified-spindle RPM including
  valid zero, correct override selector/scaling, message length/clearing, supported
  diagnostic metadata and signed power, missing-diagnostic suppression, partial
  fast reads, connection reuse/recovery and EOF cleanup.
- Native library load and resolution of all 18 allowlisted entry points without
  allocating a CNC connection.
- Exact native import/call allowlist checks and JavaScript syntax checks.

These tests validate software behavior. New maintenance mappings, polling rates
and HA boost controls still need comparison in the user's installed environment.
GitHub Actions additionally builds the complete Linux image and repeats native
load checks with networking disabled; consult the workflow for its current result.

## Existing hardware evidence

Three real 0i controllers returned system/status/feed/load/program/alarm/message
readings. Two packet captures on October 12 verified reuse of the recurring TCP
connection and clean FIN/ACK shutdown when the add-on was stopped. Captured
traffic was approximately 2 KB/s at the earlier polling configuration. That does
not measure controller CPU load or qualify the new faster polling configuration.

An earlier isolated Supervisor install verified Ingress, MQTT device creation,
identity preservation, restart/removal and backup/restore using simulated CNC data.
That result is installation/lifecycle evidence, not hardware measurement validation.

See [controller checks](hardware-acceptance.md) for the remaining comparisons and
[development](development.md) to reproduce local checks. Native provenance and
license notices remain in the repository.
