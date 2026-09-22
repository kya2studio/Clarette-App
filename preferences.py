"""Validated preferences, portable workspaces and protected output presets."""
import copy
import json
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
PANELS = ['portraits', 'preview', 'outputSize', 'color', 'detailMask']
# Dockview-based workspace (schema 2). Layouts are opaque `DockviewApi.toJSON()`
# blobs built and interpreted entirely on the frontend (see web/dockview-workspace.js);
# Python only guards their shape/size and which panel ids they may reference. The five
# built-in presets are *not* stored here -- they're computed from code in JS -- so they
# stay protected simply by never being persisted; a live edit while one is active forks
# it into a new `custom` entry instead of mutating the preset.
WORKSPACE_PRESETS = ['landscape', 'portrait']
MAX_LAYOUT_BYTES = 200_000

def defaults():
    return dict(final_folder=str(Path.home()/'Documents/Clarette/Final Output'), model='birefnet-general',
                quality_cutout=True, notifications=True, notification_sound=False, voice_commands=False, show_panel_names=True,
                upscale_method='fast', accelerate=True, auto_guide=True, preview_color=True, face_restore=False,
                masking_enabled=True, solid_preview=False, preview_background='#00a84f', checker_brightness=35,
                cutout_format='PNG', photo_format='JPEG', jpeg_quality=95, tiff_compression='tiff_lzw',
                embed_profile=True, metadata_mode='preserve', processing_metadata=False, print_profile='',
                enhancement_prompt='', restore_location='', hypir_location='', osediff_location='', flowsr_location='', seesr_location='', enhancement_provider='classical', toolbar_apps=['photoshop'], toolbar_tools=['chatgpt','gemini','prompt'],
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
    for key,options in {'model':['birefnet-general','birefnet-portrait','u2netp'],
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
    if not isinstance(result['toolbar_tools'],list) or any(x not in ('chatgpt','gemini','prompt') for x in result['toolbar_tools']): raise ValueError('Invalid toolbar tool')
    if not isinstance(result['toolbar_apps'],list) or any(x not in ('photoshop','affinity','photos') for x in result['toolbar_apps']): raise ValueError('Invalid external application')
    return result

def validate_dockview_layout(value):
    """A shallow, defensive check of a `DockviewApi.toJSON()` blob.

    This never has to be an exhaustive schema for dockview's internal grid
    tree -- the frontend wraps `fromJSON()` in its own try/catch and falls
    back to the default preset on any exception. This just bounds payload
    size and confirms every referenced panel id is one Clarette still knows
    about, so a stale/edited session.json can't reference removed panels or
    balloon storage.
    """
    if not isinstance(value,dict): raise ValueError('Invalid workspace layout')
    if len(json.dumps(value))>MAX_LAYOUT_BYTES: raise ValueError('Workspace layout is too large')
    grid=value.get('grid')
    if not isinstance(grid,dict) or not isinstance(grid.get('root'),dict): raise ValueError('Invalid workspace layout grid')
    panels=value.get('panels')
    if not isinstance(panels,dict): raise ValueError('Invalid workspace layout panels')
    for panel_id in panels:
        if panel_id not in PANELS: raise ValueError('Unknown panel: '+str(panel_id))
    return copy.deepcopy(value)

def default_workspace2():
    return dict(schema=2,active='landscape',locked=False,custom={})

def validate_workspace2(value):
    """Strict validation: raises if `value` itself isn't a well-formed workspace record."""
    if not isinstance(value,dict): raise ValueError('Workspace must be an object')
    custom={}
    raw_custom=value.get('custom',{})
    if not isinstance(raw_custom,dict): raise ValueError('Invalid custom workspaces')
    for key,item in raw_custom.items():
        if not isinstance(key,str) or not key or len(key)>100 or key in WORKSPACE_PRESETS: raise ValueError('Invalid workspace id')
        if not isinstance(item,dict): raise ValueError('Invalid workspace record')
        name=str(item.get('name','')).strip()
        if not name or len(name)>80: raise ValueError('Enter a workspace name under 80 characters')
        layout=validate_dockview_layout(item.get('layout'))
        based_on=item.get('basedOn')
        if based_on is not None and based_on not in WORKSPACE_PRESETS: based_on=None
        custom[key]=dict(name=name,layout=layout,basedOn=based_on,explicit=bool(item.get("explicit",False)))
    active=value.get('active')
    if not isinstance(active,str) or (active not in WORKSPACE_PRESETS and active not in custom): raise ValueError('Invalid active workspace')
    return migrate_workspace_autosaves(dict(schema=2,active=active,locked=bool(value.get('locked',False)),custom=custom,autosaved=validate_autosaved(value.get('autosaved',{}))))

def recover_workspace2(value):
    """Preserve valid customized workspace layouts; fall back to the default preset otherwise.

    Unlike `validate_workspace2`, this tolerates and drops individually-invalid
    custom entries (a corrupted/edited session.json) rather than discarding the
    whole record, matching `recover_settings`/`recover_preset`'s "keep what's
    still valid" behaviour.
    """
    if value is None: return default_workspace2(),False
    if not isinstance(value,dict): return default_workspace2(),True
    repaired=False
    custom={}
    raw_custom=value.get('custom',{})
    if isinstance(raw_custom,dict):
        for key,item in raw_custom.items():
            try:
                if not isinstance(key,str) or not key or len(key)>100 or key in WORKSPACE_PRESETS: raise ValueError()
                if not isinstance(item,dict): raise ValueError()
                name=str(item.get('name','')).strip()
                if not name or len(name)>80: raise ValueError()
                layout=validate_dockview_layout(item.get('layout'))
                based_on=item.get('basedOn')
                if based_on is not None and based_on not in WORKSPACE_PRESETS: based_on=None
                custom[key]=dict(name=name,layout=layout,basedOn=based_on,explicit=bool(item.get("explicit",False)))
            except (TypeError,ValueError,OverflowError): repaired=True
    else: repaired=True
    active=value.get('active')
    if not isinstance(active,str) or (active not in WORKSPACE_PRESETS and active not in custom): active='landscape';repaired=True
    locked=value.get('locked',False)
    if type(locked) is not bool: locked=bool(locked);repaired=True
    try: autosaved=validate_autosaved(value.get('autosaved',{}))
    except (TypeError,ValueError):autosaved={};repaired=True
    return migrate_workspace_autosaves(dict(schema=2,active=active,locked=locked,custom=custom,autosaved=autosaved)),repaired

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

def portable(state):
    # An allowlist, never a blacklist: provider status, credentials and sessions cannot escape.
    settings={k:copy.deepcopy(state['settings'].get(k,v)) for k,v in defaults().items()}
    for key in ('final_folder','print_profile','restore_location','hypir_location','osediff_location','flowsr_location','seesr_location'): settings.pop(key,None)
    return dict(format='clarette-preferences',version=2,settings=settings,
                workspace2=copy.deepcopy(state.get('workspace2',default_workspace2())),
                presets=copy.deepcopy(state['presets']),shortcuts=copy.deepcopy(state.get('shortcuts',{})))


def validate_autosaved(value):
    if not isinstance(value,dict):raise ValueError('Invalid workspace autosave')
    return {key:validate_dockview_layout(layout) for key,layout in value.items() if key in WORKSPACE_PRESETS}

def migrate_workspace_autosaves(ws):
    """Old automatic forks become unnamed resume layouts, never saved menu items."""
    autosaved=ws.setdefault('autosaved',{})
    active=ws['active']
    for key,item in list(ws['custom'].items()):
        if item['name']=='Custom Layout' and item.get('basedOn') and not item.get('explicit'):
            preset=item['basedOn']
            if preset not in autosaved or key==active:autosaved[preset]=item['layout']
            if key==active:ws['active']=preset
            del ws['custom'][key]
    return ws
