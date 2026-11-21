"""Compile and run a locked consumer after deleting its original dependencies."""
import json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from support import ROOT,NEO,RUNNER,BUILD

def neo(*args,cwd):
    p=subprocess.run([NEO,*args],cwd=cwd,capture_output=True,text=True)
    assert p.returncode==0,(args,p.stdout[-2000:],p.stderr[-2000:])
    return p.stdout

class PackagingTests(unittest.TestCase):
    def test_vendored_consumer_survives_deleted_source_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='neo-libs-offline-') as tmp:
            root=Path(tmp);source_root=root/'sources';source_root.mkdir()
            aliases=['jsonrpc','mcp','websocket','providers','http-client','http-server','audio','rtp','opus-packet','stun','srtp']
            for alias in aliases:
                shutil.copytree(ROOT/alias,source_root/alias,ignore=shutil.ignore_patterns('.neo-build','build','__pycache__'))
            (root/'neo.toml').write_text('[package]\nname="offline-consumer"\nversion="0.1.0"\nentry="src/main.neo"\n[dependencies]\n'+''.join(f'{a}={{path="sources/{a}",version="0.1.0"}}\n' for a in aliases))
            (root/'src').mkdir()
            source=(ROOT/'tests/codecs.neo').read_text()
            for alias in ['websocket','jsonrpc','http-server']:source=source.replace(f'../{alias}/src/lib.neo',f'pkg:{alias}')
            entry=root/'src/main.neo';entry.write_text(source)
            neo('pkg','lock',cwd=root);lock=json.loads((root/'neo.lock').read_text());self.assertEqual(len(lock['packages']),12)
            neo('pkg','vendor',cwd=root);shutil.rmtree(source_root);neo('pkg','verify',cwd=root)
            self.assertFalse(source_root.exists())
            binary=root/'consumer'
            p=subprocess.run([NEO,'build',str(entry),'-o',str(binary),'--report'],cwd=root,capture_output=True,text=True)
            report=json.loads(p.stdout);self.assertEqual(p.returncode,0,(report.get('errors'),p.stderr));self.assertEqual(report['undefined_symbols'],[])
            p=subprocess.run(RUNNER+[str(binary),'0'],input=b'dGhlIHNhbXBsZSBub25jZQ==',capture_output=True,timeout=15)
            self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout,b's3pPLMBiTxaQ9kYGzzhZRbK+xOo=')
            result={'ok':True,'packages':12,'original_source_dependencies_deleted':True,'runtime_imports':[],'target':report.get('target'),'vendored_packages':sorted(v['name'] for k,v in lock['packages'].items() if k!=lock['root'])}
            (BUILD/'offline-packaging.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':unittest.main(verbosity=2)
