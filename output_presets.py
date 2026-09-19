"""Portable, versioned output dimensions with size-specific face guides."""
import copy,math
from guides import validate_guide,guide_for,preset_key

def export_document(state,selected_ids=None):
    batch=state['batches'].get(state.get('active'),{});current=batch.get('canvas');profiles=state['settings'].get('default_guides',{})
    presets={key:dict(copy.deepcopy(p),preset_id=key) for key,p in state['presets'].items()}
    if current and preset_key(current) not in presets:presets[preset_key(current)]=copy.deepcopy(current)
    entries=[]
    for key,p in presets.items():
        if selected_ids is not None and key not in selected_ids:continue
        g=p.get('guide') or profiles.get(key) or guide_for(p)
        if current and current.get('guide') and key==preset_key(current):g=current['guide']
        entries.append(dict(id=key,label=p.get('label','Custom'),width=p['width'],height=p['height'],dpi=p['dpi'],guide=copy.deepcopy(g)))
    if not entries:raise ValueError('Select at least one output preset to export')
    return {'format':'clarette-output-presets','version':1,'presets':entries}

def match_existing(entry,presets):
    identity=entry.get('import_id')
    if identity in presets:return identity
    return next((key for key,p in presets.items() if p.get('label','').strip().casefold()==entry['label'].strip().casefold()),None)

def validate_document(value):
    if not isinstance(value,dict) or value.get('format')!='clarette-output-presets' or value.get('version')!=1:raise ValueError('Choose a Clarette output presets JSON file (version 1)')
    entries=value.get('presets')
    if not isinstance(entries,list) or not 1<=len(entries)<=100:raise ValueError('Preset file must contain 1 to 100 output sizes')
    result=[]
    for p in entries:
        try:
            if not isinstance(p,dict):raise ValueError()
            w,h,dpi=(p[k] for k in ('width','height','dpi'))
            if any(type(v)!=int for v in (w,h,dpi)) or not 16<=w<=32768 or not 16<=h<=32768 or w*h>__import__('imaging').MAX_PIXELS or not 1<=dpi<=1200:raise ValueError()
            label=p.get('label','Custom')
            if not isinstance(label,str) or not label.strip() or len(label)>100:raise ValueError()
            g=validate_guide(p['guide']);identity=p.get('id');identity=identity if isinstance(identity,str) and len(identity)<=100 else None
            result.append(dict(import_id=identity,label=label.strip(),width=w,height=h,dpi=dpi,headW=g['width'],headTop=g['top'],guide=g))
        except (KeyError,TypeError,ValueError,OverflowError):raise ValueError('Invalid output size, DPI or face guide in the preset file') from None
    return result
