import json,os,platform,shlex,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# NEO is the compiler: the NEO variable, else `neo` on PATH.
NEO=os.environ.get('NEO') or shutil.which('neo')
if not NEO:raise SystemExit('neo-libs tests need the Neo compiler: put neo on PATH or set NEO')
BUILD=ROOT/'build'/(os.environ.get('NEO_TARGET') or platform.system().lower()+'-'+platform.machine());BUILD.mkdir(parents=True,exist_ok=True)
RUNNER=shlex.split(os.environ.get('NEO_RUNNER',''))
def compile(source,name):
    binary=BUILD/name
    p=subprocess.run([NEO,'build',str(ROOT/source),'-o',str(binary),'--report'],cwd=ROOT,capture_output=True,text=True)
    try:r=json.loads(p.stdout)
    except ValueError:raise AssertionError(p.stdout[-2000:]+p.stderr)
    (BUILD/(name+'.report.json')).write_text(json.dumps(r,indent=2)+'\n')
    assert p.returncode==0,(r.get('errors'),[x for x in r.get('obligations',[]) if x['status'] not in ('proven','checked')],p.stderr[-2000:])
    assert r['undefined_symbols']==[]
    return binary

def run(binary,*args,data=None,timeout=15):
    p=subprocess.run(RUNNER+[str(binary),*map(str,args)],input=data,capture_output=True,timeout=timeout)
    assert p.returncode==0,(binary,args,p.returncode,p.stdout[-2000:],p.stderr[-2000:])
    return p.stdout
