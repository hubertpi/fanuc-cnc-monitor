"""One collector instance per machine; native calls run in a bounded subprocess."""
import asyncio
import json
import os
import time
from pathlib import Path


class CollectionError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class Simulator:
    mode = "simulation"

    async def read(self, endpoint):
        # No network operations. Explicit names exercise outages in development.
        await asyncio.sleep(0.01)
        if endpoint["host"].startswith("offline"):
            raise CollectionError("Simulated FOCAS socket failure", -16)
        tick = int(time.monotonic())
        def signal(value, source, kind="sensor", unit=None):
            return {"value": value, "source": source, "kind": kind, "unit": unit}
        return {"controller": {"series": "0i", "version": "SIM", "type": "T", "axes": 2,
                               "model": "Simulated Fanuc 0i-T", "simulation": True},
                "signals": {
                    "execution": signal("ACTIVE" if tick % 20 < 15 else "READY", "cnc_statinfo.run"),
                    "mode": signal("AUTOMATIC", "cnc_statinfo.aut"),
                    "spindle_rpm": signal(1200 + tick % 40, "cnc_rdspeed.acts", unit="rpm"),
                    "spindle_load": signal(36, "cnc_rdspmeter.load", unit="%"),
                    "axis_X_load": signal(12, "cnc_rdsvmeter.X", unit="%"),
                    "axis_Z_load": signal(8, "cnc_rdsvmeter.Z", unit="%"),
                    "feed_rate": signal(4.5, "cnc_rdspeed.actf", unit="in/min"),
                    "feed_override": signal(100, "simulation.feed_override", unit="%"),
                    "program_number": signal(1234, "cnc_rdprgnum"),
                    "program_comment": signal("SIMULATED BRACKET", "cnc_rdprogdir3.comment"),
                    "tool_number": signal(3, "cnc_toolnum"),
                    "emergency_stop": signal(False, "cnc_statinfo.emergency", "binary_sensor"),
                    "alarm_active": signal(False, "cnc_statinfo.alarm", "binary_sensor"),
                    "alarms": signal([], "cnc_rdalmmsg2"),
                    "machine_message": signal("Simulation; no CNC connected", "cnc_rdopmsg")},
                "unsupported": {}, "simulation": True}

    async def close(self):
        pass


class NativeCollector:
    mode = "focas"

    def __init__(self, command=None, library=None):
        self.command = command or ["dotnet", "/opt/worker/Monitor.Worker.dll"]
        self.library = library
        self.process = None

    async def read(self, endpoint):
        if self.process is None or self.process.returncode is not None:
            self.process = await asyncio.create_subprocess_exec(
                *self.command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=1024 * 1024,
                env={**os.environ, **({"FOCAS_LIBRARY_PATH": str(self.library)} if self.library else {})})
        import socket
        try:
            addresses = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(
                endpoint["host"], endpoint["port"], family=socket.AF_INET, type=socket.SOCK_STREAM), endpoint["timeout"])
        except (OSError, asyncio.TimeoutError) as error:
            raise CollectionError("Machine DNS/IPv4 address cannot be resolved") from error
        request = {k: endpoint[k] for k in ("host", "port", "timeout")}
        request["host"] = addresses[0][4][0]
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        await self.process.stdin.drain()
        try:
            raw = await asyncio.wait_for(self.process.stdout.readline(), endpoint["timeout"] * 24 + 5)
            if not raw:
                raise CollectionError("Native worker exited; check library and architecture")
            data = json.loads(raw)
            if "error" in data:
                raise CollectionError(data["error"], data.get("code"))
            if "controller" not in data or "signals" not in data:
                raise CollectionError("Invalid native worker response")
            return data
        except (asyncio.TimeoutError, ValueError) as error:
            await self.close()
            raise CollectionError("Native read timed out or returned invalid data") from error

    async def close(self):
        if self.process and self.process.returncode is None:
            # EOF lets the worker release its persistent FOCAS handle on its
            # owning thread. Hung native calls still have a bounded shutdown.
            if self.process.stdin:
                self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except asyncio.TimeoutError:
                if self.process.returncode is None:
                    self.process.kill()
            await self.process.wait()
        self.process = None


def native_ready(options):
    if not options.get("hardware_testing_enabled", False):
        raise CollectionError("Hardware testing is disabled. Enable it only for an explicitly authorized hardware step")
    import hashlib
    digest = options.get("native_library_sha256", "")
    if digest:
        library = Path("/share/fanuc/libfwlib32-linux-x64.so.1.0.5")
    else:
        native = Path(__file__).resolve().parents[1] / "native"
        try:
            manifest = json.loads((native / "provenance.json").read_text())
            library = native / manifest["filename"]
            digest = manifest["sha256"]
        except (OSError, ValueError, KeyError) as error:
            raise CollectionError("Bundled FOCAS library manifest missing or invalid") from error
    if not library.is_file() or len(digest) != 64:
        raise CollectionError("FOCAS library missing or override SHA-256 invalid")
    if hashlib.sha256(library.read_bytes()).hexdigest() != digest.lower():
        raise CollectionError("FOCAS library SHA-256 does not match")
    import struct
    header = library.read_bytes()[:64]
    if len(header) < 64 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != 62:
        raise CollectionError("Native library must be a little-endian Linux amd64 ELF shared object")
    return library


def factory(options):
    if options.get("mode", "simulation") == "simulation":
        return Simulator
    library = native_ready(options)
    return lambda: NativeCollector(library=library)
