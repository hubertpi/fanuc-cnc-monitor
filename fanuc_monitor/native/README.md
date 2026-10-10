# Bundled Linux FOCAS runtime

`libfwlib32-linux-x64.so.1.0.5` is copied unchanged from the public
[strangesast/fwlib repository](https://github.com/strangesast/fwlib).
`provenance.json` records the exact upstream commit, URL and SHA-256.

This is a third-party FANUC binary, not project-authored Apache-2.0 code.
Public availability alone does not establish its redistribution terms; no
additional FANUC license grant is asserted here. Upstream attribution is retained.

The image build verifies the checksum, loads the library and resolves every
allowlisted entry point without connecting to a CNC. Real controller ABI,
data accuracy and hardware compatibility still require hardware acceptance.

The bundled runtime is used by default in FOCAS mode. Setting an explicit
`native_library_sha256` selects the override at
`/share/fanuc/libfwlib32-linux-x64.so.1.0.5` instead, with mandatory hash checking.
