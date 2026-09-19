"""Explicit Siri/Shortcuts actions; no microphone or background listening."""
import json, os, sys, urllib.request, urllib.error
from pathlib import Path

COMMANDS={'enhance':'/api/enhance','detect-subject':'/api/mask-detect','auto-fit':'/api/detect','undo':'/api/undo','redo':'/api/redo'}

def command_request(command,batch,selected):
    if command not in COMMANDS: raise ValueError('Unknown Clarette voice action')
    payload={'batch':batch,'id':selected}
    if command=='enhance': payload.update(scale=1,amount=70)
    return COMMANDS[command],payload

def publish_connection(data,url,token):
    path=Path(data)/'automation.json'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as file:json.dump({'url':url,'token':token},file)

def invoke(command,data):
    command_request(command,'','')
    try: config=json.loads((Path(data)/'automation.json').read_text())
    except (OSError,ValueError):raise ValueError('Open Clarette and select a portrait first.')
    from urllib.parse import urlparse
    parsed=urlparse(config['url'])
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1':raise ValueError('Invalid local Clarette connection')
    request=urllib.request.Request(config['url']+'/api/voice',data=json.dumps({'command':command}).encode(),headers={'Content-Type':'application/json','X-Glass-Token':config['token']},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        try:message=json.load(error).get('error','Clarette could not perform the action.')
        except ValueError:message='Clarette could not perform the action.'
        raise ValueError(message)
    except urllib.error.URLError:raise ValueError('Open Clarette and select a portrait first.')

def main(args=None):
    from support import support_dir
    args=sys.argv[1:] if args is None else args
    try:
        if len(args)!=1:raise ValueError('Choose one action: '+', '.join(COMMANDS))
        result=invoke(args[0],support_dir())
        print('Clarette started the action. A notification will report completion.' if result.get('job') else 'Clarette completed the action.')
    except Exception as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)

if __name__=='__main__':main()
