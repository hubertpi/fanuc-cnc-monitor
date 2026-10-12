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
short pmc_rdpmcrng() { return 6; }
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


def test_native_groups_multi_spindle_and_validated_diagnostics(tmp_path):
    dotnet,compiler=shutil.which('dotnet'),shutil.which('cc')
    worker=Path(__file__).resolve().parents[1]/'fanuc_monitor/worker/bin/Release/net10.0/Monitor.Worker.dll'
    if not dotnet or not compiler or not worker.is_file():
        pytest.skip('Requires built worker and cc')
    source=tmp_path/'fake.c'; trace=tmp_path/'trace'
    source.write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static int messages, overrides;
static void log_event(const char *event) { FILE *f=fopen(getenv("SESSION_TRACE"),"a");fprintf(f,"%s\n",event);fclose(f); }
short cnc_startupprocess(){return 0;}
short cnc_exitprocess(){return 0;}
short cnc_allclibhndl3(const char *host,unsigned short port,int timeout,unsigned short *h){*h=0;log_event("open");return 0;}
short cnc_freelibhndl(){log_event("close");return 0;}
short cnc_sysinfo(unsigned short h,void *p){memset(p,0,18);memcpy((char*)p+4,"0 ",2);*(short*)p=2;memcpy((char*)p+16," 2",2);memcpy((char*)p+6,"MT",2);log_event("identity");return 0;}
short cnc_statinfo(unsigned short h,void *p){memset(p,0,18);return 0;}
short cnc_rdspeed(unsigned short h,short type,void *p){memset(p,0,24);*(int*)((char*)p+12)=1800;*(short*)((char*)p+18)=2;return 0;}
short cnc_acts2(unsigned short h,short spindle,void *p){memset(p,0,20);*(short*)p=spindle;*(int*)((char*)p+4)=spindle==1?0:2400;log_event(spindle==1?"rpm1":"rpm2");return 0;}
short cnc_rdspmeter(unsigned short h,short type,short *n,void *p){*n=2;memset(p,0,96);return 0;}
short cnc_rdsvmeter(unsigned short h,short *n,void *p){*n=2;memset(p,0,96);((char*)p)[8]='X';((char*)p)[20]='Z';return 0;}
short cnc_rdprgnum(unsigned short h,void *p){log_event("program");memset(p,0,8);((short*)p)[2]=53;((short*)p)[3]=1234;return 0;}
short cnc_rdprogdir3(){return 6;}
short cnc_modal(unsigned short h,short number,short block,void *p){memset(p,0,12);*(int*)((char*)p+4)=303;return 0;}
short pmc_rdpmcrng(unsigned short h,short area,short type,unsigned short start,unsigned short end,unsigned short length,void *p){if(area!=0||type!=0||start!=12||end!=12||length!=9)return 5;memset(p,0,14);((short*)p)[2]=start;((short*)p)[3]=end;unsigned char raw[]={155,255,105,55,0,135}; int i=overrides++; ((unsigned char*)p)[8]=raw[i%6]; if(i==6)((short*)p)[2]=13; return 0;}
short cnc_rdalmmsg2(unsigned short h,short type,short *n,void *p){*n=2;memset(p,0,760);((short*)p)[2]=4;((short*)p)[3]=1;((short*)p)[5]=2;memcpy((char*)p+12,"OT",2);((short*)((char*)p+76))[2]=6;((short*)((char*)p+76))[3]=2;return 0;}
short cnc_rdopmsg(unsigned short h,short type,short length,void *p){memset(p,'X',262);((short*)p)[0]=messages++ ? -1 : 2000;((short*)p)[1]=0;((short*)p)[2]=3;memcpy((char*)p+6,"OK!junk",7);return 0;}
short cnc_rddiaginfo(unsigned short h,short number,unsigned short n,void *p){memset(p,0,46);((short*)p)[0]=1;((short*)p)[3]=number==309?310:number;((short*)p)[4]=(number==308||number==403)?5:135;return 0;}
short cnc_diagnoss(unsigned short h,short number,short axis,short length,void *p){memset(p,0,8);*(short*)p=number;((short*)p)[1]=axis;*(int*)((char*)p+4)=number==308?0:number==403?55:-500;return 0;}
''')
    library=tmp_path/'fake.so'
    subprocess.run([compiler,'-shared','-fPIC',str(source),'-o',str(library)],check=True)
    endpoint={'host':'192.0.2.1','port':8193,'timeout':3}
    requests=[{**endpoint,'groups':['fast','status','slow']},{**endpoint,'groups':['fast']}]+[{**endpoint,'groups':['status']} for _ in range(6)]
    result=subprocess.run([dotnet,str(worker)],input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=15,env={**os.environ,'FOCAS_LIBRARY_PATH':str(library),'SESSION_TRACE':str(trace)})
    assert result.returncode==0,result.stderr
    responses=[json.loads(line) for line in result.stdout.splitlines()]
    assert all('signals' in r for r in responses),responses
    first,fast,status=[r['signals'] for r in responses[:3]]
    assert first['axis_1_overtravel']['value'] is True
    assert first['axis_2_overtravel']['value'] is False
    assert first['feed_override']['value']==100
    assert first['tool_code']['value']=='T0303'
    assert first['program_number']['value']=='O0053'
    assert first['main_program_number']['value']=='O1234'
    assert first['spindle_rpm']['value']==1800
    assert 'spindle_rpm' not in fast
    assert fast['feed_rate']['value']==0
    assert first['machine_message']['value']=='OK!'
    assert status['machine_message']['value']==''
    assert fast['spindle_1_rpm']['value']==0 and fast['spindle_2_rpm']['value']==2400
    assert first['axis_1_motor_temperature']['value'] is None and first['axis_1_motor_temperature']['available'] is False
    assert [r['signals'].get('feed_override',{}).get('value') for r in responses[2:]]==[0,150,200,None,120,None]
    assert 'pmc_rdpmcrng.G12' in responses[5]['unsupported']
    assert 'pmc_rdpmcrng.G12' in responses[7]['unsupported']
    assert responses[0]['controller']['type']=='MT'
    assert first['axis_1_power']['value']==-500
    assert first['spindle_2_motor_temperature']['value']==55
    assert not any('encoder_temperature' in name for name in first)
    assert all(signal['group']=='fast' for signal in fast.values())
    events=trace.read_text().splitlines()
    assert events.count('open')==events.count('close')==events.count('identity')==events.count('program')==1
