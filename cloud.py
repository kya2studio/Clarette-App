"""Explicit cloud image edits; local operations never call these providers."""
import base64,io,re
import requests
from credentials import get_key

def checked(response):
    if not response.ok:
        # Never echo a provider response, request URL, or authentication data.
        reasons={401:'API key was rejected',403:'Account does not have access',429:'Rate or billing limit reached',400:'Check the selected image model and request',404:'The selected model is unavailable'}
        raise ValueError(reasons.get(response.status_code,'Provider request failed')+f' (HTTP {response.status_code})')
    return response.json()

COMPATIBLE={
    'openai':['gpt-image-2.5-sunburst','gpt-image-2.5-flare','gpt-image-2','gpt-image-1.5','gpt-image-1'],
    'gemini':['gemini-3.1-flash-image','gemini-3.1-flash-lite-image','gemini-3-pro-image','gemini-2.5-flash-image'],
    'seedream':['dola-seedream-5-0-pro-260628','seedream-4-0-250828'],
}

def preflight(provider,model,prompt):
    if provider not in COMPATIBLE:raise ValueError('Choose an AI provider')
    if not isinstance(model,str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',model):raise ValueError('Enter a valid image model ID in Settings')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>16000:raise ValueError('Enter a prompt under 16,000 characters')
    get_key(provider) # Fail before creating any paid request.

def test_connection(provider):
    if provider not in COMPATIBLE:raise ValueError('Unknown provider')
    key=get_key(provider)
    try:
        if provider=='openai':
            data=checked(requests.get('https://api.openai.com/v1/models',headers={'Authorization':'Bearer '+key},timeout=(10,20)))
            ids={x['id'] for x in data.get('data',[])}
        elif provider=='gemini':
            data=checked(requests.get('https://generativelanguage.googleapis.com/v1beta/models',headers={'x-goog-api-key':key},timeout=(10,20)))
            ids={x['name'].removeprefix('models/') for x in data.get('models',[]) if 'generateContent' in x.get('supportedGenerationMethods',[])}
        else:
            # ModelArk has no verified image-capability discovery contract in this adapter.
            return {'ok':False,'models':COMPATIBLE[provider],'status':'Key saved; verified connection test unavailable. No billable test was sent.'}
        models=sorted(m for m in ids if (m.startswith('gpt-image-') if provider=='openai' else m.startswith('gemini-') and 'image' in m))
        return {'ok':True,'models':models,'status':'Connected' if models else 'Connected; no image models listed. You can enter a model ID manually.'}
    except requests.RequestException:raise ValueError('Could not reach the provider. Check your connection.') from None

def enhance(im,provider,model,prompt,report):
    import imaging
    preflight(provider,model,prompt)
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',model):raise ValueError('Invalid model name')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>16000:raise ValueError('Enter a prompt under 16,000 characters')
    key=get_key(provider);raw=imaging.png(im)
    report('Sending the selected portrait for cloud enhancement…')
    try:
        if provider=='openai':
            r=requests.post('https://api.openai.com/v1/images/edits',headers={'Authorization':'Bearer '+key},files={'image':('portrait.png',raw,'image/png')},data={'model':model,'prompt':prompt,'size':'auto','output_format':'png'},timeout=(20,240))
            data=checked(r);encoded=data['data'][0]['b64_json']
        elif provider=='gemini':
            r=requests.post('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',headers={'x-goog-api-key':key},json={'contents':[{'parts':[{'text':prompt},{'inlineData':{'mimeType':'image/png','data':base64.b64encode(raw).decode()}}]}],'generationConfig':{'responseModalities':['TEXT','IMAGE']}},timeout=(20,240))
            data=checked(r);parts=data.get('candidates',[{}])[0].get('content',{}).get('parts',[])
            encoded=next((p.get('inlineData',p.get('inline_data',{})).get('data') for p in parts if p.get('inlineData',p.get('inline_data',{})).get('data')),None)
            if not encoded:raise ValueError('Provider returned no image. Try another prompt or image model.')
        else:
            # BytePlus ModelArk Image Generation API, compatible Seedream 4.0.
            # Base64 avoids publishing the user's source at a public URL.
            r=requests.post('https://ark.ap-southeast.bytepluses.com/api/v3/images/generations',
                headers={'Authorization':'Bearer '+key},json={'model':model,'prompt':prompt,
                'image':'data:image/png;base64,'+base64.b64encode(raw).decode(),
                'size':'2K','response_format':'b64_json','sequential_image_generation':'disabled',
                'stream':False,'watermark':False},timeout=(20,240))
            data=checked(r);encoded=data['data'][0]['b64_json']
        report('Loading the enhanced portrait…');return imaging.load(io.BytesIO(base64.b64decode(encoded,validate=True)))
    except requests.RequestException:raise ValueError('Cloud request interrupted or timed out. Your previous image is preserved.') from None
    except (KeyError,IndexError):raise ValueError('Provider returned no editable image') from None
