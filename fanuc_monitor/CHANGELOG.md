# Changelog

## 0.3.1

- Read feed override from the fixed, read-only PMC G12 byte; preserve genuine 0% and overrides above 100%.
- Format program numbers as Oxxxx and tool codes by detected machine type; MT uses lathe formatting.
- Remove redundant CNC-selected RPM entities when numbered spindle RPM is available.
- Suppress zero-only temperature entities; previously validated temperatures become unavailable on 0°C.
- Expose only OEE percentages with the requested names; remove duration/coverage helper entities while retaining internal accounting.
- Preserve existing sensor identities and persist validated temperature capability across restarts.

## 0.3.0

- Add a shared UI editor for 1–8 shifts, names, start/end times, breaks, working days and timezone.
- Apply schedule edits prospectively and preserve existing utilization totals and earlier planned time.
- Clean up entities for removed shifts and use configured shift names in HA.
- Hide/skip already configured discovery endpoints, including disabled machines.
- Publish tested, versioned amd64 images to GHCR for HA to download without compiling.
- Stop per-machine workers concurrently to avoid cumulative shutdown delays.


## 0.2.0

- Separate 250 ms fast, 1 s status and 60 s diagnostic/program read groups.
- Add individual spindle RPM, validated feed override and bounded operator messages.
- Add supported motor/encoder temperatures, motor power and axis overtravel.
- Add timed diagnostic boost in the UI and local-only HA switch/number controls.
- Add manual/custom-port onboarding and bounded subnet discovery.
- Add local shift/24-hour/week/month feed-motion utilization, coverage and unknown time.
- Handle overnight shifts, weekday schedules and all six scheduled breaks.
- Retain seven days of minute details and small current-period counters.
- Continue collecting independently of HA/MQTT; start in Supervisor services stage.
- Batch persistence, preserve existing machine identities and simplify documentation.


## 0.1.2-dev

- Reuse one FOCAS connection per machine across successful polling sweeps.
- Release and reopen the connection after read failures or endpoint changes.
- Close workers through stdin EOF so native handles are released on their owning
  thread; force-stop workers that do not exit within two seconds.
- Add session lifecycle self-tests and cooperative/hung worker shutdown tests.
- Per-machine polling intervals remain configurable from 1 to 60 seconds.

## 0.1.1-dev

- Bundle the pinned C# FOCAS binding source and verify its existing SHA-256
  locally. Removes the install-time GitHub Raw HTTPS request that failed on
  some HA hosts with `CERTIFICATE_VERIFY_FAILED`.
- TLS certificate verification remains enabled for other package downloads.
- Linux FOCAS runtime is included; hardware qualification is still pending.

## 0.1.0-dev

- Ingress management with tested-endpoint onboarding and editable names.
- Atomic configuration, UUIDs, isolated machine tasks and diagnostics.
- Restricted native read/session allowlist and .NET 10 worker.
- Durable device discovery, QoS 1, availability, reconnect and cleanup.
- Simulator, real test-broker tests and pinned build inputs.
- Development build: Linux/HA installation and hardware acceptance remain open.
