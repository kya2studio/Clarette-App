"""Google sign-in: OAuth 2.0 Device Flow, no client secret needed (see
device_auth.py). CLIENT_ID is a public identifier, not a secret -- see
github_auth.py's docstring for why it's a constant, not just an env var.

Google's device/code endpoint only works for an OAuth client registered as
a "TVs and Limited Input devices" type in Google Cloud Console -- a Desktop
or Web client id will fail here with an error from Google, not this code.
"""
import os
import credentials
import device_auth

CLIENT_ID=os.environ.get('CLARETTE_GOOGLE_CLIENT_ID','1014938305928-hmnpu55hjtccrqfqo6ip9tbt792jitrg.apps.googleusercontent.com')
DEVICE_ENDPOINT='https://oauth2.googleapis.com/device/code'
TOKEN_ENDPOINT='https://oauth2.googleapis.com/token'

def start():
    return device_auth.start(DEVICE_ENDPOINT,CLIENT_ID,'openid email profile')

def wait_for_token(device_code,interval,expires_in):
    return device_auth.wait_for_token(TOKEN_ENDPOINT,CLIENT_ID,device_code,interval,expires_in)

def fetch_profile(token):
    user=device_auth.fetch_json('https://www.googleapis.com/oauth2/v3/userinfo',token)
    avatar,avatar_type=b'','image/jpeg'
    if user.get('picture'):
        try:avatar,avatar_type=device_auth.fetch_bytes(user['picture'])
        except OSError:pass
    return user.get('name') or user.get('email'),avatar,avatar_type

def sign_out():
    try:credentials.delete_key('google')
    except ValueError:pass
