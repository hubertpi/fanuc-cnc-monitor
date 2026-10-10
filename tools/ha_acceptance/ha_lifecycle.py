import json
import time
from pathlib import Path
import ha_acceptance as a
from ha_test_api import supervisor, ingress_client, ws

state=json.loads(a.STATE.read_text())

def ready():
    try:
        a.client,a.base=ingress_client()
        r=a.api('status')
        return r if r['mqtt_connected'] else False
    except Exception:
        return False

def stable():
    states={s['entity_id']:s['state'] for s in ws('get_states')}
    for ident,snapshot in state['snapshots'].items():
        entities,devices=a.registry(ident)
        if len(devices)!=1: return False
        assert snapshot=={'device_id':devices[0]['id'],'entities':{e['unique_id']:e['entity_id'] for e in entities}}
        if any(states.get(i) in (None,'unknown','unavailable') for i in snapshot['entities'].values()): return False
    return True

def record(message):
    state['checks'].append(message)
    a.STATE.write_text(json.dumps(state,indent=2))
    print(message,flush=True)

if __name__=='__main__':
    for slug in ['local_fanuc_cnc_monitor','core_mosquitto']:
        supervisor('/addons/'+slug+'/restart',method='post')
        a.eventually(ready,60)
        a.eventually(stable,60)
        record(slug+' restart: live states and all device/entity identities preserved')
    # Restart this isolated HA only. Its own HTTP request can disconnect.
    try: supervisor('/core/restart',method='post',timeout=120)
    except Exception: pass
    time.sleep(3)
    a.eventually(ready,120)
    a.eventually(stable,60)
    record('HA Core restart: live states and all device/entity identities preserved')
    first,second=state['machines']
    supervisor('/addons/core_mosquitto/stop',method='post')
    a.eventually(lambda: not a.api('status')['mqtt_connected'])
    a.api('machines/'+first['id'],'delete')
    assert a.api('diagnostics')['pending_mqtt_topics']>0
    # Restart collector with the broker down to exercise the durable queue.
    supervisor('/addons/local_fanuc_cnc_monitor/restart',method='post')
    supervisor('/addons/core_mosquitto/start',method='post')
    a.eventually(ready,60)
    a.eventually(lambda: a.registry(first['id'])==([],[]),60)
    a.eventually(lambda: a.api('diagnostics')['pending_mqtt_topics']==0,60)
    del state['snapshots'][first['id']]
    a.eventually(stable,60)
    record('Broker-outage deletion survives collector restart; HA entities AND device removed, journal drained, second machine live')
    a.api('machines/'+second['id'],'delete')
    a.eventually(lambda: a.registry(second['id'])==([],[]),60)
    a.eventually(lambda: a.api('diagnostics')['pending_mqtt_topics']==0,60)
    record('Connected deletion removes remaining HA entities AND device, journal drained')
