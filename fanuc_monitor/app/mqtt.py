"""Durable retained-topic journal, QoS 1 delivery and HA device discovery."""
import hashlib
import json
import queue
import ssl
import uuid
from pathlib import Path
import paho.mqtt.client as mqtt
from .store import atomic_json


def key(identity):
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


class Publisher:
    def __init__(self, directory: Path, broker=None, client=None):
        self.path = directory / "mqtt-journal.json"
        self.journal = json.loads(self.path.read_text()) if self.path.exists() else {
            "version": 1, "installation": str(uuid.uuid4()), "topics": {}}
        if self.journal.get("version") != 1:
            raise ValueError("Unsupported MQTT journal version")
        self.root = "fanuc_monitor/" + self.journal["installation"]
        self.online_topic = self.root + "/availability"
        self.connected = False
        self.dirty = set(self.journal["topics"])
        self.inflight = {}
        self.events = queue.SimpleQueue()
        self.broker = broker or {}
        self.error = None
        self.client = client or mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                           client_id="fanuc-" + self.journal["installation"])
        self.client.will_set(self.online_topic, "offline", qos=1, retain=True)
        self.client.on_connect = self._connect
        self.client.on_disconnect = lambda *args: self.events.put("disconnect")
        self.client.on_message = lambda c, u, msg: self.events.put("birth") if msg.topic == "homeassistant/status" and msg.payload == b"online" else None
        self.client.reconnect_delay_set(1, 60)
        self.client.max_inflight_messages_set(20)
        self.client.max_queued_messages_set(500)
        self.put(self.online_topic, "offline")

    def _connect(self, client, userdata, flags, reason, properties):
        if reason == 0:
            client.subscribe("homeassistant/status", qos=1)  # Only HA birth, no commands.
            self.events.put("connect")
        else:
            self.events.put("connect_error")

    def start(self):
        if not self.broker.get("host"):
            self.error = "MQTT service unavailable; configure an explicit test or HA broker"
            return
        if self.broker.get("username"):
            self.client.username_pw_set(self.broker["username"], self.broker.get("password", ""))
        if self.broker.get("tls"):
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.connect_async(self.broker["host"], self.broker.get("port", 1883), keepalive=20)
        self.client.loop_start()

    def put(self, topic, payload):
        value = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if self.journal["topics"].get(topic) != value:
            self.journal["topics"][topic] = value
            self.dirty.add(topic)
            atomic_json(self.path, self.journal)

    def forget(self, topic):
        # Tombstones persist across broker outages and service restarts.
        self.put(topic, "")

    def pump(self):
        while not self.events.empty():
            event = self.events.get()
            if event in ("connect", "birth"):
                self.connected = True
                self.error = None
                self.inflight.clear()
                self.dirty.update(self.journal["topics"])
                self.put(self.online_topic, "online")
            else:
                self.connected = False
                self.error = "MQTT disconnected" if event == "disconnect" else "MQTT authentication/connection rejected"
                self.inflight.clear()
                self.dirty.update(self.journal["topics"])
        for topic, (info, sent) in list(self.inflight.items()):
            if info.is_published():
                del self.inflight[topic]
                if self.journal["topics"].get(topic) == sent:
                    self.dirty.discard(topic)
        if self.connected:
            for topic in list(self.dirty):
                if topic not in self.inflight and len(self.inflight) < 20:
                    payload = self.journal["topics"][topic]
                    info = self.client.publish(topic, payload, qos=1, retain=True)
                    if info.rc == mqtt.MQTT_ERR_SUCCESS:
                        self.inflight[topic] = (info, payload)

    def acknowledged(self, topic):
        return self.connected and topic not in self.dirty and topic not in self.inflight

    def machine_root(self, identity):
        return self.root + "/machine/" + identity

    def discovery_topic(self, identity):
        return "homeassistant/device/fanuc_" + self.journal["installation"] + "/" + identity + "/config"

    def availability(self, identity, online):
        self.put(self.machine_root(identity) + "/availability", "online" if online else "offline")

    def discovery(self, machine, signals, controller):
        identity = machine["id"]
        root = self.machine_root(identity)
        components = {}
        for name, signal in signals.items():
            slug = key(name)
            component = {
                "platform": signal.get("kind", "sensor"),
                "unique_id": identity + "_" + slug,
                "name": name.replace("_", " ").title(),
                "state_topic": root + "/signal/" + slug,
                "value_template": "{{ value_json.value }}",
                "json_attributes_topic": root + "/signal/" + slug,
                "json_attributes_template": "{{ {'source': value_json.source, 'last_read': value_json.last_read, 'simulation': value_json.simulation, 'details': value_json.details | default(none)} | tojson }}",
                "availability": [{"topic": self.online_topic}, {"topic": root + "/availability"}],
                "availability_mode": "all",
                "expire_after": max(15, machine["interval"] * 3),
            }
            if component["platform"] == "binary_sensor":
                component.update(payload_on="ON", payload_off="OFF")
            if signal.get("unit"):
                component["unit_of_measurement"] = signal["unit"]
            if isinstance(signal["value"], (int, float)) and not isinstance(signal["value"], bool) and signal.get("unit"):
                component["state_class"] = "measurement"
            if name.startswith("raw_") or name in ("collector_error", "collector_mode"):
                component["entity_category"] = "diagnostic"
            components[slug] = component
        # HA requires a platform-only config to remove a component; omission
        # alone is insufficient. Keep tombstones in retained discovery until
        # the signal is collected again, so HA restart also sees the deletion.
        previous = self.journal["topics"].get(self.discovery_topic(identity), "")
        if previous:
            for slug, component in json.loads(previous).get("components", {}).items():
                if slug not in components:
                    components[slug] = {"platform": component["platform"]}
        self.put(self.discovery_topic(identity), {
            "device": {"identifiers": [identity], "name": machine["name"],
                       "manufacturer": "FANUC", "model": controller.get("model", "Fanuc CNC")},
            "origin": {"name": "Fanuc CNC Monitor", "sw_version": "0.1.1-dev"},
            "components": components,
        })
        expected = {root + "/signal/" + key(name) for name in signals}
        for topic in list(self.journal["topics"]):
            if topic.startswith(root + "/signal/") and topic not in expected:
                self.forget(topic)

    def state(self, identity, name, signal, read_at, simulation):
        value = signal["value"]
        details = None
        if signal.get("kind") == "binary_sensor":
            value = "ON" if value else "OFF"
        elif isinstance(value, (list, dict)):
            details = value
            value = len(value)
        elif isinstance(value, str) and len(value) > 255:
            details = value
            value = value[:252] + "…"
        self.put(self.machine_root(identity) + "/signal/" + key(name), {
            "value": value, "source": signal["source"], "last_read": read_at,
            "simulation": simulation, "details": details})

    def remove(self, identity):
        prefix = self.machine_root(identity) + "/"
        for topic in list(self.journal["topics"]):
            if topic.startswith(prefix) or topic == self.discovery_topic(identity):
                self.forget(topic)

    def reconcile(self, identities):
        # Recover deletion if a crash occurred after saving config but before MQTT cleanup.
        prefix = self.root + "/machine/"
        disco = "homeassistant/device/fanuc_" + self.journal["installation"] + "/"
        for topic in list(self.journal["topics"]):
            if topic.startswith(prefix) and topic[len(prefix):].split("/")[0] not in identities:
                self.forget(topic)
            if topic.startswith(disco) and topic[len(disco):].split("/")[0] not in identities:
                self.forget(topic)
        for identity in identities:
            self.availability(identity, False)
            # Avoid restoring stale values before a fresh successful read.
            for topic in list(self.journal["topics"]):
                if topic.startswith(self.machine_root(identity) + "/signal/"):
                    self.forget(topic)

    def close(self):
        self.put(self.online_topic, "offline")
        if self.connected:
            info = self.client.publish(self.online_topic, "offline", qos=1, retain=True)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                try:
                    info.wait_for_publish(timeout=2)
                except RuntimeError:
                    pass  # Journal and LWT cover a connection lost during shutdown.
        self.client.disconnect()
        self.client.loop_stop()
