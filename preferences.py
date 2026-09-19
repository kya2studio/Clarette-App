"""Validated preferences, portable workspaces and protected output presets."""
import copy
import math
from pathlib import Path

BUILTINS = {
    'landscape': dict(label='Landscape Headshot', width=2048, height=1024, dpi=72, headW=.255, headTop=.035),
    'passport': dict(label='U.S. Passport Photo', width=600, height=600, dpi=300, headW=.45, headTop=.10,
                     guide=dict(cx=.5, top=.10, width=.45, height=.59, eyes=.45)),
    'linkedin': dict(label='LinkedIn Profile', width=800, height=800, dpi=72, headW=.48, headTop=.08),
    'social': dict(label='Social Media Profile', width=1080, height=1080, dpi=72, headW=.48, headTop=.08),
    'website': dict(label='Website Profile', width=1200, height=1200, dpi=72, headW=.48, headTop=.08),
    'print': dict(label='Print Headshot', width=2400, height=3000, dpi=300, headW=.48, headTop=.08),
}
PANELS = ['portraits', 'preview', 'adjustments']
WORKSPACES = {
    'landscape': dict(name='Landscape Mode', orientation='horizontal', order=PANELS, sizes=[250, 700, 350], locked=False),
    'portrait': dict(name='Portrait Mode', orientation='nested', order=['preview', 'portraits', 'adjustments'], sizes=[600, 340, 340], locked=False),
}

def defaults():
    return dict(final_folder=str(Path.home()/'Documents/Clarette/Final Output'), model='birefnet-general-lite',
                quality_cutout=True, notifications=True, notification_sound=False, voice_commands=False, show_panel_names=True,
                upscale_method='fast', accelerate=True, auto_guide=True, preview_color=True, face_restore=False,
                masking_enabled=True, solid_preview=False, preview_background='#00a84f', checker_brightness=35,
                cutout_format='PNG', photo_format='JPEG', jpeg_quality=95, tiff_compression='tiff_lzw',
                embed_profile=True, metadata_mode='preserve', processing_metadata=False, print_profile='',
                enhancement_prompt='', restore_location='', hypir_location='', osediff_location='', flowsr_location='', seesr_location='', enhancement_provider='classical', toolbar_apps=['photoshop'],
                openai_model='gpt-image-2.5-sunburst', gemini_model='gemini-3.1-flash-image', seedream_model='dola-seedream-5-0-pro-260628')

def validate_settings(values, previous=None):
    if not isinstance(values, dict): raise ValueError('Settings must be an object')
    result=copy.deepcopy(previous or defaults())
    known=defaults()
    for key,value in values.items():
        if key not in known: continue
        default=known[key]
        if type(default) is bool and type(value) is not bool: raise ValueError('Invalid '+key)
        if type(default) is str and (not isinstance(value,str) or len(value)>4096): raise ValueError('Invalid '+key)
        result[key]=copy.deepcopy(value)
    for key,options in {'model':['birefnet-general-lite','birefnet-general','birefnet-portrait','u2netp'],
                        'upscale_method':['neural','fast'], 'cutout_format':['PNG','TIFF'],
                        'photo_format':['JPEG','PNG','TIFF'], 'tiff_compression':['raw','tiff_lzw','tiff_adobe_deflate'],
                        'metadata_mode':['preserve','copyright','strip'],
                        'enhancement_provider':['classical','restore','edsr','hypir','osediff','flowsr','seesr','openai','gemini','seedream']}.items():
        if result[key] not in options: raise ValueError('Invalid '+key)
    for key,lo,hi in [('jpeg_quality',1,100),('checker_brightness',0,100)]:
        if type(result[key]) not in (int,float) or not math.isfinite(result[key]) or not lo<=result[key]<=hi: raise ValueError('Invalid '+key)
        result[key]=int(result[key])
    import re
    for key in ('openai_model','gemini_model','seedream_model'):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',result[key]):raise ValueError('Enter a valid image model ID')
    if not re.fullmatch('#[a-fA-F0-9]{6}',result['preview_background']): raise ValueError('Choose a valid preview color')
    if not isinstance(result['toolbar_apps'],list) or any(x not in ('photoshop','affinity','photos') for x in result['toolbar_apps']): raise ValueError('Invalid external application')
    return result

