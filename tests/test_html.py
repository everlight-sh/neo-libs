import json,os,time,unittest
from pathlib import Path
from support import compile,run

# html5lib-tests tokenizer suite (https://github.com/html5lib/html5lib-tests),
# used as an independent oracle. Set HTML5LIB_TESTS to a checkout to run it.
SUITE=os.environ.get('HTML5LIB_TESTS')
KINDS={1:'Character',2:'StartTag',3:'EndTag',4:'Comment',5:'DOCTYPE',7:'ProcessingInstruction'}

def tokens(binary,data):
    out=[]
    for line in run(binary,data=data).split(b'\n'):
        if not line:continue
        f=line.split(b'\t');attrs=[tuple(bytes.fromhex(x.decode()) for x in a.split(b'=')) for a in f[4:]]
        out.append((int(f[0]),bytes.fromhex(f[1].decode()),bytes.fromhex(f[2].decode()),f[3]==b'1',attrs))
    return out

def text(b):return b.decode('utf-8','surrogateescape')

def as_html5lib(toks):
    out=[]
    for kind,name,data,closing,attrs in toks:
        if kind==1:
            if not data:continue
            if out and out[-1][0]=='Character':out[-1][1]+=text(data)
            else:out.append(['Character',text(data)])
        elif kind==2:out.append(['StartTag',text(name),{text(k):text(v) for k,v in attrs}]+([True] if closing else []))
        elif kind==3:out.append(['EndTag',text(name)])
        elif kind==4:out.append(['Comment',text(data)])
        elif kind==7:out.append(['ProcessingInstruction',text(name),text(data)])
        elif kind==5:
            ids={text(k):text(v) for k,v in attrs}
            out.append(['DOCTYPE',text(name) or None,ids.get('public'),ids.get('system'),not closing])
    return out

def expected(output):
    out=[]
    for t in output:
        if t=='ParseError':continue
        t=list(t)
        if t[0]=='Character' and out and out[-1][0]=='Character':out[-1][1]+=t[1];continue
        if t[0]=='StartTag' and len(t)==4 and not t[3]:t=t[:3]
        out.append(t)
    return out

def unescape(s):return s.encode('utf-8').decode('unicode-escape')

def conformance(binary,suite):
    """Runs every Data-state test; other initial states are counted, not run."""
    files={};failures=[];skipped={'other state':0,'lone surrogate':0}
    for path in sorted(Path(suite,'tokenizer').glob('*.test')):
        cases=json.loads(path.read_text(encoding='utf-8')).get('tests',[]);passed=total=0
        for case in cases:
            if 'Data state' not in case.get('initialStates',['Data state']):skipped['other state']+=1;continue
            source,output=case['input'],case['output']
            if case.get('doubleEscaped'):source,output=unescape(source),json.loads(unescape(json.dumps(output)))
            try:raw=source.encode('utf-8')
            except UnicodeEncodeError:skipped['lone surrogate']+=1;continue
            total+=1;got=as_html5lib(tokens(binary,raw));want=expected(output)
            if got==want:passed+=1
            else:failures.append((path.name,case['description'],source,want,got))
        files[path.name]=(passed,total)
    return files,failures,skipped

class HTMLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.binary=compile('tests/html.neo','html')
    def html(self,source):return as_html5lib(tokens(self.binary,source.encode()))
    def test_named_references_use_the_whatwg_table(self):
        self.assertEqual(self.html('&notin; &notit; &amp &CounterClockwiseContourIntegral; &NotEqualTilde; &foo;'),
            [['Character','∉ ¬it; & ∳ ≂̸ &foo;']])
    def test_numeric_references_and_windows_1252(self):
        self.assertEqual(self.html('&#x80;&#0;&#65&#x1F600;&#xD800;&#;'),[['Character','€�A\U0001f600�&#;']])
    def test_legacy_names_in_attributes(self):
        self.assertEqual(self.html('<a href="?x=1&copy=2&amp;y" title=&lt;b>'),
            [['StartTag','a',{'href':'?x=1&copy=2&y','title':'<b'}]])
    def test_raw_text_and_rcdata(self):
        self.assertEqual(self.html('<script>a<b && "</p>"</script><title>&amp;<i></title>'),
            [['StartTag','script',{}],['Character','a<b && "</p>"'],['EndTag','script'],
             ['StartTag','title',{}],['Character','&<i>'],['EndTag','title']])
    def test_markup_tokens(self):
        self.assertEqual(self.html('<!DOCTYPE html><!-- c --><br/><A HREF=x b b=2>t</A>'),
            [['DOCTYPE','html',None,None,True],['Comment',' c '],['StartTag','br',{},True],
             ['StartTag','a',{'href':'x','b':''}],['Character','t'],['EndTag','a']])
    def test_linear_time(self):
        def elapsed(count):
            data=b'<p class="x">word &amp; word</p>\n'*count;start=time.perf_counter();run(self.binary,data=data,timeout=60)
            return time.perf_counter()-start
        small,large=elapsed(20000),elapsed(80000)
        self.assertLess(large,small*6,(small,large))
    @unittest.skipUnless(SUITE,'set HTML5LIB_TESTS to an html5lib-tests checkout')
    def test_html5lib_tokenizer_suite(self):
        files,failures,skipped=conformance(self.binary,SUITE)
        passed=sum(p for p,_ in files.values());total=sum(t for _,t in files.values())
        for name,(p,t) in files.items():print(f'{name:32} {p:5}/{t:<5}')
        print(f'data state {passed}/{total} ({100*passed/max(total,1):.1f}%), not run: {skipped}')
        report=os.environ.get('HTML5LIB_REPORT')
        if report:Path(report).write_text(json.dumps({'files':files,'skipped':skipped,'failures':failures[:3000]},indent=1,ensure_ascii=False))
        self.assertGreater(passed,0)

if __name__=='__main__':unittest.main(verbosity=2)
