#!/usr/bin/env python3
"""Seller-side tool: signs a new Clarette license key for one buyer.

Run this on your own machine only -- never bundle it or the private key
inside the shipped app (packaging/GlassStudio.spec doesn't reference this
file, so it never ends up in dist/Clarette.app). Keep the private key in a
password manager, not in this file or any git repo; pass it via the
CLARETTE_LICENSE_PRIVATE_KEY env var each time you run this.

Usage:
    CLARETTE_LICENSE_PRIVATE_KEY=<private key> python3 generate_license.py buyer@example.com [gift|purchased|personal]
"""
import base64,datetime,json,os,sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

TYPES=('purchased','gift','personal')

def generate(email,private_key_b64,kind='purchased'):
    if kind not in TYPES:raise ValueError('type must be one of '+', '.join(TYPES))
    private_key=Ed25519PrivateKey.from_private_bytes(base64.urlsafe_b64decode(private_key_b64+'='*(-len(private_key_b64)%4)))
    payload=json.dumps({'email':email,'issued':datetime.date.today().isoformat(),'type':kind}).encode()
    signature=private_key.sign(payload)
    return '.'.join(base64.urlsafe_b64encode(part).decode() for part in (payload,signature))


if __name__=='__main__':
    if len(sys.argv) not in (2,3):sys.exit('Usage: generate_license.py <buyer-email> [gift|purchased|personal]')
    private_key_b64=os.environ.get('CLARETTE_LICENSE_PRIVATE_KEY')
    if not private_key_b64:sys.exit('Set CLARETTE_LICENSE_PRIVATE_KEY to the private key (see license.py header).')
    try:print(generate(sys.argv[1],private_key_b64,sys.argv[2] if len(sys.argv)==3 else 'purchased'))
    except ValueError as e:sys.exit(str(e))
