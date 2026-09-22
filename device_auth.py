"""OAuth 2.0 Device Authorization Grant (RFC 8628) -- shared polling/error
logic for any identity provider that supports it (GitHub, Google). Apple
does not: Sign in with Apple is a redirect-based web flow needing a paid
Developer account, a registered Services ID, and a JWT-signed client
secret, so it isn't built on this module. Stdlib only, no client secret
needed for any of this -- Device Flow is designed for exactly this case
(a public/installed app that can't keep a secret).
"""
import json,time,urllib.parse,urllib.request

_HEADERS={'Accept':'application/json','User-Agent':'Clarette-App'}
_ERRORS={'expired_token':'The sign-in code expired. Try again.','access_denied':'Sign-in was cancelled.'}

def _post(url,fields):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(fields).encode(),headers=_HEADERS)
    with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read())

def start(device_endpoint,client_id,scope):
    if not client_id:raise ValueError('Sign-in is not configured for this provider.')
    device=_post(device_endpoint,{'client_id':client_id,'scope':scope})
    # RFC 8628 names the field verification_uri; Google's device endpoint
    # predates the RFC and calls the same thing verification_url --
    # normalized once here so every caller only ever reads verification_uri.
    device.setdefault('verification_uri',device.get('verification_url'))
    return device

def wait_for_token(token_endpoint,client_id,device_code,interval,expires_in):
    """Blocks (sleep+poll) inside the caller's own request thread until the
    user approves or the code expires -- see github_auth.py/google_auth.py
    callers for why this isn't a separate polling endpoint."""
    if not device_code:raise ValueError('Start sign-in first')
    interval=max(1,int(interval or 5));deadline=time.time()+max(1,int(expires_in or 900))
    while True:
        time.sleep(interval)
        result=_post(token_endpoint,{'client_id':client_id,'device_code':device_code,'grant_type':'urn:ietf:params:oauth:grant-type:device_code'})
        error=result.get('error')
        if not error:return result['access_token']
        if error=='slow_down':interval+=5
        elif error!='authorization_pending':raise ValueError(_ERRORS.get(error,error))
        if time.time()>=deadline:raise ValueError('The sign-in code expired. Try again.')

def fetch_json(url,token):
    req=urllib.request.Request(url,headers={**_HEADERS,'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read())

def fetch_bytes(url):
    req=urllib.request.Request(url,headers=_HEADERS)
    with urllib.request.urlopen(req,timeout=15) as r:return r.read(),(r.headers.get('Content-Type') or 'image/jpeg').split(';')[0].strip()


def _demo():
    """ponytail self-check: the retry/error-mapping logic, without any real
    network access."""
    import unittest.mock as mock
    calls=[]
    def fake_post(url,fields):
        calls.append(fields.get('device_code'))
        if len(calls)==1:return {'error':'authorization_pending'}
        if len(calls)==2:return {'error':'slow_down'}
        return {'access_token':'tok_demo'}
    with mock.patch(f'{__name__}._post',fake_post),mock.patch('time.sleep',lambda s:None):
        token=wait_for_token('https://example/token','client','devcode',1,60)
        assert token=='tok_demo',token
        assert calls==['devcode','devcode','devcode'],calls
    def fake_post_denied(url,fields):return {'error':'access_denied'}
    with mock.patch(f'{__name__}._post',fake_post_denied),mock.patch('time.sleep',lambda s:None):
        try:
            wait_for_token('https://example/token','client','devcode',1,60);raise AssertionError('expected ValueError')
        except ValueError as e:assert str(e)=='Sign-in was cancelled.',str(e)
    def fake_post_device(url,fields):return {'device_code':'d','user_code':'ABCD-1234','verification_url':'https://example/activate','expires_in':900,'interval':5}
    with mock.patch(f'{__name__}._post',fake_post_device):
        device=start('https://example/device','client','scope')
        assert device['verification_uri']=='https://example/activate',device
    try:
        start('https://example/device','','scope');raise AssertionError('expected ValueError')
    except ValueError:pass
    print('PASS: device_auth retries pending/slow_down, maps error codes, and normalizes verification_url/uri')

if __name__=='__main__':
    _demo()
