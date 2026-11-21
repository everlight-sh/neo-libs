import base64,ctypes,ctypes.util,json,os,random,struct,unittest
from support import ROOT,compile,run

class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=compile('tests/media.neo','media');fixtures=ROOT/'tests/fixtures'
        # Checked-in expected values: G.711 tables and RTP reorder results recorded
        # from a Go reference implementation that is not part of this repository.
        cls.go=json.loads((fixtures/'go-media-oracle.json').read_text());cls.traces=json.loads((fixtures/'media-traces.json').read_text())
    def media(self,mode,raw):
        try:return run(self.binary,mode,data=raw)
        except AssertionError as error:raise AssertionError(('input',mode,raw[:512].hex(),str(error))) from error
    def test_g711_decoders_against_go_reference(self):
        raw=bytes(range(256))
        for mode,name in [(0,'ulaw'),(1,'alaw')]:
            self.assertEqual(self.media(mode,raw),struct.pack('<256h',*self.go[name]))
    def test_ulaw_encoder_all_pcm16_against_go_reference(self):
        raw=struct.pack('<65536h',*range(-32768,32768))
        self.assertEqual(self.media(2,raw),base64.b64decode(self.go['ulaw_encode']))
    def test_alaw_known_samples_and_decode_roundtrip(self):
        samples=[-32768,-1000,-1,0,1,1000,32767]
        encoded=self.media(3,struct.pack('<7h',*samples))
        self.assertEqual(encoded,bytes([0x2a,0x7a,0x55,0xd5,0xd5,0xfa,0xaa]))
        self.assertEqual(len(self.media(1,encoded)),14)
        self.assertEqual(self.media(2,b'x'),b'error');self.assertEqual(self.media(3,b'x'),b'error')
    def test_rtp_reorder_against_go_reference(self):
        for trace,expected in zip(self.traces,self.go['traces']):
            with self.subTest(trace=trace):self.assertEqual(self.media(7,json.dumps(trace).encode()).decode(),expected)
    def test_rtp_packet_roundtrip_and_padding(self):
        for sequence in [0,1,65535]:
            raw=struct.pack('!BBHII',0x80,0x80|111,sequence,0xffffffff,123)+b'payload'
            self.assertEqual(self.media(5,raw),raw);self.assertEqual(self.media(4,raw),f'{sequence} 4294967295 123 "payload"'.encode())
        raw=struct.pack('!BBHII',0xb1,8,42,48000,99)+struct.pack('!IHH',100,0xbede,1)+b'\x10\x00\x00\x00'+b'audio'+b'\0\0\0\x04'
        self.assertEqual(self.media(4,raw),b'42 48000 99 "audio"')
        expected=bytes([raw[0]&~32])+raw[1:-4];self.assertEqual(self.media(5,raw),expected)
        for invalid in [b'',b'\x80'*11,b'\x40'+b'\0'*11,b'\x90'+b'\0'*11,b'\xa0'+b'\0'*11]:self.assertEqual(self.media(5,invalid),b'error')
    def test_opus_packet_framing_against_libopus_oracle(self):
        name=os.environ.get('NEO_OPUS_ORACLE_LIBRARY') or ctypes.util.find_library('opus')
        if not name and os.path.exists('/opt/homebrew/lib/libopus.dylib'):name='/opt/homebrew/lib/libopus.dylib'
        if not name:self.skipTest('libopus is an independent test oracle; install only in tools environment')
        lib=ctypes.CDLL(name);byte=ctypes.c_ubyte;pointer=ctypes.POINTER(byte)
        lib.opus_packet_parse.argtypes=[pointer,ctypes.c_int32,ctypes.POINTER(byte),ctypes.POINTER(pointer),ctypes.POINTER(ctypes.c_int16),ctypes.POINTER(ctypes.c_int)];lib.opus_packet_parse.restype=ctypes.c_int
        lib.opus_packet_get_nb_samples.argtypes=[pointer,ctypes.c_int32,ctypes.c_int32];lib.opus_packet_get_nb_samples.restype=ctypes.c_int
        rng=random.Random(6716)
        packets=[b'',b'\xf8\xff\xfe',b'\x02',b'\x02\0',b'\x03\0',b'\x83\x30'+b'a'*48,b'\x83\xc3\x02\x01\x02'+b'abcdef'+b'\0\0']
        packets += [bytes([toc])+rng.randbytes(rng.randrange(0,50)) for toc in range(256)]
        for _ in range(120):packets.append(rng.randbytes(rng.randrange(0,200)))
        for raw in packets:
            data=(byte*max(1,len(raw)))(*raw);toc=byte();frames=(pointer*48)();sizes=(ctypes.c_int16*48)();offset=ctypes.c_int()
            count=lib.opus_packet_parse(data,len(raw),ctypes.byref(toc),frames,sizes,ctypes.byref(offset));got=self.media(6,raw)
            if count<0:self.assertEqual(got,b'error',raw);continue
            samples=lib.opus_packet_get_nb_samples(data,len(raw),48000)
            expected=f'{count} {samples} '+''.join(f'{ctypes.cast(frames[i],ctypes.c_void_p).value-ctypes.addressof(data)}:{sizes[i]},' for i in range(count))
            self.assertEqual(got,expected.encode(),raw)
if __name__=='__main__':unittest.main(verbosity=2)