def validate_workspace(value):
    if not isinstance(value,dict) or sorted(value.get('order',[]))!=sorted(PANELS): raise ValueError('A workspace must contain each panel once')
    if value.get('orientation') not in ('horizontal','vertical','nested'): raise ValueError('Invalid workspace orientation')
    sizes=value.get('sizes',[])
    if len(sizes)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or not 160<=x<=5000 for x in sizes): raise ValueError('Invalid panel sizes')
    name=str(value.get('name','')).strip()
    if not name or len(name)>80: raise ValueError('Enter a workspace name under 80 characters')
    divider=value.get('divider_size',5)
    if type(divider) not in (int,float) or not 3<=divider<=20:raise ValueError('Invalid divider size')
    visible=value.get('visible',{})
    if not isinstance(visible,dict):raise ValueError('Invalid panel visibility')
    return dict(name=name,orientation=value['orientation'],order=list(value['order']),sizes=list(sizes),locked=bool(value.get('locked',False)),divider_size=3,show_dividers=bool(value.get('show_dividers',True)),visible={p:True if p=='preview' else bool(visible.get(p,True)) for p in PANELS})

def recover_settings(value):
    """Keep individually valid preferences from an untrusted saved session."""
    result=defaults();repaired=not isinstance(value,dict)
    if not isinstance(value,dict):return result,repaired
    for key,item in value.items():
        if key in result:
            try:result=validate_settings({key:item},result)
            except (TypeError,ValueError,OverflowError):repaired=True
        elif key in ('openai_connected','gemini_connected','seedream_connected'):
            if type(item) is bool:result[key]=item
            else:repaired=True
        elif key=='default_guides':
            guides={}
            if isinstance(item,dict):
                from guides import validate_guide
                for preset_id,guide in item.items():
                    try:
                        if not isinstance(preset_id,str) or not preset_id or len(preset_id)>100:raise ValueError()
                        guides[preset_id]=validate_guide(guide)
                    except (KeyError,TypeError,ValueError,OverflowError):repaired=True
            else:repaired=True
            result[key]=guides
        else:
            # Old ad-hoc keys, including any legacy secrets, do not re-enter state.
            repaired=True
    return result,repaired

def recover_preset(value,max_pixels):
    """Return a safe output-size record, or None when its geometry is unusable."""
    if not isinstance(value,dict):return None,True
    result=copy.deepcopy(value);repaired=False
    try:
        width,height,dpi=(result[k] for k in ('width','height','dpi'))
        if any(type(v) is not int for v in (width,height,dpi)):raise ValueError()
        if not 16<=width<=32768 or not 16<=height<=32768 or width*height>max_pixels or not 1<=dpi<=1200:raise ValueError()
        label=result.get('label','Custom')
        if not isinstance(label,str) or not label.strip() or len(label)>100:raise ValueError()
        result['label']=label.strip()
        head_width=float(result.get('headW',.255));head_top=float(result.get('headTop',.035))
        if not math.isfinite(head_width+head_top) or not .05<=head_width<=.95 or not 0<=head_top<=.8:raise ValueError()
        result['headW']=head_width;result['headTop']=head_top
    except (KeyError,TypeError,ValueError,OverflowError):return None,True
    if 'guide' in result:
        try:
            from guides import validate_guide
            result['guide']=validate_guide(result['guide'])
        except (KeyError,TypeError,ValueError,OverflowError):
            result.pop('guide',None);repaired=True
    preset_id=result.get('preset_id')
    if preset_id is not None and (not isinstance(preset_id,str) or not preset_id or len(preset_id)>100):
        result.pop('preset_id',None);repaired=True
    return result,repaired

def recover_workspaces(value):
    """Preserve valid customized workspaces while restoring protected defaults."""
    result=copy.deepcopy(WORKSPACES);repaired=value is not None and not isinstance(value,dict)
    if value is None:return result,repaired
    if not isinstance(value,dict):return result,True
    for key,item in value.items():
        try:
            if not isinstance(key,str) or not key or len(key)>100:raise ValueError()
            result[key]=validate_workspace(item)
        except (TypeError,ValueError,OverflowError):repaired=True
    return result,repaired

def portable(state):
    # An allowlist, never a blacklist: provider status, credentials and sessions cannot escape.
    settings={k:copy.deepcopy(state['settings'].get(k,v)) for k,v in defaults().items()}
    for key in ('final_folder','print_profile','restore_location','hypir_location','osediff_location','flowsr_location','seesr_location'): settings.pop(key,None)
    return dict(format='clarette-preferences',version=1,settings=settings,
                workspaces=copy.deepcopy(state.get('workspaces',WORKSPACES)),
                presets=copy.deepcopy(state['presets']),shortcuts=copy.deepcopy(state.get('shortcuts',{})))
