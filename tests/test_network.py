import contextlib,json,os,selectors,socket,ssl,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from support import ROOT,BUILD,RUNNER,compile,run
from tls_certificates import certificates

@contextlib.contextmanager
def peer(handler,context=None):
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(8);errors=[];stop=threading.Event()
    def serve():
        try:
            connection,_=listener.accept()
            with connection:
                connection.settimeout(8)
                if context:
                    with context.wrap_socket(connection,server_side=True) as secure:handler(secure,stop)
                else:handler(connection,stop)
        except Exception as e:errors.append(e)
    thread=threading.Thread(target=serve,daemon=True);thread.start()
    try:yield listener.getsockname()[1]
    finally:
        stop.set();thread.join(10);listener.close();assert not thread.is_alive();assert not errors,errors

def request(connection):
    raw=b''
    while b'\r\n\r\n' not in raw:raw+=connection.recv(16384)
    header,body=raw.split(b'\r\n\r\n',1)
    length=next((int(line.split(b':',1)[1]) for line in header.split(b'\r\n')[1:] if line.lower().startswith(b'content-length:')),0)
    while len(body)<length:body+=connection.recv(16384)
    assert len(body)==length
    return header,body

class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=compile('tests/network.neo','network');cls.tmp=tempfile.TemporaryDirectory(prefix='neo-libs-certs-');cls.certs=Path(cls.tmp.name);certificates(cls.certs)
        cls.context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);cls.context.minimum_version=ssl.TLSVersion.TLSv1_3;cls.context.maximum_version=ssl.TLSVersion.TLSv1_3
        cls.context.load_cert_chain(str(cls.certs/'leaf.pem'),str(cls.certs/'leaf.key'));cls.context.set_alpn_protocols(['http/1.1'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_connection_reuse_same_tcp_socket(self):
        def handler(c,stop):
            for path,body,connection in [(b'/first',b'first',b'keep-alive'),(b'/second',b'second',b'close')]:
                header,_=request(c);assert header.startswith(b'GET '+path+b' HTTP/1.1');assert b'Connection: keep-alive' in header
                c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: '+connection+b'\r\n\r\n'+body)
        with peer(handler) as port:self.assertEqual(run(self.binary,port,0),b'firstsecond')
    def test_server_flushes_before_response_finishes(self):
        with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
        p=subprocess.Popen(RUNNER+[str(self.binary),str(port),'1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            selector=selectors.DefaultSelector();selector.register(p.stdout,selectors.EVENT_READ);self.assertTrue(selector.select(5));self.assertEqual(p.stdout.readline(),b'listening\n');selector.close()
            with socket.create_connection(('127.0.0.1',port),timeout=3) as c:
                c.sendall(b'GET /events HTTP/1.1\r\nHost: localhost\r\n\r\n');t=time.monotonic();raw=b''
                while b'data: first\n\n' not in raw:raw+=c.recv(16384)
                self.assertLess(time.monotonic()-t,.25);self.assertNotIn(b'0\r\n\r\n',raw)
                while True:
                    part=c.recv(16384)
                    if not part:break
                    raw+=part
                self.assertTrue(raw.endswith(b'0\r\n\r\n'));self.assertGreaterEqual(time.monotonic()-t,.25)
            self.assertEqual(p.wait(timeout=5),0,p.stderr.read())
        finally:
            if p.poll() is None:p.kill();p.wait()
            p.stdout.close();p.stderr.close()
    def test_cancel_stalled_tls_handshake(self):
        def handler(c,stop):c.recv(16384);stop.wait(2)
        with peer(handler) as port:
            t=time.monotonic();self.assertEqual(run(self.binary,port,2,self.certs/'ca.der'),b'error:125');self.assertLess(time.monotonic()-t,1.5)
    def test_cancel_stalled_authenticated_tls_read(self):
        def handler(c,stop):stop.wait(2)
        with peer(handler,self.context) as port:
            t=time.monotonic();self.assertEqual(run(self.binary,port,4,self.certs/'ca.der'),b'error:125');self.assertLess(time.monotonic()-t,2)
    def test_cancel_stalled_dns(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.bind(('127.0.0.1',0));t=time.monotonic();self.assertEqual(run(self.binary,s.getsockname()[1],3),b'error:125');self.assertLess(time.monotonic()-t,1.5)
if __name__=='__main__':unittest.main(verbosity=2)
