import asyncio
import copy
import time
import uuid
from datetime import datetime, timezone
from .collector import CollectionError


def utc():
    return datetime.now(timezone.utc).isoformat()


class Manager:
    def __init__(self, store, publisher, collector_factory):
        self.store, self.publisher, self.collector_factory = store, publisher, collector_factory
        self.records = {item["id"]: item for item in store.data["machines"]}
        self.status = {}
        self.tasks = {}
        self.lock = asyncio.Lock()

    def empty_status(self):
        return {"online": False, "last_attempt": None, "last_success": None,
                "error": None, "error_code": None, "reconnect_attempts": 0,
                "controller": {}, "signals": {}, "unsupported": {}}

    async def start(self):
        self.publisher.reconcile(set(self.records))
        for identity in self.records:
            self.launch(identity)

    def launch(self, identity):
        self.status[identity] = self.empty_status()
        if self.records[identity]["enabled"]:
            self.tasks[identity] = asyncio.create_task(self.loop(identity))

    async def stop_one(self, identity):
        task = self.tasks.pop(identity, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.publisher.availability(identity, False)

    async def save(self, value, identity=None):
        async with self.lock:
            new = value.model_dump(exclude={"revision"})
            for other_id, record in self.records.items():
                if other_id != identity and (record["host"], record["port"]) == (new["host"], new["port"]):
                    raise ValueError("That machine endpoint is already configured")
            if identity:
                if identity not in self.records:
                    raise KeyError(identity)
                if value.revision != self.records[identity]["revision"]:
                    raise ValueError("Configuration changed; refresh before saving")
            identity = identity or str(uuid.uuid4())
            new.update(id=identity, revision=self.records.get(identity, {}).get("revision", 0) + 1)
            replacement = {**self.records, identity: new}
            self.store.save(list(replacement.values()))
            await self.stop_one(identity)
            self.records = replacement
            self.launch(identity)
            return new

    async def remove(self, identity):
        async with self.lock:
            if identity not in self.records:
                raise KeyError(identity)
            replacement = {k: v for k, v in self.records.items() if k != identity}
            self.store.save(list(replacement.values()))
            await self.stop_one(identity)
            self.records = replacement
            self.status.pop(identity, None)
            self.publisher.remove(identity)

    async def loop(self, identity):
        collector = self.collector_factory()
        record = self.records[identity]
        status = self.status[identity]
        failures = 0
        sent_values = {}
        try:
            while True:
                status["last_attempt"] = utc()
                try:
                    result = await collector.read(record)
                    now = utc()
                    status.update(online=True, last_success=now, error=None, error_code=None,
                                  controller=result["controller"], unsupported=result.get("unsupported", {}))
                    signals = copy.deepcopy(result["signals"])
                    signals["collector_mode"] = {"value": collector.mode, "source": "monitor.mode", "kind": "sensor"}
                    signals["collector_error"] = {"value": "OK", "source": "monitor.error", "kind": "sensor"}
                    self.publisher.discovery(record, signals, result["controller"])
                    for name, signal in signals.items():
                        old = sent_values.get(name)
                        # Refresh before HA expire_after, even if value hasn't changed.
                        if old is None or old[0] != signal or time.monotonic() - old[1] >= max(5, record["interval"] * 2):
                            self.publisher.state(identity, name, signal, now, result.get("simulation", False))
                            sent_values[name] = (copy.deepcopy(signal), time.monotonic())
                        signal["last_read"] = now
                    status["signals"] = signals
                    self.publisher.availability(identity, True)
                    failures = 0
                except (CollectionError, OSError) as error:
                    failures += 1
                    status.update(online=False, error=str(error), error_code=getattr(error, "code", None))
                    status["reconnect_attempts"] += 1
                    self.publisher.availability(identity, False)
                    # Restart worker after failure, avoiding partially invalid native handles.
                    await collector.close()
                await asyncio.sleep(min(60, 2 ** min(failures, 6)) if failures else record["interval"])
        except asyncio.CancelledError:
            raise
        except Exception:
            status.update(online=False, error="Collector failed internally; see service logs")
            import logging
            logging.exception("Collector task failed for %s", identity)
            self.publisher.availability(identity, False)
        finally:
            await collector.close()

    def list(self):
        items = []
        for identity, record in self.records.items():
            item = copy.deepcopy({**record, **self.status.get(identity, self.empty_status())})
            for name, signal in item["signals"].items():
                from .mqtt import key
                signal["published"] = self.publisher.acknowledged(self.publisher.machine_root(identity) + "/signal/" + key(name))
                signal["discovery_published"] = self.publisher.acknowledged(self.publisher.discovery_topic(identity))
            items.append(item)
        return items

    async def close(self):
        for identity in list(self.tasks):
            await self.stop_one(identity)
