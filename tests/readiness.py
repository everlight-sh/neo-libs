#!/usr/bin/env python3
"""A scope gate, not a substitute for running the implementation tests."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from support import NEO

def verify(root):
    p=subprocess.run([NEO,'pkg','verify'],cwd=root,capture_output=True,text=True)
    assert p.returncode==0,(p.stdout[-2000:],p.stderr[-2000:])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--require',choices=['documented','full'],default='documented');args=ap.parse_args()
    matrix=json.loads((ROOT/'docs/readiness.json').read_text());verify(ROOT)
    for capability in matrix['capabilities']:
        # std:… entries name Neo standard-library modules, which ship with the compiler.
        for path in capability['sources']+capability['tests']:assert path.startswith('std:') or (ROOT/path).is_file(),path
    gaps=[c for c in matrix['capabilities'] if c['status'] in ('missing','partial')]
    print('Full scope:', 'READY' if matrix['full_scope_ready'] and not gaps else 'INCOMPLETE', '('+matrix['full_scope']+')')
    for item in gaps:print(item['id']+': '+item['profile'])
    if args.require=='full' and (gaps or not matrix['full_scope_ready']):return 2
    return 0
if __name__=='__main__':raise SystemExit(main())
