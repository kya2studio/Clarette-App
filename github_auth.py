"""GitHub OAuth Device Flow sign-in -- stdlib only, no client secret needed
for a desktop app. The token itself never enters session.json (Keychain
only, via credentials.py's existing pattern); only the non-secret login
live in app.py's S['settings'].

Two calls, not a polling endpoint the frontend has to manage on a timer:
start() returns the code to show the user right away, wait_for_token() then
blocks (sleep+poll) inside that one request until GitHub reports success or
failure. ThreadingHTTPServer gives every request its own thread, so one
long-lived sign-in request doesn't block anything else in the app while
it waits -- ponytail: that's a smaller diff than a second endpoint plus a
client-side interval timer and its own cancel/cleanup bookkeeping.
"""
import json,os,time,urllib.parse,urllib.request
import credentials

CLIENT_ID=os.environ.get('CLARETTE_GITHUB_CLIENT_ID','')
_HEADERS={'Accept':'application/json','User-Agent':'Clarette-App'}
_ERRORS={'expired_token':'The sign-in code expired. Try again.','access_denied':'Sign-in was cancelled.'}

def _post(url,fields):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(fields).encode(),headers=_HEADERS)
    with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read())

def start():
    if not CLIENT_ID:raise ValueError('GitHub sign-in is not configured (set CLARETTE_GITHUB_CLIENT_ID).')
    return _post('https://github.com/login/device/code',{'client_id':CLIENT_ID,'scope':'read:user'})

def wait_for_token(device_code,interval,expires_in):
    if not device_code:raise ValueError('Start GitHub sign-in first')
    interval=max(1,int(interval or 5));deadline=time.time()+max(1,int(expires_in or 900))
    while True:
        time.sleep(interval)
        result=_post('https://github.com/login/oauth/access_token',{'client_id':CLIENT_ID,'device_code':device_code,'grant_type':'urn:ietf:params:oauth:grant-type:device_code'})
        error=result.get('error')
        if not error:return result['access_token']
        if error=='slow_down':interval+=5
        elif error!='authorization_pending':raise ValueError(_ERRORS.get(error,error))
        if time.time()>=deadline:raise ValueError('The sign-in code expired. Try again.')

def fetch_profile(token):
    req=urllib.request.Request('https://api.github.com/user',headers={**_HEADERS,'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=15) as r:user=json.loads(r.read())
    avatar,avatar_type=b'','image/jpeg'
    try:
        req=urllib.request.Request(user['avatar_url'],headers=_HEADERS)
        with urllib.request.urlopen(req,timeout=15) as r:avatar=r.read();avatar_type=(r.headers.get('Content-Type') or avatar_type).split(';')[0].strip()
    except OSError:pass
    return user.get('login'),avatar,avatar_type

def sign_out():
    try:credentials.delete_key('github')
    except ValueError:pass


def _demo():
    """ponytail self-check: exercises the error-mapping/retry logic without
    any real network access, by faking _post."""
    import unittest.mock as mock
    calls=[]
    def fake_post(url,fields):
        calls.append(fields.get('device_code'))
        if len(calls)==1:return {'error':'authorization_pending'}
        if len(calls)==2:return {'error':'slow_down'}
        return {'access_token':'tok_demo'}
    with mock.patch(f'{__name__}._post',fake_post),mock.patch('time.sleep',lambda s:None):
        token=wait_for_token('devcode',1,60)
        assert token=='tok_demo',token
        assert calls==['devcode','devcode','devcode'],calls
    def fake_post_denied(url,fields):return {'error':'access_denied'}
    with mock.patch(f'{__name__}._post',fake_post_denied),mock.patch('time.sleep',lambda s:None):
        try:
            wait_for_token('devcode',1,60);raise AssertionError('expected ValueError')
        except ValueError as e:assert str(e)=='Sign-in was cancelled.',str(e)
    print('PASS: wait_for_token retries pending/slow_down and maps GitHub error codes')

if __name__=='__main__':
    _demo()
