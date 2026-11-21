import json,os,subprocess,unittest
try:
    import bs4,soupsieve
except ImportError:
    bs4=None
from pathlib import Path
from support import compile,run,RUNNER

# The html5lib tree-construction tests, now maintained in web-platform-tests
# (html/syntax/parsing/resources/*.dat), used as an independent oracle. Set
# TREE_CONSTRUCTION_TESTS to that directory to run them.
SUITE=os.environ.get('TREE_CONSTRUCTION_TESTS')
HEADINGS={'#data','#errors','#new-errors','#document-fragment','#script-on','#script-off','#document'}

def cases(path):
    """Yields dicts of heading -> list of lines, one per test in a .dat file."""
    lines=path.read_bytes().decode('utf-8').split('\n');case=None;key=None  # keep literal CRs
    for i,line in enumerate(lines):
        if line=='#data' and (case is None or (i>0 and lines[i-1]=='')):
            if case is not None:yield case
            case={'#data':[]};key='#data';continue
        if case is not None and line in HEADINGS:key=line;case[key]=[];continue
        if case is not None:case[key].append(line)
    if case is not None:yield case

def tree(binary,data,scripting,context=None):
    args=[str(binary),'1' if scripting else '0']+([context] if context else [])
    p=subprocess.run(RUNNER+args,input=data,capture_output=True,timeout=30)
    if p.returncode!=0:return None,p.returncode
    return p.stdout.decode('utf-8','surrogateescape'),0

def conformance(binary,suite):
    files={};failures=[];crashes=0
    for path in sorted(Path(suite).glob('*.dat')):
        passed=total=0
        for case in cases(path):
            data='\n'.join(case['#data']).encode('utf-8','surrogatepass')
            document=case.get('#document',[])
            while document and document[-1]=='':document.pop()
            want='\n'.join(document)+'\n' if document else ''
            context=case['#document-fragment'][0].strip() if case.get('#document-fragment') else None
            got,code=tree(binary,data,'#script-on' in case,context)
            total+=1
            if code:crashes+=1
            if got==want:passed+=1
            else:failures.append({'file':path.name,'data':data.decode('utf-8','replace'),'context':context,'want':want,'got':got,'exit':code})
        files[path.name]=(passed,total)
    return files,failures,crashes

# Selector conformance: every selector's matches, as tree-order element
# positions, against soupsieve on the same document parsed by html5lib.
DOCUMENT='''<!DOCTYPE html><html lang="en"><head><title>T</title></head><body class="home page">
<header id="top"><nav><ul class="menu"><li class="item active"><a href="/">Home</a></li><li class="item"><a href="/docs" rel="nofollow help">Docs</a></li><li class="item last"><a>Plain</a></li></ul></nav></header>
<main><article data-kind="post" lang="en-US"><h1>Title</h1><p>One <em>two</em> three</p><p class="lead"></p><p><!-- c --></p>
<section><h2 id="a1">A</h2><div><span>x</span><span>y</span><b>z</b><span>w</span></div></section></article>
<form id="f"><input type="text" name="q" required placeholder="Search"><input type="CHECKBOX" name="c" checked><input type="radio" disabled>
<select name="s"><option value="1">1</option><option value="2" selected>2</option></select><textarea readonly></textarea>
<fieldset disabled><button>Go</button></fieldset></form>
<table><tbody><tr><td>1</td><td>2</td><td>3</td></tr><tr><td>4</td><td>5</td><td>6</td></tr></tbody></table>
<svg viewBox="0 0 1 1"><foreignObject><p>in svg</p></foreignObject><circle r="1"/></svg></main>
<footer><p>end</p></footer></body></html>'''
SELECTORS=['*','p','P','#top','.item','.item.active','li.item:not(.active)','ul > li','nav a','header a[href]','a[href="/docs"]',
    'a[rel~=help]','a[href^="/d"]','a[href$="cs"]','a[href*="oc"]','[lang|=en]','[data-kind=POST i]','[data-kind=POST]','input[type=checkbox]',
    'li:first-child','li:last-child','span:nth-child(2)','span:nth-child(odd)','span:nth-child(2n+1)','span:nth-last-child(1)','span:nth-of-type(2)',
    'span:nth-last-of-type(1)','span:first-of-type','b:only-of-type','div > :nth-child(-n+2)','td:nth-child(3n)','tr:nth-child(even) td','p:empty',
    ':root','html:root','h1 + p','h1 ~ p','p + section','section h2','article > p','main p','header ~ main','li:is(.active,.last) a','li:where(.last)',
    'p:not(:empty)',':not(p, span, li, a, td)','input:checked','option:checked','input:disabled','button:disabled','input:enabled','input:required',
    'input:optional','textarea:read-only','input:read-write','input:placeholder-shown','a:link','a:any-link','svg','circle','svg p','[viewBox]',
    'span:nth-child(2 of span)','td:nth-last-child(2)','body > *','li > a:only-child','p:nth-of-type(2)','.lead','.menu .item:last-child a',
    'h2#a1','#a1','#nope','div span + span','div span ~ b','#f input:not([type=radio])','[name]','[name=q][required]','p:first-child',
    'p:last-of-type','ul,ol , h1','a:not([href])','td:nth-child(n+2):nth-child(-n+2)','*:empty']

class DOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.binary=compile('tests/dom.neo','dom')
    def dump(self,source,*args):return run(self.binary,'0',*args,data=source.encode()).decode()
    def test_implied_structure(self):
        self.assertEqual(self.dump('<p>One<p>Two'),'| <html>\n|   <head>\n|   <body>\n|     <p>\n|       "One"\n|     <p>\n|       "Two"\n')
    def test_adoption_agency(self):
        self.assertEqual(self.dump('<b>1<p>2</b>3</p>'),
            '| <html>\n|   <head>\n|   <body>\n|     <b>\n|       "1"\n|     <p>\n|       <b>\n|         "2"\n|       "3"\n')
    def test_foster_parenting(self):
        self.assertEqual(self.dump('<table>x<tr><td>y</table>'),
            '| <html>\n|   <head>\n|   <body>\n|     "x"\n|     <table>\n|       <tbody>\n|         <tr>\n|           <td>\n|             "y"\n')
    def test_foreign_content(self):
        self.assertEqual(self.dump('<svg viewbox="0 0 1 1"><foreignobject><p>x</svg>'),
            '| <html>\n|   <head>\n|   <body>\n|     <svg svg>\n|       viewBox="0 0 1 1"\n|       <svg foreignObject>\n|         <p>\n|           "x"\n')
    def test_fragment(self):self.assertEqual(self.dump('<td>a<td>b','tr'),'| <td>\n|   "a"\n| <td>\n|   "b"\n')
    @unittest.skipUnless(bs4,'needs beautifulsoup4, soupsieve and html5lib as an oracle')
    def test_selectors_against_soupsieve(self):
        binary=compile('tests/select.neo','select')
        soup=bs4.BeautifulSoup(DOCUMENT,'html5lib');elements=list(soup.find_all(True));position={id(e):i for i,e in enumerate(elements)}
        mismatches=[]
        for selector in SELECTORS:
            want=sorted(position[id(e)] for e in soup.select(selector))
            got=run(binary,selector,data=DOCUMENT.encode()).decode()
            got=sorted(int(x) for x in got.split()) if not got.startswith('error') else got.strip()
            if got!=want:mismatches.append((selector,want,got))
        self.assertEqual(mismatches,[])
        self.assertTrue(run(binary,'p::before',data=b'').startswith(b'error'));self.assertTrue(run(binary,'a[',data=b'').startswith(b'error'))
    @unittest.skipUnless(SUITE,'set TREE_CONSTRUCTION_TESTS to wpt/html/syntax/parsing/resources')
    def test_html5lib_tree_construction(self):
        files,failures,crashes=conformance(self.binary,SUITE)
        passed=sum(p for p,_ in files.values());total=sum(t for _,t in files.values())
        for name,(p,t) in files.items():print(f'{name:36} {p:5}/{t:<5}')
        print(f'tree construction {passed}/{total} ({100*passed/max(total,1):.1f}%), crashes: {crashes}')
        report=os.environ.get('TREE_CONSTRUCTION_REPORT')
        if report:Path(report).write_text(json.dumps({'files':files,'crashes':crashes,'failures':failures},indent=1,ensure_ascii=False))
        self.assertEqual(crashes,0)

if __name__=='__main__':unittest.main(verbosity=2)
