import json,struct,unittest
from support import compile,run
class SRTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=compile('tests/srtp.neo','srtp')
    def neo(self,mode,doc):return run(self.binary,mode,data=json.dumps(doc).encode(),timeout=60).decode().splitlines()
    def packet(self,seq,ssrc=0x12345678,payload=b'audio',extension=False,padding=0):
        flags=0x80|(0x10 if extension else 0)|(0x20 if padding else 0)
        wire=struct.pack('!BBHII',flags,111,seq,seq*960%2**32,ssrc)
        if extension:wire+=struct.pack('!HH',0xbede,1)+b'\x10x\0\0'
        return (wire+payload+(bytes(padding-1)+bytes([padding]) if padding else b'')).hex()
    def test_rfc3711_derivation(self):
        doc={'key':'e1f97a0d3e018be0d64fa32c06de4139','salt':'0ec675ad498afeebb6960b3aabe6'}
        self.assertEqual(self.neo(0,doc),['c61e7a93744f39ee10734afe3ff7a087','cebe321f6ff7716b6fd4ab49af256a156d38baa4','30cbbc08863d8c85d49db34a9ae1'])

    def test_sender_rejects_nonce_reuse(self):
        doc={'key':'00'*16,'salt':'00'*14,'ssrc':0x12345678,'packets':[self.packet(1),self.packet(1)]}
        result=self.neo(1,doc);self.assertNotEqual(result[0],'error');self.assertEqual(result[1],'error')
if __name__=='__main__':unittest.main(verbosity=2)
