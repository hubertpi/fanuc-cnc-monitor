import json
import os
from urllib.parse import urlsplit
from pathlib import Path
import httpx
from websockets.sync.client import connect

# Deliberately restricted to the dedicated loopback test deployment.
if os.environ.get('FANUC_HA_TEST_CONFIRM') != 'isolated-simulation':
    raise RuntimeError('Set FANUC_HA_TEST_CONFIRM=isolated-simulation for this destructive test suite')
BASE = os.environ.get('FANUC_HA_TEST_URL', 'http://127.0.0.1:7123').rstrip('/')
url = urlsplit(BASE)
if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost') or url.port != 7123 or url.path or url.username:
    raise RuntimeError('Acceptance tools only target the isolated loopback port 7123')
DATA = {'access_token': os.environ['FANUC_HA_TEST_TOKEN']}

def client():
    return httpx.Client(base_url=BASE, trust_env=False, timeout=90,
        headers={'Authorization': 'Bearer ' + DATA['access_token']})

def ws(command, **kwargs):
    with connect(BASE.replace('http:', 'ws:') + '/api/websocket', proxy=None, open_timeout=10) as sock:
        json.loads(sock.recv())
        sock.send(json.dumps({'type': 'auth', 'access_token': DATA['access_token']}))
        assert json.loads(sock.recv())['type'] == 'auth_ok'
        sock.send(json.dumps({'id': 1, 'type': command, **kwargs}))
        while True:
            data = json.loads(sock.recv())
            if data.get('id') == 1:
                if not data.get('success'):
                    raise RuntimeError(data.get('error'))
                return data['result']

def supervisor(endpoint, method='get', data=None, timeout=90):
    return ws('supervisor/api', endpoint=endpoint, method=method, data=data or {}, timeout=timeout)

def ingress_client():
    addon = supervisor('/addons/local_fanuc_cnc_monitor/info')
    session = supervisor('/ingress/session', method='post')
    c = client()
    c.cookies.set('ingress_session', session['session'])
    return c, addon['ingress_url']

