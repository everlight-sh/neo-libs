"""Test certificate authorities, leaves and broken variants, made with the openssl CLI.

Copied from Neo's tests/tls_language.py (v0.2.4) so these tests no longer need a
Neo checkout. openssl is an independent test tool, never linked into a library.
"""
import subprocess


def openssl(*args,data=None):
    r=subprocess.run(['openssl',*map(str,args)],input=data,capture_output=True,timeout=60)
    assert r.returncode==0,r.stderr
    return r.stdout


def certificates(root):
    openssl('req','-new','-x509','-newkey','rsa:2048','-nodes','-keyout',root/'ca.key','-out',root/'ca.pem','-subj','/CN=Neo Test Root','-days','2','-sha256',
        '-addext','basicConstraints=critical,CA:TRUE,pathlen:1','-addext','keyUsage=critical,keyCertSign,cRLSign')
    openssl('req','-new','-newkey','rsa:2048','-nodes','-keyout',root/'leaf.key','-out',root/'leaf.csr','-subj','/CN=localhost')
    variants={'leaf':'','unknown':'1.2.3.4.5=critical,DER:05:00\n','wrong-eku':'','wildcard':'','ca-leaf':''}
    for name,extra in variants.items():
        config='basicConstraints=critical,CA:'+('TRUE' if name=='ca-leaf' else 'FALSE')+'\nkeyUsage=critical,digitalSignature\nextendedKeyUsage='+('clientAuth' if name=='wrong-eku' else 'serverAuth')+'\nsubjectAltName='+('DNS:*.example.test' if name=='wildcard' else 'DNS:localhost,IP:127.0.0.1')+'\n'+extra
        (root/'extensions').write_text(config)
        openssl('x509','-req','-in',root/'leaf.csr','-CA',root/'ca.pem','-CAkey',root/'ca.key','-CAcreateserial','-out',root/(name+'.pem'),'-days','1','-sha256','-extfile',root/'extensions')
    for name in ['ca',*variants]:openssl('x509','-in',root/(name+'.pem'),'-outform','DER','-out',root/(name+'.der'))
    openssl('req','-new','-newkey','rsa:2048','-nodes','-keyout',root/'middle.key','-out',root/'middle.csr','-subj','/CN=Neo Test Intermediate')
    for name,usage in [('middle','keyCertSign,cRLSign'),('middle-wrong-ku','digitalSignature')]:
        (root/'extensions').write_text('basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,'+usage+'\n')
        openssl('x509','-req','-in',root/'middle.csr','-CA',root/'ca.pem','-CAkey',root/'ca.key','-CAcreateserial','-out',root/(name+'.pem'),'-days','1','-sha256','-extfile',root/'extensions')
        openssl('x509','-in',root/(name+'.pem'),'-outform','DER','-out',root/(name+'.der'))
    (root/'extensions').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
    openssl('x509','-req','-in',root/'leaf.csr','-CA',root/'middle.pem','-CAkey',root/'middle.key','-CAcreateserial','-out',root/'middle-leaf.pem','-days','1','-sha256','-extfile',root/'extensions')
    openssl('x509','-in',root/'middle-leaf.pem','-outform','DER','-out',root/'middle-leaf.der')
    (root/'intermediate-chain.pem').write_bytes((root/'middle-leaf.pem').read_bytes()+(root/'middle.pem').read_bytes())
    openssl('req','-new','-x509','-key',root/'ca.key','-out',root/'zero-ca.pem','-subj','/CN=Neo Test Root','-days','2','-sha256',
        '-addext','basicConstraints=critical,CA:TRUE,pathlen:0','-addext','keyUsage=critical,keyCertSign,cRLSign')
    openssl('x509','-in',root/'zero-ca.pem','-outform','DER','-out',root/'zero-ca.der')
    corrupted=bytearray((root/'leaf.der').read_bytes());corrupted[-1]^=1;(root/'signature.der').write_bytes(corrupted)
    openssl('x509','-inform','DER','-in',root/'signature.der','-out',root/'signature.pem')
    openssl('req','-new','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes','-keyout',root/'ec-ca.key','-out',root/'ec-ca.pem','-subj','/CN=Neo EC Test Root','-days','2','-sha256',
        '-addext','basicConstraints=critical,CA:TRUE,pathlen:1','-addext','keyUsage=critical,keyCertSign,cRLSign')
    openssl('req','-new','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes','-keyout',root/'ec-leaf.key','-out',root/'ec-leaf.csr','-subj','/CN=localhost')
    (root/'extensions').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n')
    for name,csr,issuer in [('ec-leaf','ec-leaf','ec-ca'),('ec-cross','ec-leaf','ca'),('rsa-ec','leaf','ec-ca')]:
        openssl('x509','-req','-in',root/(csr+'.csr'),'-CA',root/(issuer+'.pem'),'-CAkey',root/(issuer+'.key'),'-CAcreateserial','-out',root/(name+'.pem'),'-days','1','-sha256','-extfile',root/'extensions')
        openssl('x509','-in',root/(name+'.pem'),'-outform','DER','-out',root/(name+'.der'))
    openssl('x509','-in',root/'ec-ca.pem','-outform','DER','-out',root/'ec-ca.der')
    return root
