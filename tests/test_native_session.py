"""Run the real worker against a fake library; no CNC/network calls occur."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_native_session_reuse_failure_reconnect_and_eof(tmp_path):
    dotnet, compiler = shutil.which("dotnet"), shutil.which("cc")
    worker = Path(__file__).resolve().parents[1] / "fanuc_monitor/worker/bin/Release/net10.0/Monitor.Worker.dll"
    if not dotnet or not compiler or not worker.is_file():
        pytest.skip("Requires cc and the built Release worker (provided by CI)")
    trace = tmp_path / "trace"
    source = tmp_path / "fake.c"
    source.write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static int reads;
static void log_event(const char *event) {
    FILE *f = fopen(getenv("SESSION_TRACE"), "a");
    fprintf(f, "%s\n", event); fclose(f);
}
short cnc_startupprocess(long level, const char *filename) { log_event("startup"); return 0; }
short cnc_exitprocess(void) { log_event("exit"); return 0; }
short cnc_allclibhndl3(const char *host, unsigned short port, int timeout, unsigned short *handle) {
    *handle = 0; log_event("open"); return 0;
}
short cnc_freelibhndl(unsigned short handle) { log_event("close"); return 0; }
short cnc_sysinfo(unsigned short handle, void *data) { memset(data, 0, 18); return 0; }
short cnc_statinfo(unsigned short handle, void *data) {
    log_event("read"); memset(data, 0, 18); return ++reads == 3 ? -16 : 0;
}
// Optional groups report unsupported, which must preserve the connection.
short cnc_rdspeed() { return 6; }
short cnc_rdspmeter() { return 6; }
short cnc_rdsvmeter() { return 6; }
short cnc_rdprgnum() { return 6; }
short cnc_rdprogdir3() { return 6; }
short cnc_modal() { return 6; }
short cnc_rdopnlsgnl() { return 6; }
short cnc_rdalmmsg2() { return 6; }
short cnc_rdopmsg() { return 6; }
''')
    library = tmp_path / "fake.so"
    subprocess.run([compiler, "-shared", "-fPIC", str(source), "-o", str(library)], check=True)
    first = {"host": "192.0.2.1", "port": 8193, "timeout": 3}
    second = {**first, "host": "192.0.2.2"}
    requests = [first, first, first, first, second]
    result = subprocess.run(
        [dotnet, str(worker)], input="".join(json.dumps(r) + "\n" for r in requests),
        text=True, capture_output=True, timeout=15,
        env={**os.environ, "FOCAS_LIBRARY_PATH": str(library), "SESSION_TRACE": str(trace)})
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(responses) == 5
    assert all("signals" in responses[i] for i in (0, 1, 3, 4))
    assert responses[2]["code"] == -16
    assert trace.read_text().splitlines() == [
        "startup", "open", "read", "read", "read", "close",
        "open", "read", "close", "open", "read", "close", "exit"]
