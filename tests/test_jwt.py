"""Independent OpenSSL signatures; native Neo implementation never calls OpenSSL."""
import base64,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urlencode
from support import NEO

ROOT=Path(__file__).resolve().parents[1]
def b64(value):return base64.urlsafe_b64encode(value).decode().rstrip('=')
def compact(value):return json.dumps(value,separators=(',',':'),ensure_ascii=False)

class JWTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='neo-jwt-');cls.addClassCleanup(cls.directory.cleanup)
        cls.work=Path(cls.directory.name);cls.binary=cls.work/'jwt'
        subprocess.run([NEO,'build',str(ROOT/'tests/jwt.neo'),'-o',str(cls.binary)],check=True,capture_output=True)
        cls.oidc=cls.work/'oidc'
        subprocess.run([NEO,'build',str(ROOT/'tests/oidc.neo'),'-o',str(cls.oidc)],check=True,capture_output=True)
        cls.key=cls.work/'key.pem'
        subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(cls.key)],check=True,capture_output=True)
        modulus=subprocess.check_output(['openssl','rsa','-in',str(cls.key),'-noout','-modulus'],stderr=subprocess.DEVNULL).decode().strip().split('=')[1]
        cls.jwk={'kty':'RSA','kid':'test-key','alg':'RS256','use':'sig','key_ops':['verify'],'n':b64(bytes.fromhex(modulus)),'e':'AQAB'}
        cls.claims={'iss':'https://issuer.test','sub':'account-42','aud':'test-client','nonce':'test-nonce-at-least-16-bytes','iat':1999999900,'exp':2000000300}
    def token(self,claims=None,header=None,raw=None,head_raw=None):
        body=raw if raw is not None else compact(self.claims if claims is None else claims)
        head=head_raw if head_raw is not None else compact(header or {'alg':'RS256','kid':'test-key','typ':'JWT'})
        message=(b64(head.encode())+'.'+b64(body.encode())).encode()
        signature=subprocess.check_output(['openssl','dgst','-sha256','-sign',str(self.key)],input=message)
        return message.decode()+'.'+b64(signature)
    def verify(self,token,jwks=None):
        tokenfile=self.work/'token';keyfile=self.work/'jwks'
        tokenfile.write_text(token);keyfile.write_text(compact({'keys':[self.jwk]}) if jwks is None else compact(jwks) if isinstance(jwks,dict) else jwks)
        result=subprocess.run([str(self.binary)],env={**os.environ,'JWT_TOKEN_FILE':str(tokenfile),'JWT_JWKS_FILE':str(keyfile)},capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr.decode());return result.stdout.decode().strip()
    def test_valid_claims_and_audiences(self):
        cases=[self.claims,{**self.claims,'aud':['test-client']},{**self.claims,'aud':['test-client','other'],'azp':'test-client'},
               {**self.claims,'at_hash':b64(hashlib.sha256(b'opaque-access-token').digest()[:16])}]
        for claims in cases:
            with self.subTest(claims=claims):self.assertEqual(self.verify(self.token(claims)),'OK:account-42')
    def test_claims_fail_closed(self):
        for changes in [{'iss':'https://attacker.test'},{'aud':'other'},{'aud':['test-client','other']},{'azp':'other'},{'aud':['test-client',4],'azp':'test-client'},
                        {'nonce':'wrong'},{'exp':1999999900},{'iat':2000000031},{'iat':1999996000},{'nbf':2000000031},{'nbf':'2000000000'},
                        {'exp':9223372036854775808},{'exp':'2000000300'},{'sub':''},{'sub':'bad\0subject'},{'at_hash':'wrong'}]:
            with self.subTest(changes=changes):self.assertTrue(self.verify(self.token({**self.claims,**changes})).startswith('ERROR:'))
        for field in ['iss','sub','aud','iat','exp','nonce']:
            claims={**self.claims};claims.pop(field)
            with self.subTest(missing=field):self.assertTrue(self.verify(self.token(claims)).startswith('ERROR:'))
    def test_signature_encoding_and_algorithm_confusion(self):
        token=self.token();parts=token.split('.')
        for bad in ['',token+'.extra','.'.join(parts[:2])+'.','.'.join([parts[0],b64(compact({**self.claims,'sub':'attacker'}).encode()),parts[2]]),
                    token[:-10],'.'.join([parts[0]+'=',parts[1],parts[2]]),token+'=',token+'\n']:
            with self.subTest(token=bad[:30]):self.assertTrue(self.verify(bad).startswith('ERROR:'))
        for changes in [{'alg':'none'},{'alg':'HS256'},{'kid':'missing'},{'crit':['custom']},{'b64':True},{'jku':'https://attacker.test/jwks'},{'jwk':self.jwk},{'typ':'at+jwt'}]:
            with self.subTest(header=changes):self.assertTrue(self.verify(self.token(header={'alg':'RS256','kid':'test-key',**changes})).startswith('ERROR:'))
    def test_duplicate_members_and_key_selection(self):
        raw=compact(self.claims)[:-1]+',"\\u0061ud":"test-client"}'
        self.assertTrue(self.verify(self.token(raw=raw)).startswith('ERROR:'))
        self.assertTrue(self.verify(self.token(head_raw='{"alg":"none","alg":"RS256","kid":"test-key"}')).startswith('ERROR:'))
        token=self.token()
        for jwks in [{'keys':[]},{'keys':[self.jwk,self.jwk]},{'keys':[self.jwk]*33}]:self.assertTrue(self.verify(token,jwks).startswith('ERROR:'))
        for changes in [{'e':'Aw'},{'n':'AQAB'},{'alg':'HS256'},{'use':'enc'},{'key_ops':['sign']},{'d':'private'},{'kty':'oct'}]:
            with self.subTest(key=changes):self.assertTrue(self.verify(token,{'keys':[{**self.jwk,**changes}]}).startswith('ERROR:'))
        self.assertEqual(self.verify(token,{'keys':[{**self.jwk,'kid':'old'},self.jwk]}),'OK:account-42')
    def test_oidc_authorization_code_chain(self):
        start=json.loads(subprocess.check_output([str(self.oidc),'0']))
        query=parse_qs(urlsplit(start['url']).query);nonce=query['nonce'][0]
        self.assertEqual(nonce,query['state'][0]);self.assertEqual(query['code_challenge_method'],['S256'])
        claims={**self.claims,'nonce':nonce}
        (self.work/'jwks.json').write_text(compact({'keys':[self.jwk]}))
        def exchange(claims,subject='account-42',cookie=None):
            (self.work/'token.json').write_text(compact({'access_token':'opaque-access-token','token_type':'Bearer','id_token':self.token(claims)}))
            (self.work/'userinfo.json').write_text(compact({'sub':subject,'name':'Test User'}))
            env={**os.environ,'OIDC_COOKIE':start['cookie'] if cookie is None else cookie,'OIDC_QUERY':urlencode({'state':query['state'][0],'code':'test-code'})}
            result=subprocess.run([str(self.oidc),'1'],cwd=self.work,env=env,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode());return result.stdout.decode().strip()
        self.assertEqual(exchange(claims),'OK:https://issuer.test|account-42')
        for changes in [{'nonce':'wrong'},{'iss':'https://other.test'},{'aud':'other'},{'exp':1999999900}]:
            with self.subTest(exchange=changes):self.assertTrue(exchange({**claims,**changes}).startswith('ERROR:'))
        self.assertTrue(exchange(claims,subject='other-account').startswith('ERROR:'))
        self.assertTrue(exchange(claims,cookie=start['cookie']+'x').startswith('ERROR:'))

if __name__=='__main__':unittest.main(verbosity=2)
