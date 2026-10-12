"""Exercise EOF cleanup and the hung-worker fallback with real subprocesses."""
import asyncio
import sys

from app.collector import NativeCollector


def test_worker_reused_and_releases_on_eof(tmp_path):
    marker = tmp_path / "closed"
    script = '''import sys, json
from pathlib import Path
for line in sys.stdin:
    print(json.dumps({"controller": {}, "signals": {}}), flush=True)
Path(sys.argv[1]).write_text("released")
'''

    async def check():
        collector = NativeCollector([sys.executable, "-c", script, str(marker)])
        endpoint = {"host": "127.0.0.1", "port": 8193, "timeout": 1}
        await collector.read(endpoint)
        process = collector.process
        await collector.read(endpoint)
        assert collector.process is process
        await collector.close()
        assert marker.read_text() == "released"
        assert process.returncode == 0
        assert collector.process is None
        await collector.close()

    asyncio.run(check())


def test_hung_worker_is_killed():
    async def check():
        collector = NativeCollector()
        collector.process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "import time; time.sleep(60)",
            stdin=asyncio.subprocess.PIPE)
        process = collector.process
        await asyncio.wait_for(collector.close(), 5)
        assert process.returncode is not None and process.returncode != 0
        assert collector.process is None

    asyncio.run(check())
