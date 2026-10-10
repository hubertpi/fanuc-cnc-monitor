import json
import time
from pathlib import Path
from ha_test_api import ingress_client, ws, supervisor

STATE = Path(__file__).with_name('ha-acceptance-state.json')
client, base = ingress_client()

def api(path, method='get', data=None, token=None):
    response = client.get(base+'api/status')
    response.raise_for_status()
    status = response.json()
    headers = {'x-monitor-csrf': status['csrf']}
    if token:
        headers['x-connection-test'] = token
    r = client.request(method, base+'api/'+path, headers=headers, json=data)
    r.raise_for_status()
    return r.json()

def eventually(check, seconds=30):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=check()
        if value:
            return value
        time.sleep(.5)
    raise AssertionError('Acceptance condition timed out')

def registry(machine_id):
    entities=[e for e in ws('config/entity_registry/list') if e.get('platform')=='mqtt'
              and e.get('unique_id','').startswith(machine_id+'_')]
    devices=[d for d in ws('config/device_registry/list') if ['mqtt',machine_id] in d.get('identifiers',[])]
    return entities,devices

def create(host,name):
    endpoint={'host':host,'port':8193,'timeout':3}
    tested=api('test','post',endpoint)
    assert tested['simulation']
    return api('machines','post',{**endpoint,'name':name,'interval':1,'enabled':True},tested['test_token'])

if __name__=='__main__':
    status=api('status')
    assert status['mode']=='simulation' and not status['hardware_testing_enabled']
    assert status['mqtt_connected'] and not status['machines'], 'Expected fresh isolated test configuration'
    machines=[create('192.0.2.20','SIM Lathe A'),create('192.0.2.21','SIM Lathe B')]
    STATE.write_text(json.dumps({'machines':machines,'checks':[]},indent=2))
    report=[]
    snapshots={}
    for machine in machines:
        ident=machine['id']
        eventually(lambda: len(registry(ident)[0])>=17)
        entities,devices=registry(ident)
        assert len(devices)==1, (len(devices),ident)
        assert {e['entity_id'].split('.')[0] for e in entities}=={'sensor','binary_sensor'}
        assert len({e['unique_id'] for e in entities})==len(entities)
        snapshots[ident]={'device_id':devices[0]['id'],'entities':{e['unique_id']:e['entity_id'] for e in entities}}
        ids=set(snapshots[ident]['entities'].values())
        def live():
            values=[s for s in ws('get_states') if s['entity_id'] in ids]
            return values if len(values)==len(ids) and all(s['state'] not in ('unknown','unavailable') for s in values) else False
        states=eventually(live)
        assert len(states)==len(entities)
        assert all(s['attributes'].get('simulation') is True for s in states)
        print(machine['name'],len(devices),'HA device,',len(entities),'live read-only entities')
    report.append('Actual HA device discovery: two CNCs, one device each, 17 entities each, all simulated and live')
    # Rename and readdress without changing device, unique IDs or entity IDs.
    first=machines[0]
    endpoint={'host':'192.0.2.22','port':8193,'timeout':3}
    tested=api('test','post',endpoint)
    changed=api('machines/'+first['id'],'put',{**endpoint,'name':'SIM Lathe A renamed','interval':1,'enabled':True,'revision':first['revision']},tested['test_token'])
    eventually(lambda: registry(first['id'])[1][0]['name']=='SIM Lathe A renamed')
    entities,devices=registry(first['id'])
    assert snapshots[first['id']]=={'device_id':devices[0]['id'],'entities':{e['unique_id']:e['entity_id'] for e in entities}}
    machines[0]=changed
    report.append('Rename and readdress preserve actual HA device ID, unique IDs and entity IDs')
    # Disable one only, then recover.
    payload={k:changed[k] for k in ['host','port','timeout','name','interval','enabled','revision']}
    disabled=api('machines/'+first['id'],'put',{**payload,'enabled':False})
    first_ids=set(snapshots[first['id']]['entities'].values())
    second_ids=set(snapshots[machines[1]['id']]['entities'].values())
    def isolated():
        states={s['entity_id']:s['state'] for s in ws('get_states')}
        return all(states.get(i)=='unavailable' for i in first_ids) and all(states.get(i) not in (None,'unknown','unavailable') for i in second_ids)
    eventually(isolated)
    machines[0]=api('machines/'+first['id'],'put',{**payload,'enabled':True,'revision':disabled['revision']})
    eventually(lambda: all(s['state']!='unavailable' for s in ws('get_states') if s['entity_id'] in first_ids))
    report.append('Disable/re-enable gives independent HA availability with second machine still live')
    STATE.write_text(json.dumps({'machines':machines,'snapshots':snapshots,'checks':report},indent=2))
    print('\n'.join(report))
