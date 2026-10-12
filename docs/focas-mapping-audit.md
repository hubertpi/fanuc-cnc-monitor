# FOCAS mapping audit — October 12, 2026

This audit checks all fourteen imported reads and their derived signals against
FOCAS documentation. Changes are on the unreleased fix branch; 0.3.1 remains the
published version. Native fixture tests exercise the actual worker through its C
ABI. They do not qualify readings against an installed CNC.

## Confirmed corrections

- Emergency status is an enum. Only code 1 asserts E-stop; 2 is RESET and 3 is
  WAIT (FS35i). Unknown codes withhold the boolean and preserve raw diagnostics.
- Alarm status is also an enum. Codes 1 (alarm), 3 (fan alarm) and 8 (PMC alarm)
  assert `alarm_active`. Battery-low and PS/FSSB/insulation/encoder warnings remain
  distinguishable in `alarm_status` and `raw_alarm_code`; they are not collapsed
  into a generic alarm. Unknown codes withhold the boolean.
- Execution 0 is RESET, not READY. Execution 4 is MSTR (tool recovery/JOG MDI),
  not ordinary automatic production. Codes 1/2/3 retain STOPPED/FEED_HOLD/ACTIVE.
- Mode codes now distinguish handle, jog, teaching, incremental feed, reference
  and test from unknown values. MEMORY/REMOTE remain automatic for accounting.
- Invalid feedrate/RPM/load units no longer create unlabeled or mislabeled readings.
- Diagnostic decoding follows signed/unsigned metadata and verifies axis versus
  spindle scope, scalar type, returned diagnosis number and index. Unsupported
  metadata is withheld, not converted into a fabricated measurement.
- Maintenance mappings require identified 0i-D/F or 30i families. Unknown 0i
  model codes are not assumed to have the modern diagnostic attribute layout.
- A full ten-message alarm buffer cannot prove absence of an axis OT condition;
  observed OT remains true, while unobserved conditions are withheld until a
  complete buffer is available.
- Negative program numbers in the current four-digit ABI are rejected.
- Series 15/15i is rejected before status reads because its ODBST layout differs
  from this worker's buffer.

## Read-by-read review

| Read | Mapping and limits | Reference |
| --- | --- | --- |
| `cnc_sysinfo` | i-series flag is bit 1; model code is bits 8–15; M/TT/MT types retain full text. Model qualification and Series 15 guard added. | [System info](https://www.inventcom.net/fanuc-focas-library/misc/cnc_sysinfo) |
| `cnc_statinfo` | Execution, operating mode, emergency and alarm use explicit enumerations; raw codes retained. | [Status](https://www.inventcom.net/fanuc-focas-library/misc/cnc_statinfo), [Kepware status codes](https://support.ptc.com/help/kepware/drivers/en/kepware/drivers/FANUCFOCAS1ETHERNET/status-info-tags.html) |
| `cnc_rdspeed` | Decimal scaling is data / 10^dec. Feed units 0/1/3/4; spindle unit 2. Selected spindle is a fallback. | [Speed](https://www.inventcom.net/fanuc-focas-library/position/cnc_rdspeed) |
| `cnc_acts2` | Specified-spindle reads use data[0]; no inferred main/sub/live-tool role. Current reader supports up to four reported spindles. | [Spindle speed](https://www.inventcom.net/fanuc-focas-library/position/cnc_acts2) |
| `cnc_rdspmeter` | Selector 0 requests spindle load; returned count controls iteration; percentage unit validated. | [Spindle load](https://www.inventcom.net/fanuc-focas-library/position/cnc_rdspmeter) |
| `cnc_rdsvmeter` | Returned axis count controls iteration; unit must be 0 (%). | [Servo load](https://www.inventcom.net/fanuc-focas-library/position/cnc_rdsvmeter) |
| `cnc_rdprgnum` | data is executing program, mdata main program. Binding uses the four-digit interface, not the eight-digit variant. | [Program number](https://www.inventcom.net/fanuc-focas-library/program/cnc_rdprgnum) |
| `cnc_rdprogdir3` | Type 2 includes comment; returned program must match the requested executing program. | [Program directory](https://www.inventcom.net/fanuc-focas-library/program/cnc_rdprogdir3) |
| `cnc_modal` | Type 108 is T; block 0 is active for supported families. This is a T command, not independent installed-tool verification. | [Modal data](https://www.inventcom.net/fanuc-focas-library/misc/cnc_modal) |
| `pmc_rdpmcrng` | Fixed G12 byte read with address/type validation and active-low decoding. G12 is not a universal machine-builder-specific knob address or physical knob verification. | [PMC read](https://www.inventcom.net/fanuc-focas-library/pmc/pmc_rdpmcrng), [FANUC PMC training](https://studylib.net/doc/28418127/fanuc-pmc-maintenance-3xi-amp-0id-v2) |
| `cnc_rdalmmsg2` | Type 4 includes OT/external data; axis-qualified conditions only. Bounded message length; full-buffer absence is not treated as false. | [Alarm messages](https://www.inventcom.net/fanuc-focas-library/misc/cnc_rdalmmsg2) |
| `cnc_rdopmsg` | First message uses selector 0 and length 262; datano -1 means no message; length/type checked. English/ASCII is the current text-decoding scope. | [Operator message](https://www.inventcom.net/fanuc-focas-library/misc/cnc_rdopmsg) |
| `cnc_rddiaginfo` | Check actual diagnosis presence, type, real/bit flags, axis/spindle flags and sign metadata. | [Diagnostic information](https://www.inventcom.net/fanuc-focas-library/misc/cnc_rddiaginfo) |
| `cnc_diagnoss` | Byte temps 308/309/403; signed W power 4901/4902. Header and ranges checked. Negative regenerative power remains valid when signed. | [Diagnostic read](https://www.inventcom.net/fanuc-focas-library/misc/cnc_diagnoss), [FANUC 0i-F Plus maintenance manual](https://studylib.net/doc/27303587/b-64695en-fanuc-0i-model-f-plus-maintenance-manual-compre...), [FANUC 0i-D maintenance manual](https://studylib.net/doc/28333937/b-64305en03--series-0i-model-d--maintenance-manual) |

## Accounting and publication

OEE continues to count confirmed automatic execution with positive actual feed.
RESET/MSTR/manual/MDI/test/unknown states do not qualify. Zero feedrate, RPM, load,
power and genuine zero override remain valid; zero-only temperature suppression
is the user's explicit policy, not a claim that FANUC universally marks 0°C invalid.
MQTT converts actual booleans to ON/OFF and treats loss of availability separately.

No new native reads or writes were introduced. Four session functions and fourteen
read functions remain allowlisted. Default FOCAS path, capped spindle/axis counts,
ASCII text scope and four-digit program interface remain implementation limits.
Physical tool identity, controller-specific temperatures and effective override
still need live comparison. No arbitrary PMC address, native function selector,
write or CNC command is exposed.
