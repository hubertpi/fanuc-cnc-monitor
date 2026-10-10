# Pinned binding source

`fwlib.cs.txt` is the unchanged source from
https://github.com/Ladder99/fanuc-driver/blob/b9080d0938757789159714c38305fe559728e146/fanuc/fwlib.cs

The adjacent `../upstream.lock.json` pins its canonical LF SHA-256. Build-time
generation verifies that digest, selects LINUX64 and removes every import outside
the explicit read/session allowlist. The original copyright notice is preserved.
This third-party source is not covered by the license for project-authored code.
Bundling removes an otherwise unnecessary network dependency during installation.
