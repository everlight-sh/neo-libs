#!/usr/bin/env python3
"""ELF audit plus binary-only chroot execution; Linux test tools stay outside."""
import argparse,hashlib,json,os,platform,shutil,subprocess,tempfile
from pathlib import Path
from support import ROOT,BUILD,compile

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert platform.system()=='Linux' and os.geteuid()==0
    compile('tests/standalone.neo','standalone');halfclose=compile('tests/reactor_halfclose.neo','reactor-halfclose')
    names=['agent-path','codecs','providers','mcp','reactor','network','media','stun','udp','srtp','websocket-live','standalone']
    report={'system':platform.uname()._asdict(),'binaries':{},'empty_roots':{}}
    for name in names:
        binary=BUILD/name;assert binary.is_file(),binary
        ph=subprocess.check_output(['readelf','-l',str(binary)],text=True)
        dyn=subprocess.check_output(['readelf','-d',str(binary)],text=True)
        imports=subprocess.check_output(['nm','-u',str(binary)],text=True)
        assert 'INTERP' not in ph and 'NEEDED' not in dyn and not imports.strip(),name
        build=json.loads((BUILD/(name+'.report.json')).read_text());assert build['undefined_symbols']==[]
        report['binaries'][name]={'sha256':digest(binary),'bytes':binary.stat().st_size,'interpreter':False,'shared_libraries':[],'undefined_symbols':[]}
    cases=[('udp',BUILD/'udp',[],b'',b'UDP OK\n'),('websocket-sha1',BUILD/'codecs',['0'],b'dGhlIHNhbXBsZSBub25jZQ==',b's3pPLMBiTxaQ9kYGzzhZRbK+xOo='),('media',BUILD/'media',['0'],b'\xff',b'\0\0'),('crypto',BUILD/'standalone',[],b'',b'crypto OK\n')]
    cases.append(('self-exec-reactor',halfclose,[],b'',b'reactor OK\n'))
    for name,binary,args,data,expected in cases:
        with tempfile.TemporaryDirectory(prefix='neo-empty-root-') as tmp:
            empty=Path(tmp);shutil.copy2(binary,empty/'program');assert list(empty.iterdir())==[empty/'program']
            result=subprocess.run(['chroot',str(empty),'/program',*args],input=data,capture_output=True,timeout=60)
            assert result.returncode==0 and result.stdout==expected,(name,result.returncode,result.stdout,result.stderr)
            report['empty_roots'][name]={'passed':True,'files':['/program'],'stdout_sha256':hashlib.sha256(result.stdout).hexdigest()}
    out=ROOT/'docs/dependency-audit-linux-arm64.json';out.write_text(json.dumps(report,indent=2)+'\n');print('PASS ELF audit:',len(names),'binaries; binary-only chroot:',len(cases),'cases')
if __name__=='__main__':main()
