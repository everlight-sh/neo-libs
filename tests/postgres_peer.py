"""Independent wire peer: SCRAM proof, parameter separation, framing and recovery."""
import base64,hashlib,hmac,json,socket,struct,subprocess,threading
from pathlib import Path
from support import NEO
ROOT=Path(__file__).resolve().parents[1]
def exact(connection,size):
    result=b''
    while len(result)<size:
        piece=connection.recv(size-len(result))
        if not piece:raise EOFError()
        result+=piece
    return result

def message(connection):
    kind=exact(connection,1);size=struct.unpack('>I',exact(connection,4))[0]
    assert 4<=size<=16*1024*1024
    return kind,exact(connection,size-4)
def frame(kind,body):return kind+struct.pack('>I',len(body)+4)+body
def mac(key,message):return hmac.new(key,message,hashlib.sha256).digest()
def peer(connection,invalid):
    size=struct.unpack('>I',exact(connection,4))[0];startup=exact(connection,size-4)
    assert startup.startswith(struct.pack('>I',196608)) and b'user\0test\0database\0test\0' in startup
    connection.sendall(frame(b'R',struct.pack('>I',10)+b'SCRAM-SHA-256\0\0'))
    kind,initial=message(connection);assert kind==b'p'
    mechanism,initial=initial.split(b'\0',1);length=struct.unpack('>I',initial[:4])[0];first=initial[4:]
    assert mechanism==b'SCRAM-SHA-256' and length==len(first) and first.startswith(b'n,,n=test,r=')
    bare=first[3:];nonce=bare.split(b'r=',1)[1];salt=b'0123456789abcdef'
    challenge=b'r='+nonce+b'server,s='+base64.b64encode(salt)+b',i=4096'
    connection.sendall(frame(b'R',struct.pack('>I',11)+challenge))
    kind,final=message(connection);assert kind==b'p'
    without,proof=final.rsplit(b',p=',1)
    auth=bare+b','+challenge+b','+without
    salted=hashlib.pbkdf2_hmac('sha256',b'pencil',salt,4096)
    client_key=mac(salted,b'Client Key');signature=mac(hashlib.sha256(client_key).digest(),auth)
    assert base64.b64decode(proof)==bytes(a^b for a,b in zip(client_key,signature))
    server=mac(mac(salted,b'Server Key'),auth)
    connection.sendall(frame(b'R',struct.pack('>I',12)+b'v='+base64.b64encode(b'bad' if invalid else server)))
    if invalid:
        assert connection.recv(1)==b'';return
    connection.sendall(frame(b'R',struct.pack('>I',0))+frame(b'S',b'client_encoding\0UTF8\0')+frame(b'Z',b'I'))
    for round_ in range(3):
        messages=[message(connection) for _ in range(5)]
        assert [kind for kind,_ in messages]==[b'P',b'B',b'D',b'E',b'S']
        parse=messages[0][1];bind=messages[1][1]
        if round_==0:
            assert b'$1' in parse and b'DROP' not in parse and b"DROP TABLE users" in bind
            assert struct.unpack('>h',bind[4:6])[0]==2 and bind.endswith(b'\xff\xff\xff\xff\0\0')
            columns=[b'value',b'absent'];values=["x'); DROP TABLE users; -- café".encode(),None]
        elif round_==1:
            assert b'select 1/0' in parse
            connection.sendall(frame(b'1',b'')+frame(b'2',b'')+frame(b'E',b'SERROR\0C22012\0Mdivision by zero\0\0')+frame(b'Z',b'I'));continue
        else:columns=[b'value'];values=[b'42']
        descriptor=struct.pack('>h',len(columns))+b''.join(name+b'\0'+struct.pack('>IhIhih',0,0,25,-1,-1,0) for name in columns)
        row=struct.pack('>h',len(values))+b''.join(struct.pack('>i',-1) if value is None else struct.pack('>I',len(value))+value for value in values)
        wire=frame(b'1',b'')+frame(b'2',b'')+frame(b'T',descriptor)+frame(b'D',row)+frame(b'C',b'SELECT 1\0')+frame(b'Z',b'I')
        for at in range(0,len(wire),7):connection.sendall(wire[at:at+7])

def main():
    binary=Path('/private/tmp/neokit-postgres-peer')
    compiled=subprocess.run([NEO,'build',str(ROOT/'tests/postgres_live.neo'),'-o',str(binary)],capture_output=True,text=True)
    if compiled.returncode:
        try:
            report=json.loads(compiled.stdout);print(report.get('errors'));print([o for o in report.get('obligations',[]) if o['status'] not in ('checked','proven')])
        except ValueError:print(compiled.stdout[-3000:],compiled.stderr)
        raise SystemExit(1)
    for invalid in (False,True):
        errors=[]
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen();port=listener.getsockname()[1]
            def server():
                try:
                    connection,_=listener.accept()
                    with connection:
                        connection.settimeout(10);peer(connection,invalid)
                except Exception as error:errors.append(error)
            thread=threading.Thread(target=server);thread.start()
            result=subprocess.run([str(binary),str(port),str(int(invalid))],capture_output=True,text=True,timeout=15)
            thread.join(12)
            assert result.returncode==0,(result.stdout,result.stderr,errors)
            assert not thread.is_alive() and not errors,errors
            if not invalid:
                rows=[json.loads(line) for line in result.stdout.splitlines()]
                assert rows==[[{'value':"x'); DROP TABLE users; -- café",'absent':None}],[{'value':'42'}]],rows
            else:assert 'Rejected invalid server proof' in result.stdout
    print('PASS native PostgreSQL SCRAM-SHA-256, independent server proof, parameterized queries, Unicode/NULL results, fragmented messages, SQL-error recovery and connection reuse')
if __name__=='__main__':main()
