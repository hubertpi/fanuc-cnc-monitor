# Ladder99 source and dependency audit

Reviewed 2026-10-09: Ladder99/fanuc-driver revision
`b9080d0938757789159714c38305fe559728e146`; base-driver submodule
`12859194171ea54dc96795ab4fce37a04f99fe97`. This is source/ELF inspection and
managed compilation, not Linux native execution or hardware qualification.

## Linux and dependencies

Upstream Linux64 targets .NET 9 and LINUX64. ARM uses ARMV7, not aarch64. The
inspected native x64 library SHA-256 is
`0304931e1366e57ff19f42021f84ac2cb694b0b2c764e0b99d81317ee0880d84`.
ELF inspection found 64-bit little-endian x86-64 (machine 62), dependencies
`libstdc++.so.6`, `libgcc_s.so.1`, `libc.so.6`, and referenced GLIBC versions
2.2.5, 2.3.4, 2.4, 2.14 and 2.15. Native loading and structure ABI execution
remain untested. Ubuntu/glibc is selected; Alpine compatibility is not assumed.

The upstream project references MQTTnet, linked base-driver sources and
SparkplugNet.dll. Its older standalone Linux guide still refers to .NET Core
3.1. The constrained new worker targets .NET 10 without external NuGet packages.
Local compilation and self-tests pass; Linux runtime qualification remains open.

Sources: [Dockerfile](https://github.com/Ladder99/fanuc-driver/blob/b9080d0938757789159714c38305fe559728e146/Dockerfile.LINUX64),
[project](https://github.com/Ladder99/fanuc-driver/blob/b9080d0938757789159714c38305fe559728e146/fanuc/fanuc.csproj),
[binding](https://github.com/Ladder99/fanuc-driver/blob/b9080d0938757789159714c38305fe559728e146/fanuc/fwlib.cs).

## Licensing

Ladder99's project is Apache-2.0. The fwlib.cs binding separately contains FANUC
copyright and an all-rights-reserved notice. Native library AND binding
redistribution rights are unresolved; the repository license does not establish
them. Generated binding source preserves the copyright and marks modifications.
No native FANUC binaries are included or downloaded by the build.

An operator-supplied licensed Linux amd64 library is mounted read-only from
`/share/fanuc/`, checked against the supplied SHA-256 and ELF architecture. The
build DOES compile FANUC binding definitions into the managed worker: omission
of the native binary alone does not resolve public image redistribution. CI
builds without publishing. No SparkplugNet binary is used. See [notices](../NOTICE.md).

## MQTT and collector selection

Inspected Ladder99 MQTT transport sends retained JSON on DATA_ARRIVE, SWEEP_END
and INT_MODEL. It supports topic templates, TCP/WebSocket selection, credentials
and reconnect handling during sweeps. The inspected implementation did not
provide HA device discovery, HA birth subscription, LWT or TLS. Configuration
examples alone do not establish Home Assistant lifecycle correctness.

Upstream supports machine lists and collector composition. Its broader platform
also exposes Reset and ProgramUpload, and StateData combines optional reads
with PMC assumptions including G12/G14/G30. Running it unchanged would not
satisfy the requested narrow native callable boundary or general metric semantics.

This implementation adapts pinned upstream binding definitions, retains only
15 explicit session/read imports, and runs independently bounded read groups in
one .NET worker per machine. It does not run the full Ladder99 driver or claim
a successful upstream Linux build. This scope reduction still requires native
ABI and hardware qualification. Paho handles application MQTT independently.

## TrakHound polling reference

TrakHound/Fanuc-MTConnect-Agent revision
`efe91623c3f314973910bff769869e1c939174a0` ships Windows binaries/templates. Its
README identifies mtconnect/adapter as their base. Inspected 0id/30i templates
have no scanDelay override. That upstream defaults to 100 ms, configurable with
`[adapter] scanDelay` in milliseconds. The loop gathers/sends data then sleeps,
so actual cycle time includes read work; gathering occurs when clients connect.
This source-derived default does not establish the user's installed interval.

Sources: [TrakHound](https://github.com/TrakHound/Fanuc-MTConnect-Agent),
[default](https://github.com/mtconnect/adapter/blob/master/src/adapter.hpp),
[loop](https://github.com/mtconnect/adapter/blob/master/src/adapter.cpp),
[Fanuc option](https://github.com/mtconnect/adapter/blob/master/fanuc/fanuc_adapter.cpp).
