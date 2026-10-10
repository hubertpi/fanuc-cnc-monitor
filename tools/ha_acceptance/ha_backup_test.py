import json
import ha_acceptance as a
from ha_test_api import supervisor
from ha_lifecycle import ready

machine=a.create('192.0.2.30','SIM Restore Test')
ident=machine['id']
a.eventually(lambda: len(a.registry(ident)[0])==17)
before=a.registry(ident)
backup=supervisor('/backups/new/partial',method='post',data={'name':'Fanuc isolated acceptance','addons':['local_fanuc_cnc_monitor'],'homeassistant':False},timeout=180)
print('Created isolated add-on backup',backup,flush=True)
payload={k:machine[k] for k in ['host','port','timeout','name','interval','enabled','revision']}
a.api('machines/'+ident,'put',{**payload,'name':'Changed after backup','enabled':False})
result=supervisor('/backups/'+backup['slug']+'/restore/partial',method='post',data={'addons':['local_fanuc_cnc_monitor'],'homeassistant':False},timeout=180)
print('Restore completed',result,flush=True)
a.eventually(ready,90)
restored=a.api('status')['machines']
assert len(restored)==1 and restored[0]['id']==ident and restored[0]['name']==machine['name'] and restored[0]['enabled']
a.eventually(lambda: a.registry(ident)[1][0]['name']==machine['name'])
after=a.registry(ident)
assert {(e['unique_id'],e['entity_id']) for e in before[0]}=={(e['unique_id'],e['entity_id']) for e in after[0]}
assert before[1][0]['id']==after[1][0]['id']
state=json.loads(a.STATE.read_text())
state['checks'].append('Supervisor partial backup/restore recovers original machine settings and preserves HA device/entity identities')
state['backup_slug']=backup['slug']
a.STATE.write_text(json.dumps(state,indent=2))
print(state['checks'][-1],flush=True)
supervisor('/addons/local_fanuc_cnc_monitor/rebuild',method='post',timeout=300)
a.eventually(ready,90)
rebuilt=a.api('status')['machines']
assert len(rebuilt)==1 and rebuilt[0]['id']==ident and rebuilt[0]['name']==machine['name'] and rebuilt[0]['enabled']
after=a.registry(ident)
assert {(e['unique_id'],e['entity_id']) for e in before[0]}=={(e['unique_id'],e['entity_id']) for e in after[0]}
assert before[1][0]['id']==after[1][0]['id']
ids={e['entity_id'] for e in after[0]}
def live():
    states={s['entity_id']:s['state'] for s in a.ws('get_states')}
    return all(states.get(i) not in (None,'unknown','unavailable') for i in ids)
a.eventually(live,60)
state['checks'].append('Supervisor same-version image rebuild preserves settings and live HA device/entity identities; version migration not tested')
a.STATE.write_text(json.dumps(state,indent=2))
print(state['checks'][-1],flush=True)
