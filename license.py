"""Offline license-key verification (Ed25519 signature, no server -- see
packaging/generate_license.py for the seller-side signing tool). A key is
"<base64url payload json>.<base64url signature>"; only the public key
lives here, so a leaked copy of this app can never mint new valid keys.
"""
import base64,json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PUBLIC_KEY='RzmjjEPcJ6WBt7C8kHC3kK852uBXd464r8BgDOfzHTU='

def _b64decode(s):
    s=s.strip()
    return base64.urlsafe_b64decode(s+'='*(-len(s)%4))

def verify(key):
    """Returns the license payload dict, or raises ValueError."""
    key=''.join(key.split())  # emailed keys are long enough that mail clients often line-wrap them
    try:payload_b64,sig_b64=key.split('.')
    except ValueError:raise ValueError('That license key is not formatted correctly.')
    try:payload,signature=_b64decode(payload_b64),_b64decode(sig_b64)
    except (ValueError,TypeError):raise ValueError('That license key is not formatted correctly.')
    try:Ed25519PublicKey.from_public_bytes(_b64decode(PUBLIC_KEY)).verify(signature,payload)
    except InvalidSignature:raise ValueError('That license key is not valid.')
    try:return json.loads(payload)
    except ValueError:raise ValueError('That license key is not valid.')

def status(settings):
    key=settings.get('license_key','')
    if not key:return {'licensed':False,'email':None,'issued':None,'error':None}
    try:
        payload=verify(key);return {'licensed':True,'email':payload.get('email'),'issued':payload.get('issued'),'error':None}
    except ValueError as e:return {'licensed':False,'email':None,'issued':None,'error':str(e)}


def _demo():
    """ponytail self-check: a key signed with a throwaway keypair verifies;
    tampering with it, or using someone else's public key, does not."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    global PUBLIC_KEY
    priv=Ed25519PrivateKey.generate()
    real_public=PUBLIC_KEY
    PUBLIC_KEY=base64.urlsafe_b64encode(priv.public_key().public_bytes_raw()).decode()
    payload=json.dumps({'email':'buyer@example.com','issued':'2026-01-01'}).encode()
    sig=priv.sign(payload)
    key='.'.join(base64.urlsafe_b64encode(part).decode() for part in (payload,sig))
    assert verify(key)['email']=='buyer@example.com'
    assert status({'license_key':key})=={'licensed':True,'email':'buyer@example.com','issued':'2026-01-01','error':None}
    assert status({})['licensed'] is False
    tampered=key[:-4]+'AAAA'
    try:verify(tampered);raise AssertionError('tampered key must not verify')
    except ValueError:pass
    PUBLIC_KEY=real_public
    print('PASS: license verifies a genuine key and rejects a tampered one')

if __name__=='__main__':_demo()
