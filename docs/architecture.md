# Architecture and boundaries

FastAPI owns versioned configuration, Ingress routes and endpoint-test tokens.
The UI uses relative URLs under a validated Ingress base path. Production allows
only the Supervisor Ingress socket peer; forwarded headers cannot grant access.
Mutations require CSRF tokens. The development server binds loopback separately.

Store writes atomic JSON under `/data`. Stable machine UUIDs and optimistic
revisions survive rename, readdress and restart. Tests expire after five minutes
and are scoped to host, port and timeout; a new/changed endpoint cannot save
without its successful test token. There is no subnet scan.

Manager runs one collector task per enabled machine. Edit/disable/remove cancels
only that task. Each live collector owns a bounded worker process. Synchronous
FOCAS calls stay on its single main thread; one session handle is reused across
successful sweeps. Endpoint changes or failed reads release the handle; transport
failures close that worker and back off independently. Shutdown sends stdin EOF
to release the handle before native process cleanup, with a two-second forced
termination fallback for hung calls. Overall
freshness is separate from broker connectivity.

The generated native binding contains only worker/allowlist.json imports.
Tests compare generated imports, call sites and allowlist, including EntryPoint
remapping rejection. Optional read failures remain group diagnostics; required
controller/state and transport failures mark offline. Decimal scale and units
come from supported FOCAS metadata, never a blanket MTConnect division.

Publisher stores a durable retained-topic journal with QoS 1 acknowledgements,
LWT, machine availability and HA birth/reconnect republication. Device IDs use
persistent machine UUIDs and stable signal identities. Changed values publish;
unchanged values refresh before expiry. Durable tombstones clear removals and
schema changes. The only MQTT subscription is HA birth; no controls are exposed.

Structured alarms publish count as state and full code/type/axis/text in
attributes. Oversized text retains full details. Diagnostics exclude broker
passwords and Supervisor tokens, but contain addresses and operator messages.

Native limits: default CNC path, eight axes, four spindles, ten alarm records,
and first operator message. Generalized selected-tool and percent feed-override
mappings remain unverified: raw modal/panel codes are diagnostic values without
invented units. Simulator values are not evidence of native metric support.
