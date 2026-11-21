import base64,hashlib,json,random,struct,sys,unittest
from pathlib import Path
from support import ROOT,compile,run

def frame(payload,opcode=1,fin=True,masked=True,key=b'\x37\xfa\x21\x3d'):
    n=len(payload);prefix=bytes([(128 if fin else 0)|opcode,(128 if masked else 0)|(n if n<126 else 126 if n<65536 else 127)])
    prefix+=(b'' if n<126 else struct.pack('!H',n) if n<65536 else struct.pack('!Q',n))
    return prefix+(key if masked else b'')+bytes(c^(key[i%4] if masked else 0) for i,c in enumerate(payload))
def sse(events):return b''.join(('data: '+json.dumps(e,ensure_ascii=False,separators=(',',':'))+'\n\n').encode() for e in events)
def event(kind,seq,**kw):return dict(type=kind,sequence_number=seq,**kw)

class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codecs=compile('tests/codecs.neo','codecs');cls.provider=compile('tests/providers.neo','providers')
        cls.mcp=compile('tests/mcp.neo','mcp');cls.reactor=compile('tests/reactor.neo','reactor')
    def codec(self,mode,data):return run(self.codecs,mode,data=data)
    def test_sha1_handshake_vectors(self):
        rng=random.Random(71)
        for n in [0,1,3,55,56,63,64,65,127,128,1000]:
            raw=rng.randbytes(n);self.assertEqual(self.codec(1,raw),hashlib.sha1(raw).digest())
        self.assertEqual(self.codec(0,b'dGhlIHNhbXBsZSBub25jZQ=='),b's3pPLMBiTxaQ9kYGzzhZRbK+xOo=')
        self.assertEqual(self.codec(0,b'bad'),b'error')
    def test_masked_encoder_matches_independent_oracle(self):
        for n in [0,1,5,125,126,127,1000]:
            raw=b'x'*n;self.assertEqual(self.codec(2,raw),frame(raw))
    def test_fragmented_utf8_and_interleaved_ping(self):
        text='héllo 😀';raw=text.encode();wire=frame(raw[:3],fin=False)+frame(b'ping',9)+frame(raw[3:],0)
        expected=('9:'+json.dumps('ping')+'\n1:'+json.dumps(text,ensure_ascii=False)+'\n').encode()
        self.assertEqual(self.codec(3,wire),expected)
        self.assertEqual(self.codec(4,frame(b'hello',masked=False)),b'1:"hello"\n')
    def test_websocket_malformed_frames(self):
        bad=[frame(b'plain',masked=False),b'\xc1\x80xxxx',b'\x83\x80xxxx',frame(b'x',0),frame(b'x',9,False),frame(b'x'*126,9),frame(b'\xff'),frame(b'x',8),frame(struct.pack('!H',1005),8),frame(b'a',fin=False)+frame(b'b'),b'\x81\xfe\x00\x01xxxx'+b'!']
        for wire in bad:
            with self.subTest(wire=wire[:16]):self.assertEqual(self.codec(3,wire),b'error')
    def test_upgrade_validation(self):
        wire=b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: keep-alive, Upgrade\r\nSec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n\r\n'
        self.assertEqual(self.codec(7,wire),b'valid')
        for raw in [wire.replace(b'101',b'200'),wire.replace(b'Upgrade: websocket',b'Upgrade: invalid'),wire.replace(b's3pPL',b'x3pPL'),wire.replace(b'\r\n\r\n',b'\r\nSec-WebSocket-Extensions: permessage-deflate\r\n\r\n')]:self.assertEqual(self.codec(7,raw),b'invalid')
    def test_rpc_types_and_errors(self):
        cases=[({'jsonrpc':'2.0','id':7,'method':'tools/call','params':{}},b'1 7 "tools/call"'),({'jsonrpc':'2.0','method':'notify'},b'2 null "notify"'),({'jsonrpc':'2.0','id':'id','result':None},b'3 "id" ""'),({'jsonrpc':'2.0','id':1,'error':{'code':-32601,'message':'unknown'}},b'4 1 ""')]
        for obj,expected in cases:self.assertEqual(self.codec(5,json.dumps(obj).encode()),expected)
        bad=[b'[]',b'{}',b'{"jsonrpc":"2.0","id":1,"id":2,"result":null}',b'{"jsonrpc":"2.0","id":1,"result":null,"error":{}}',b'{"jsonrpc":"2.0","method":"x","params":42}',b'{"jsonrpc":"2.0","id":null,"method":"x"}']
        for raw in bad:self.assertEqual(self.codec(5,raw),b'error')
    def test_sse_multiline_encoding(self):
        self.assertEqual(self.codec(6,b'first\r\nsecond\rthird\n'),b'event: message\nid: 42\ndata: first\ndata: second\ndata: third\ndata: \n\n')
    def test_reactor_and_subprocess_halfclose(self):
        self.assertEqual(run(self.reactor,sys.executable,ROOT/'tests/process_peer.py'),b'reactor/process OK\n')
    def test_actual_mcp_stdio_and_stderr_backpressure(self):
        raw=run(self.mcp,sys.executable,ROOT/'tests/mcp_peer.py')
        result,line=raw.splitlines();self.assertEqual(json.loads(result),{'content':[{'type':'text','text':'42'}],'isError':False});self.assertEqual(line,b'MCP OK')
    def test_responses_fragments_and_opaque_reasoning(self):
        reasoning={'type':'reasoning','id':'reason-1','encrypted_content':'opaque','summary':[]}
        events=[event('response.created',0,response={'id':'r1'}),event('response.output_item.done',1,item=reasoning),event('response.output_item.added',2,output_index=1,item={'type':'function_call','id':'i1','call_id':'c1','name':'add','arguments':''}),event('response.function_call_arguments.delta',3,output_index=1,item_id='i1',delta='{"a":20,'),event('response.function_call_arguments.delta',4,output_index=1,item_id='i1',delta='"b":22}'),event('response.function_call_arguments.done',5,output_index=1,item_id='i1',arguments='{"a":20,"b":22}'),event('response.output_item.done',6,item={'type':'function_call','id':'i1','call_id':'c1','name':'add','arguments':'{"a":20,"b":22}'}),event('response.completed',7,response={'id':'r1','status':'completed','usage':{'input_tokens':10,'output_tokens':5}})]
        out=run(self.provider,data=sse(events)).decode();self.assertNotIn('error:',out);self.assertEqual(out.count('tool_ready '),1)
        items=json.loads(out.split('items ',1)[1]);self.assertEqual(items[0],reasoning);self.assertEqual(items[1]['call_id'],'c1')
    def test_no_execution_for_incomplete_provider_response(self):
        for end in [event('response.incomplete',1,response={'id':'r1'}),event('response.completed',1,response={'id':'wrong','status':'completed'}),event('response.output_text.delta',0,delta='bad')]:
            out=run(self.provider,data=sse([event('response.created',0,response={'id':'r1'}),end]));self.assertIn(b'error:',out);self.assertNotIn(b'tool_ready ',out)
    def test_provider_text(self):
        out=run(self.provider,data=sse([event('response.created',0,response={'id':'r1'}),event('response.output_text.delta',1,delta='hello 😀'),event('response.completed',2,response={'id':'r1','status':'completed'})]));self.assertIn('text "hello 😀"'.encode(),out)
if __name__=='__main__':unittest.main(verbosity=2)
