# Changelog

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
