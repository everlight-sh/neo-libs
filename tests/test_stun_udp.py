import binascii,hashlib,hmac,struct,unittest
from support import compile,run
REQUEST=bytes.fromhex('000100582112a442b7e7a701bc34d686fa87dfae802200105354554e207465737420636c69656e74002400046e0001ff80290008932ff9b151263b36000600096576746a3a68367659202020000800149aeaa70cbfd8cb56781ef2b5b2d3f249c1b571a280280004e57a3bcf')
RESPONSE=bytes.fromhex('0101003c2112a442b7e7a701bc34d686fa87dfae8022000b7465737420766563746f7220002000080001a147e112a643000800142b91f599fd9e90c38c7489f92af9ba53f06be7d780280004c07d4c96')
class STUNTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.binary=compile('tests/stun.neo','stun');cls.udp=compile('tests/udp.neo','udp')
    def test_rfc5769_integrity_and_fingerprint(self):
        self.assertEqual(run(self.binary,1,data=REQUEST),b'valid');self.assertEqual(run(self.binary,1,data=RESPONSE),b'valid')
        self.assertEqual(run(self.binary,3,data=RESPONSE),b'192.0.2.1:32853')
    def test_reject_mutations(self):
        for i in range(len(REQUEST)):
            raw=bytearray(REQUEST);raw[i]^=1
            with self.subTest(offset=i):self.assertEqual(run(self.binary,1,data=raw),b'invalid')
    def test_generated_binding_against_python_crypto(self):
        raw=run(self.binary,2,data=b'');self.assertEqual(raw[:2],b'\0\1');self.assertEqual(len(raw),20+struct.unpack('!H',raw[2:4])[0])
        attrs={};at=20
        while at<len(raw):
            kind,length=struct.unpack('!HH',raw[at:at+4]);attrs[kind]=(at,raw[at+4:at+4+length]);at+=4+(length+3)//4*4
        self.assertEqual(attrs[6][1],b'remote:local');self.assertIn(0x802a,attrs);self.assertIn(0x25,attrs)
        offset,integrity=attrs[8];authenticated=raw[:2]+struct.pack('!H',offset+4)+raw[4:offset]
        self.assertEqual(integrity,hmac.new(b'password',authenticated,hashlib.sha1).digest())
        offset,value=attrs[0x8028];self.assertEqual(struct.unpack('!I',value)[0],binascii.crc32(raw[:offset])^0x5354554e)
    def test_crc32(self):
        for raw in [b'',b'123456789',bytes(range(256))]:self.assertEqual(run(self.binary,0,data=raw),str(binascii.crc32(raw)).encode())
    def test_udp_zero_datagrams_limits_and_cancellation(self):self.assertEqual(run(self.udp),b'UDP OK\n')
if __name__=='__main__':unittest.main(verbosity=2)
