# Third-party notices

Project-authored code is Apache-2.0; see LICENSE. Binding declarations are
adapted from the pinned Ladder99/fanuc-driver revision in worker/upstream.lock.json.
Its fwlib.cs also carries FANUC copyright/all-rights-reserved terms. Binding
preparation preserves that notice and marks the restricted-import modification.
FANUC binding/native SDK redistribution permissions remain unresolved. The Linux amd64 native library is included from strangesast/fwlib; see
fanuc_monitor/native/provenance.json for its source and checksum. It is outside
the Apache-2.0 license for project-authored code. This notice is not a FANUC SDK license.

Runtime dependencies include Python (PSF), .NET (MIT and bundled notices),
FastAPI/Starlette/Pydantic/Uvicorn/HTTPX and supporting Python packages (their
package licenses), and Eclipse Paho (EPL-2.0/EDL-1.0). Test-only AMQTT is MIT.
Runtime distributions/hashes are in requirements.lock. Preserve upstream notices;
a complete image/SBOM review remains required before any public release.
