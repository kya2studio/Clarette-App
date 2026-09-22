"""GitHub sign-in: OAuth 2.0 Device Flow, no client secret needed (see
device_auth.py). CLIENT_ID is a public identifier, not a secret -- it's
meant to ship inside the app itself, the same way every real desktop OAuth
integration embeds one; an env var only exists here as an override for
local testing before an ID is registered.
"""
import os
import credentials
import device_auth

CLIENT_ID=os.environ.get('CLARETTE_GITHUB_CLIENT_ID','')
DEVICE_ENDPOINT='https://github.com/login/device/code'
TOKEN_ENDPOINT='https://github.com/login/oauth/access_token'

def start():
    return device_auth.start(DEVICE_ENDPOINT,CLIENT_ID,'read:user')

def wait_for_token(device_code,interval,expires_in):
    return device_auth.wait_for_token(TOKEN_ENDPOINT,CLIENT_ID,device_code,interval,expires_in)

def fetch_profile(token):
    user=device_auth.fetch_json('https://api.github.com/user',token)
    avatar,avatar_type=b'','image/jpeg'
    if user.get('avatar_url'):
        try:avatar,avatar_type=device_auth.fetch_bytes(user['avatar_url'])
        except OSError:pass
    return user.get('login'),avatar,avatar_type

def sign_out():
    try:credentials.delete_key('github')
    except ValueError:pass
