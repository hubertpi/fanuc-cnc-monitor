import asyncio
import json
from app.collector import Simulator
from app.manager import Manager
from app.models import MachineInput
from app.mqtt import Publisher
from app.store import Store


def test_fault_isolation_and_live_changes(tmp_path):
    async def scenario():
        pub = Publisher(tmp_path)
        manager = Manager(Store(tmp_path / "machines.json"), pub, Simulator)
        await manager.start()
        good = await manager.save(MachineInput(host="good.example", name="Good"))
        bad = await manager.save(MachineInput(host="offline.example", name="Offline"))
        await asyncio.sleep(.1)
        good_task = manager.tasks[good["id"]]
        assert manager.status[good["id"]]["online"]
        assert manager.status[bad["id"]]["error_code"] == -16
        assert manager.status[bad["id"]]["reconnect_attempts"] == 1
        await manager.save(MachineInput(host="offline.example", name="Disabled", enabled=False, revision=1), bad["id"])
        assert manager.tasks[good["id"]] is good_task
        assert not good_task.done()
        assert bad["id"] not in manager.tasks
        await manager.remove(bad["id"])
        assert manager.tasks[good["id"]] is good_task
        try:
            await manager.save(MachineInput(host="good.example", name="Duplicate"))
            assert False, "Duplicate endpoint accepted"
        except ValueError:
            pass
        await manager.close()
        assert not manager.tasks
    asyncio.run(scenario())


def test_schema_tombstones_and_restart_reconciliation(tmp_path):
    pub = Publisher(tmp_path)
    machine = {"id": "stable-id", "name": "Lathe", "interval": 1}
    signals = {"rpm": {"value": 12, "source": "cnc_rdspeed", "unit": "rpm"},
               "unknown": {"value": "a", "source": "vendor.raw"}}
    pub.discovery(machine, signals, {})
    pub.state(machine["id"], "rpm", signals["rpm"], "now", False)
    pub.discovery(machine, {"unknown": signals["unknown"]}, {})
    config = json.loads(pub.journal["topics"][pub.discovery_topic(machine["id"])])
    from app.mqtt import key
    assert config["components"][key("rpm")] == {"platform": "sensor"}
    assert "unit_of_measurement" not in config["components"][key("unknown")]
    assert pub.journal["topics"][pub.machine_root(machine["id"]) + "/signal/" + key("rpm")] == ""
    restored = Publisher(tmp_path)
    restored.reconcile(set())
    assert restored.journal["topics"][restored.discovery_topic(machine["id"])] == ""
    assert restored.journal["installation"] == pub.journal["installation"]


def test_structured_alarm_and_long_text_attributes(tmp_path):
    from app.mqtt import key
    pub = Publisher(tmp_path)
    alarms = [{"code": 123, "axis": 1, "type": 0, "message": "Overtravel"},
              {"code": 456, "axis": 2, "type": 1, "message": "Servo alarm"}]
    pub.state("machine", "alarms", {"value": alarms, "source": "cnc_rdalmmsg2"}, "now", False)
    payload = json.loads(pub.journal["topics"][pub.machine_root("machine") + "/signal/" + key("alarms")])
    assert payload["value"] == 2 and payload["details"] == alarms
    full_text = "x" * 600
    pub.state("machine", "message", {"value": full_text, "source": "cnc_rdopmsg"}, "now", False)
    payload = json.loads(pub.journal["topics"][pub.machine_root("machine") + "/signal/" + key("message")])
    assert len(payload["value"]) <= 255 and payload["details"] == full_text
    pub.state("machine", "alarms", {"value": [], "source": "cnc_rdalmmsg2"}, "later", False)
    payload = json.loads(pub.journal["topics"][pub.machine_root("machine") + "/signal/" + key("alarms")])
    assert payload["value"] == 0 and payload["details"] == []
