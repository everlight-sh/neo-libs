import base64,hashlib,socket,ssl,struct,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from support import ROOT,BUILD,compile,run
from test_network import peer,request
from tls_certificates import certificates

def frame(op,payload=b'',fin=True):
    assert len(payload)<126
    return bytes([(128 if fin else 0)|op,len(payload)])+payload

def exact(c,n):
    out=b''
    while len(out)<n:
        part=c.recv(n-len(out))
        assert part,'early EOF'
        out+=part
    return out

def client_frame(c):
    a,b=exact(c,2);assert b&128
    size=b&127
    if size==126:size=int.from_bytes(exact(c,2),'big')
    elif size==127:size=int.from_bytes(exact(c,8),'big')
    key=exact(c,4);payload=exact(c,size)
    return a&15,bytes(x^key[i%4] for i,x in enumerate(payload))

def upgrade(c,bad=False,tail=b''):
    header,_=request(c);assert header.startswith(b'GET /events HTTP/1.1')
    key=next(line.split(b':',1)[1].strip() for line in header.split(b'\r\n') if line.lower().startswith(b'sec-websocket-key:'))
    assert len(base64.b64decode(key,validate=True))==16
    accept=base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
    if bad:accept=b'wrong'
    c.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n'+tail)

class WebSocketLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=compile('tests/websocket_live.neo','websocket-live');cls.tmp=tempfile.TemporaryDirectory(prefix='neo-wss-');cls.certs=Path(cls.tmp.name);certificates(cls.certs)
        cls.context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);cls.context.minimum_version=ssl.TLSVersion.TLSv1_3;cls.context.maximum_version=ssl.TLSVersion.TLSv1_3
        cls.context.load_cert_chain(str(cls.certs/'ec-leaf.pem'),str(cls.certs/'ec-leaf.key'));cls.context.set_alpn_protocols(['http/1.1'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def exercise(self,secure):
        def handler(c,stop):
            upgrade(c,tail=frame(1,b'wel',False));assert client_frame(c)==(1,b'hello')
            wire=frame(9,b'heartbeat')+frame(0,b'come')
            for b in wire:c.sendall(bytes([b]))
            assert client_frame(c)==(10,b'heartbeat')
            c.sendall(frame(1,b'again')+frame(8,b'\x03\xe8done'))
            assert client_frame(c)==(8,b'\x03\xe8done')
        with peer(handler,self.context if secure else None) as port:
            self.assertEqual(run(self.binary,port,'tls' if secure else 'plain',self.certs/'ec-ca.der',0),b'text:welcome\ntext:again\n')
    def test_plain_fragmentation_ping_pong_close_and_masking(self):self.exercise(False)
    def test_tls_ecdsa_fragmentation_ping_pong_close(self):self.exercise(True)
    def test_bad_upgrade_rejected(self):
        def handler(c,stop):upgrade(c,bad=True)
        with peer(handler) as port:self.assertEqual(run(self.binary,port,'plain','unused',0),b'error:71')
    def test_eof_without_close_rejected(self):
        def handler(c,stop):upgrade(c);assert client_frame(c)==(1,b'hello');c.sendall(frame(1,b'incomplete',False))
        with peer(handler) as port:self.assertEqual(run(self.binary,port,'plain','unused',0),b'error:1006')
    def test_masked_server_frame_rejected(self):
        def handler(c,stop):upgrade(c);assert client_frame(c)==(1,b'hello');c.sendall(b'\x81\x80'+bytes(4))
        with peer(handler) as port:self.assertEqual(run(self.binary,port,'plain','unused',0),b'error:71')
    def test_stalled_peer_deadline(self):
        def handler(c,stop):upgrade(c);assert client_frame(c)==(1,b'hello');stop.wait(2)
        with peer(handler) as port:
            start=time.monotonic();self.assertEqual(run(self.binary,port,'plain','unused',2),b'error:110');self.assertLess(time.monotonic()-start,1)
if __name__=='__main__':unittest.main(verbosity=2)
