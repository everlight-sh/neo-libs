import json,socket,ssl,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from support import ROOT,compile,run
from test_network import request
from test_protocols import event,sse
from tls_certificates import certificates

class AgentPath(unittest.TestCase):
    def test_tls_stream_mcp_continuation_and_durable_state(self):
        binary=compile('tests/agent_path.neo','agent-path')
        with tempfile.TemporaryDirectory(prefix='neo-agent-path-') as tmp:
            root=Path(tmp);certificates(root)
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_3;context.maximum_version=ssl.TLSVersion.TLSv1_3
            context.load_cert_chain(str(root/'leaf.pem'),str(root/'leaf.key'));context.set_alpn_protocols(['http/1.1'])
            listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(10);errors=[];requests=[]
            reasoning={'type':'reasoning','id':'reason-1','encrypted_content':'opaque-state-must-survive','summary':[]}
            call={'type':'function_call','id':'i1','call_id':'c1','name':'add','arguments':'{"a":20,"b":22}','status':'completed'}
            def serve():
                try:
                    for turn in range(2):
                        client,_=listener.accept()
                        with client,context.wrap_socket(client,server_side=True) as c:
                            c.settimeout(8);header,body=request(c);assert header.startswith(b'POST /v1/responses HTTP/1.1');assert b'Authorization: Bearer test-token' in header
                            doc=json.loads(body);requests.append(doc);assert doc['stream'] is True and doc['store'] is False and doc['tools'][0]['name']=='add'
                            if turn==0:
                                assert doc['input']==[{'role':'user','content':'What is 20 + 22?'}]
                                events=[event('response.created',0,response={'id':'r1'}),event('response.output_item.done',1,item=reasoning),event('response.output_item.added',2,output_index=1,item={**call,'arguments':'','status':'in_progress'}),event('response.function_call_arguments.delta',3,output_index=1,item_id='i1',delta='{"a":20,'),event('response.function_call_arguments.delta',4,output_index=1,item_id='i1',delta='"b":22}'),event('response.function_call_arguments.done',5,output_index=1,item_id='i1',arguments=call['arguments']),event('response.output_item.done',6,item=call),event('response.completed',7,response={'id':'r1','status':'completed','output':[reasoning,call]})]
                            else:
                                assert doc['input'][1:3]==[reasoning,call]
                                output=doc['input'][3];assert output['type']=='function_call_output' and output['call_id']=='c1';assert json.loads(output['output'])=={'content':[{'type':'text','text':'42'}],'isError':False}
                                events=[event('response.created',0,response={'id':'r2'}),event('response.output_text.delta',1,delta='The answer is '),event('response.output_text.delta',2,delta='42.'),event('response.completed',3,response={'id':'r2','status':'completed'})]
                            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n')
                            raw=sse(events)
                            for i in range(0,len(raw),13):
                                part=raw[i:i+13];c.sendall(('%x\r\n'%len(part)).encode()+part+b'\r\n')
                            c.sendall(b'0\r\n\r\n')
                except Exception as e:errors.append(e)
            thread=threading.Thread(target=serve,daemon=True);thread.start()
            try:
                output=run(binary,listener.getsockname()[1],root/'ca.der',sys.executable,ROOT/'tests/mcp_peer.py',root/'state.json')
                self.assertEqual(output,b'The answer is 42.\n');saved=json.loads((root/'state.json').read_text());self.assertEqual(saved['tools_executed'],1);self.assertEqual(saved['answer'],'The answer is 42.');self.assertEqual(saved['input'],requests[1]['input'])
            finally:thread.join(12);listener.close()
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
if __name__=='__main__':unittest.main(verbosity=2)
