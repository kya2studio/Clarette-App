#!/usr/bin/env python3
"""Clarette. Local-only HTTP service and optional native macOS window."""
from functools import lru_cache
import tempfile
from image_worker import ImageWorker, Cancelled
ENGINE=ImageWorker()
import argparse, base64, copy, hashlib, io, json, math, mimetypes, os, platform, secrets, shutil, socket, subprocess, sys, threading, time, traceback, urllib.parse, uuid, webbrowser, zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PIL import Image
import imaging
from guides import guide_for, validate_guide, fit_face, preset_key
ROOT=Path(__file__).resolve().parent
WEB_ROOT=(ROOT/'web').resolve()
from support import support_dir
DATA=support_dir()
DATA.mkdir(parents=True,exist_ok=True)
MODELS=Path(os.environ.get('CLARETTE_MODELS',str(DATA/'models'))).expanduser();STATE=DATA/'session.json';TOKEN=secrets.token_urlsafe(32)
LOCK=threading.RLock();JOBS={};WINDOW=None;SERVER=None;PENDING_UPDATE=None
from release import VERSION, BUILD
import preferences, storage, actions
CACHE=storage.cache_dir(DATA)
PRESETS=copy.deepcopy(preferences.BUILTINS)
PROMPT='Enhance this headshot conservatively. Preserve the exact identity, facial proportions, expression, age, skin texture, hairline, hairstyle, clothing, hats and accessories. Improve clarity and compression artifacts without inventing facial details, teeth or eyes. If the source is small, upscale it before gentle enhancement. Keep the composition and aspect ratio unchanged. Do not beautify, change features, crop or remove the background. Return one high-resolution image.'

def fresh():return dict(version=VERSION,build=BUILD,active=None,batches={},settings=preferences.defaults(),presets=copy.deepcopy(PRESETS),workspace2=preferences.default_workspace2(),shortcuts={})

def _backup_session():
    if not STATE.is_file():return False,None
    target=STATE.with_name('session-recovery-'+str(time.time_ns())+'.json')
    try:shutil.copy2(STATE,target);return True,target
    except OSError:
        # A rename needs no duplicate disk allocation and still preserves the bytes.
        try:STATE.replace(target);return True,target
        except OSError:return False,None

def _safe_component(value):
    return isinstance(value,str) and 0<len(value)<=128 and Path(value).name==value and value not in ('.','..') and not any(ord(c)<32 for c in value)

def _safe_relative(value):
    if not isinstance(value,str) or not value or '\\' in value:return False
    path=Path(value)
    return not path.is_absolute() and all(part not in ('','.','..') for part in path.parts)

def _transform(value):
    if not isinstance(value,dict):return None
    try:
        result={key:float(value[key]) for key in ('scale','x','y')};result['rotation']=float(value.get('rotation',0))
    except (KeyError,TypeError,ValueError,OverflowError):return None
    if not all(math.isfinite(v) for v in result.values()) or not .001<=result['scale']<=100:return None
    if 'rotation' not in value:result.pop('rotation')
    return result

def _snapshot_record(value):
    if not isinstance(value,dict) or not _safe_relative(value.get('work')):return None
    try:
        width,height=value['width'],value['height']
        if any(type(v) is not int for v in (width,height)) or width<1 or height<1 or width*height>imaging.MAX_PIXELS:raise ValueError()
        color=imaging.settings(value['color']);draft=imaging.settings(value.get('draft',color));transform=_transform(value['transform'])
        if transform is None:raise ValueError()
    except (KeyError,TypeError,ValueError,OverflowError):return None
    result=copy.deepcopy(value);result.update(color=color,draft=draft,transform=transform)
    for key in ('mask','baseline','stable_work','mask_review_work'):
        if result.get(key) is not None and not _safe_relative(result[key]):result[key]=None
    result['mask_applied']=bool(result.get('mask_applied') and result.get('mask'))
    return result

def _file_record(value,batch_id,canvas):
    if not isinstance(value,dict) or not _safe_component(value.get('id')):return None,True
    if not _safe_relative(value.get('work')) or not _safe_relative(value.get('original')):return None,True
    try:
        width,height=value['width'],value['height']
        if any(type(v) is not int for v in (width,height)) or width<1 or height<1 or width*height>imaging.MAX_PIXELS:raise ValueError()
    except (KeyError,TypeError,ValueError,OverflowError):return None,True
    result=copy.deepcopy(value);repaired=False;result['batch']=batch_id
    if value.get('batch')!=batch_id:repaired=True
    name=result.get('name')
    if not isinstance(name,str) or not name or len(name)>1024 or any(ord(c)<32 for c in name):return None,True
    transform=_transform(result.get('transform'))
    if transform is None:
        scale=min(canvas['width']/width,canvas['height']/height);transform=dict(scale=scale,x=(canvas['width']-width*scale)/2,y=(canvas['height']-height*scale)/2);repaired=True
    result['transform']=transform
    try:result['color']=imaging.settings(result.get('color',{}))
    except (TypeError,ValueError,OverflowError):result['color']=imaging.color_defaults();repaired=True
    try:result['draft']=imaging.settings(result.get('draft',result['color']))
    except (TypeError,ValueError,OverflowError):result['draft']=copy.deepcopy(result['color']);repaired=True
    if result.get('mask') is not None and not _safe_relative(result['mask']):result['mask']=None;repaired=True
    result['mask_applied']=bool(result.get('mask_applied') and result.get('mask'))
    for key in ('baseline','stable_work','mask_review_work'):
        if result.get(key) is not None and not _safe_relative(result[key]):result.pop(key,None);repaired=True
    result.setdefault('baseline',result['original'])
    original_size=result.get('original_size')
    if not isinstance(original_size,list) or len(original_size)!=2 or any(type(v) is not int or v<1 for v in original_size):result['original_size']=[width,height];repaired=True
    region=result.get('original_region')
    if not isinstance(region,list) or len(region)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in region) or region[2]<=0 or region[3]<=0:result['original_region']=[0,0,width,height];repaired=True
    if type(result.get('revision')) is not int or result['revision']<1:result['revision']=1;repaired=True
    for key in ('history','redo'):
        entries=result.get(key,[])
        if not isinstance(entries,list):entries=[];repaired=True
        clean=[item for entry in entries if (item:=_snapshot_record(entry)) is not None][-20:]
        if len(clean)!=len(entries):repaired=True
        result[key]=clean
    comparisons=result.get('comparisons',{})
    if isinstance(comparisons,dict):
        clean={key:item for key,value in comparisons.items() if isinstance(key,str) and (item:=_snapshot_record(value)) is not None}
        if len(clean)!=len(comparisons):repaired=True
        result['comparisons']=clean
    else:result['comparisons']={};repaired=True
    exported=result.get('export')
    if exported is not None and (not isinstance(exported,dict) or not isinstance(exported.get('path'),str) or type(exported.get('revision')) is not int or not isinstance(exported.get('sha256'),str)):
        result['export']=None;repaired=True
    return result,repaired

def _batch_record(batch_id,value):
    if not _safe_component(batch_id) or not isinstance(value,dict):return None,True
    canvas,canvas_repaired=preferences.recover_preset(value.get('canvas'),imaging.MAX_PIXELS)
    if canvas is None or not isinstance(value.get('files'),list):return None,True
    result=copy.deepcopy(value);repaired=canvas_repaired;result['id']=batch_id;result['canvas']=canvas
    if value.get('id')!=batch_id:repaired=True
    name=result.get('name')
    if not isinstance(name,str) or not name.strip() or len(name)>120:name='Recovered batch';repaired=True
    result['name']=name.strip();subfolder=result.get('subfolder',result['name'])
    if not isinstance(subfolder,str) or not subfolder.strip() or subfolder in ('.','..') or any(c in subfolder for c in '/\\:') or any(ord(c)<32 for c in subfolder):subfolder=result['name'];repaired=True
    result['subfolder']=subfolder
    files=[]
    for item in value['files']:
        record,changed=_file_record(item,batch_id,canvas);repaired|=changed
        if record is not None:files.append(record)
    result['files']=files
    if result.get('color_mode','RGB') not in ('RGB','CMYK'):result['color_mode']='RGB';repaired=True
    else:result.setdefault('color_mode','RGB')
    if 'output_folder' in result and not isinstance(result['output_folder'],str):result.pop('output_folder');repaired=True
    removed=[]
    entries=result.get('removed_files',[])
    if not isinstance(entries,list):entries=[];repaired=True
    for entry in entries:
        if not isinstance(entry,dict):repaired=True;continue
        record,changed=_file_record(entry.get('file'),batch_id,canvas);repaired|=changed
        if record is None:continue
        index=entry.get('index');removed_at=entry.get('removed_at')
        if type(index) is not int or index<0 or type(removed_at) not in (int,float) or not math.isfinite(removed_at):repaired=True;continue
        removed.append(dict(file=record,index=index,removed_at=removed_at))
    result['removed_files']=removed
    ids={item['id'] for item in files}
    if result.get('selected_id') not in ids:result.pop('selected_id',None)
    if 'closed_at' in result and (type(result['closed_at']) not in (int,float) or not math.isfinite(result['closed_at'])):result.pop('closed_at');repaired=True
    return result,repaired

def _recover_session(value):
    state=fresh();repaired=not isinstance(value,dict)
    if not isinstance(value,dict):return state,True
    state['settings'],changed=preferences.recover_settings(value.get('settings'));repaired|=changed
    if not state['settings'].get('final_folder'):state['settings']['final_folder']=preferences.defaults()['final_folder'];repaired=True
    presets={}
    raw_presets=value.get('presets',{})
    if isinstance(raw_presets,dict):
        for key,item in raw_presets.items():
            preset,changed=preferences.recover_preset(item,imaging.MAX_PIXELS);repaired|=changed
            if _safe_component(key) and preset is not None:presets[key]=preset
            else:repaired=True
    else:repaired=True
    state['presets']={**presets,**copy.deepcopy(PRESETS)}
    batches={};raw_batches=value.get('batches',{})
    if isinstance(raw_batches,dict):
        for key,item in raw_batches.items():
            batch,changed=_batch_record(key,item);repaired|=changed
            if batch is not None:batches[key]=batch
    else:repaired=True
    state['batches']=batches;active=value.get('active');active_valid=isinstance(active,str) and active in batches;state['active']=active if active_valid else None
    if active is not None and not active_valid:repaired=True
    state['workspace2'],changed=preferences.recover_workspace2(value.get('workspace2'));repaired|=changed
    raw_shortcuts=value.get('shortcuts',{})
    try:
        from shortcuts import validate
        validate(raw_shortcuts);state['shortcuts']=copy.deepcopy(raw_shortcuts)
    except (TypeError,ValueError):repaired=True
    return state,repaired

SESSION_RECOVERY_PENDING=False;RECOVERY_NOTICE=None
if STATE.exists():
    try:
        raw_state=json.loads(STATE.read_text());S,repaired=_recover_session(raw_state)
        if repaired:
            backed_up,recovery_path=_backup_session();SESSION_RECOVERY_PENDING=not backed_up
            RECOVERY_NOTICE='Clarette repaired the saved session.'+(' The original is at '+str(recovery_path)+'.' if recovery_path else ' The original could not be backed up, so session saves are paused.')
    except Exception:
        backed_up,recovery_path=_backup_session();SESSION_RECOVERY_PENDING=not backed_up;S=fresh()
        RECOVERY_NOTICE='Clarette recovered from an unreadable saved session.'+(' The original is at '+str(recovery_path)+'.' if recovery_path else ' The original could not be backed up, so session saves are paused.')
else:S=fresh()

S['version']=VERSION;S['build']=BUILD
if RECOVERY_NOTICE:S['recovery_notice']=RECOVERY_NOTICE
for existing_batch in S['batches'].values():
    c=existing_batch['canvas']
    if not c.get('preset_id'):
        c['preset_id']=next((key for key,p in S['presets'].items() if p.get('label')==c.get('label') and p['width']==c['width'] and p['height']==c['height']),f"custom:{c['width']}x{c['height']}")

def save():
    global SESSION_RECOVERY_PENDING
    # Commit references first: a crash may leave extra files, never dangling history.
    if SESSION_RECOVERY_PENDING:
        backed_up,_=_backup_session()
        if not backed_up:return False
        SESSION_RECOVERY_PENDING=False
    tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps(S,indent=2));tmp.replace(STATE)
    for b in S['batches'].values():
        for f in b['files']:storage.prune_item(folder(f),f)
    return True

def ident():return uuid.uuid4().hex[:16]
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def atomic(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name('.'+p.name+'.'+ident()+'.tmp');t.write_bytes(data);t.replace(p)
def folder(f):return CACHE/'batches'/f['batch']/'items'/f['id']
def source(f):return imaging.load(folder(f)/f['work'])
def mask_review_path(f):
    # Legacy detections already retain their uncorrected working image here.
    previous=(f.get('comparisons') or {}).get('refinement') or {}
    name=f.get('mask_review_work') or previous.get('mask_review_work') or previous.get('work')
    if not _safe_relative(name) or not (folder(f)/name).is_file():return None
    with Image.open(folder(f)/name) as image:
        if image.size!=(f['width'],f['height']):return None
    return name

def mask(f):return Image.open(folder(f)/f['mask']).convert('L') if f.get('mask') else None

def getfile(data):
    bid=data.get('batch') or S['active'];batch=S['batches'].get(bid)
    if not batch:raise ValueError('Choose or import a batch first')
    f=next((f for f in batch['files'] if f['id']==data.get('id')),None)
    if not f:raise ValueError('Image not found')
    return batch,f

def snapshot(f):
    return {k:copy.deepcopy(f.get(k)) for k in ('work','mask','mask_applied','color','draft','transform','width','height','comparisons','crop_suggestion','original_region','baseline','stable_work','mask_review_work')}

def snap(f):
    f.setdefault('history',[]).append(snapshot(f));f['history']=f['history'][-20:];f['redo']=[]

def touch(f):f['revision']=f.get('revision',0)+1;f['changed']=time.time()

def dirty(f):return f.get('draft',f['color'])!=f['color']
def saved(f):
    e=f.get('export');return bool(e and e.get('revision')==f['revision'] and not dirty(f) and Path(e['path']).is_file())

def watch(f):
    p=folder(f)/f['work']
    if not p.exists():return
    stamp=p.stat().st_mtime_ns
    if stamp!=f.get('work_stamp'):
        # The editor writes a separate exchange file; stable_work remains immutable for Undo.
        im=imaging.load(p);oldw,oldh=f['width'],f['height']
        stable=f.get('stable_work')
        if stable and (folder(f)/stable).is_file():
            incoming=im.copy();atomic(p,(folder(f)/stable).read_bytes());commit_work(f,incoming,preserve_mask=False)
        else: commit_work(f,im,preserve_mask=False)
        baseline='BASELINE/'+ident()+'.png';atomic(folder(f)/baseline,imaging.png(im));f['baseline']=baseline
        f['original_region']=[0,0,im.width,im.height]
        f['work_stamp']=p.stat().st_mtime_ns;touch(f);save()

def state(settings_only=False):
    with LOCK:
        import photos_bridge
        if not settings_only:photos_bridge.receive_pending(sys.modules[__name__])
        active=S['batches'].get(S['active'])
        if active and not settings_only:
            for f in active['files']:
                try:
                    if not f.get('original_size'):
                        with Image.open(folder(f)/f['original']) as original:
                            size=list(original.size)
                            if original.getexif().get(274) in (5,6,7,8):size.reverse()
                            f['original_size']=size
                    watch(f);f.pop('external_error',None)
                except Exception:f['external_error']='Working file cannot be read yet. Finish saving it in Photoshop.'
        if settings_only:
            out=copy.deepcopy({k:v for k,v in S.items() if k!='batches'})
            out['batches']={key:{k:copy.deepcopy(v) for k,v in batch.items() if k not in ('files','removed_files')} for key,batch in S['batches'].items()}
        else:out=copy.deepcopy(S)
        out['token']=TOKEN;out['platform']=platform.system();out['native']=bool(WINDOW);out['prompt']=S['settings'].get('enhancement_prompt') or PROMPT
        for batch in out['batches'].values():
            for f in batch.get('files',[]):
                f['saved']=saved(f);f['pending_color']=dirty(f);f['can_undo']=bool(f.get('history'));f['can_redo']=bool(f.get('redo'));f.pop('history',None);f.pop('redo',None)
        from providers import restore_status,bundled_restoration_status
        from shortcuts import DEFAULTS
        restore_location=S['settings'].get('restore_location','')
        out['restore']=restore_status(restore_location) if restore_location else bundled_restoration_status();out['shortcut_defaults']=DEFAULTS
        from optional_engines import statuses
        import cloud
        out['provider_models']=copy.deepcopy(cloud.COMPATIBLE);out['engines']=statuses(S['settings'],MODELS);out['hypir_available']=out['engines']['hypir']['status']=='Ready'
        import native
        out['external_apps']=native.available_apps()
        import license
        out['licensed']=license.status(S['settings'])
        out['jobs']=list(copy.deepcopy(JOBS).values());out['pending_update']=copy.deepcopy(PENDING_UPDATE);return out

def notify(message):
    if platform.system()!='Darwin' or not WINDOW:return
    from notifications import send
    try:
        if S['settings'].get('notifications'):send(message,sound=False)
    except Exception:traceback.print_exc()

def start_job(title,fn):
    with LOCK:
        if ENGINE.stop_requested.is_set():raise ValueError('Clarette is closing')
        if any(j['status']=='running' for j in JOBS.values()):raise ValueError('Wait for the current operation to finish')
        jid=ident();job=dict(id=jid,title=title,message='Starting…',status='running',started=time.time(),cancel_requested=False);JOBS[jid]=job
        for old in list(JOBS)[:-30]: JOBS.pop(old,None)
    def check():
        if job.get('cancel_requested'):raise Cancelled('Processing cancelled. Previous edits are preserved.')
    def report(message):
        check()
        with LOCK:job['message']=message
    report.check=check
    def run():
        try:
            result=fn(report)
            with LOCK:job.update(status='done',message='Complete',result=result,elapsed=round(time.time()-job['started'],3));save()
            notify(title+' complete')
        except Cancelled as e:
            with LOCK:job.update(status='cancelled',message=str(e));save()
        except Exception as e:
            traceback.print_exc()
            with LOCK:job.update(status='error',message=str(e)[:700]);save()
            notify(title+' needs attention')
    threading.Thread(target=run,daemon=False).start();return {'job':jid}

def safe_name(name):
    name=Path(str(name).replace('\\','/')).name
    if not name or name in ('.','..') or any(ord(c)<32 for c in name):raise ValueError('Invalid filename')
    return name

def import_items(items,label,append=False):
    with LOCK:
        bid=S['active'] if append and S['active'] else ident()
        batch=S['batches'].get(bid) or dict(id=bid,name=label,subfolder=label,canvas=dict(copy.deepcopy(PRESETS['landscape']),preset_id='landscape'),files=[])
        if not batch['files']:
            key=preset_key(batch['canvas'])
            if S['settings'].get('default_guides',{}).get(key):batch['canvas']['guide']=copy.deepcopy(S['settings']['default_guides'][key])
        names={f['name'].lower() for f in batch['files']};stems={Path(f['name']).stem.lower() for f in batch['files']};added=[];skipped=[]
        for name,raw in items:
            name=safe_name(name)
            if name.lower() in names or Path(name).stem.lower() in stems:skipped.append(name+' (duplicate output name)');continue
            try:im=imaging.load(io.BytesIO(raw))
            except Exception as e:skipped.append(name+': '+str(e));continue
            fid=ident();f=dict(id=fid,batch=bid,name=name,work='WORKING/'+Path(name).stem+'.png',original='ORIGINAL/'+name,width=im.width,height=im.height,mask=None,mask_applied=False,color=imaging.color_defaults(),draft=imaging.color_defaults(),revision=1,history=[],export=None)
            s=min(batch['canvas']['width']/im.width,batch['canvas']['height']/im.height);f['transform']=dict(scale=s,x=(batch['canvas']['width']-im.width*s)/2,y=(batch['canvas']['height']-im.height*s)/2);f['original_transform']=copy.deepcopy(f['transform']);f['original_size']=list(im.size);f['original_region']=[0,0,im.width,im.height]
            atomic(folder(f)/f['original'],raw);atomic(folder(f)/f['work'],imaging.png(im));f['work_stamp']=(folder(f)/f['work']).stat().st_mtime_ns
            f['baseline']=f['original'];f['stable_work']='BASELINE/'+ident()+'.png';atomic(folder(f)/f['stable_work'],imaging.png(im))
            batch['files'].append(f);names.add(name.lower());stems.add(Path(name).stem.lower());added.append(fid)
        if not added:raise ValueError('No images imported. '+('; '.join(skipped[:3])))
        S['batches'][bid]=batch;S['active']=bid;save();return dict(added=len(added),skipped=skipped)

def destination(batch):
    base=batch.get('output_folder') or S['settings'].get('final_folder','')
    if not base:raise ValueError('Choose your Final folder before exporting')
    name=batch['subfolder'].strip()
    if not name or name in ('.','..') or any(c in name for c in '/\\:') or any(ord(c)<32 for c in name):raise ValueError('Use one folder name without slashes')
    base=Path(base).expanduser().resolve();out=base/name
    if out.is_symlink():raise ValueError('Choose a regular output folder, not a symbolic link')
    if any(out.resolve()==root or root in out.resolve().parents for root in (DATA,CACHE)):raise ValueError('Final must be outside Clarette temporary storage')
    out.mkdir(parents=True,exist_ok=True);return out

def export_files(ids,overwrite,report,apply_all=False,folder_mode='add'):
    with LOCK:
        live_batch=S['batches'][S['active']]
        targets=[Path(f['name']).stem.casefold() for f in live_batch['files'] if not ids or f['id'] in ids]
        if len(targets)!=len(set(targets)):raise ValueError('Portraits have duplicate output names. Remove the duplicate before exporting.')
        if folder_mode=='replace':
            target=destination(live_batch)
            backup=target.with_name(target.name+' backup '+time.strftime('%Y%m%d-%H%M%S')+'-'+ident()[:4])
            target.rename(backup)

        for f in live_batch['files']:watch(f)
        if apply_all:
            destination(live_batch)
            for f in live_batch['files']:
                if (not ids or f['id'] in ids) and (dirty(f) or (S['settings'].get('masking_enabled',True) and f.get('mask') and not f.get('mask_applied'))):
                    snap(f);f['color']=imaging.settings(f.get('draft',f['color']));f['mask_applied']=bool(f.get('mask')) if S['settings'].get('masking_enabled',True) else f.get('mask_applied',False);touch(f)
            save()
        batch=copy.deepcopy(live_batch);files=[f for f in batch['files'] if not ids or f['id'] in ids];settings=copy.deepcopy(S['settings'])
        # Keep both rendering choices and the default destination stable for the job.
        batch['output_folder']=batch.get('output_folder') or settings.get('final_folder','');out=destination(batch)
    skipped=[]
    if not files:raise ValueError('No images to export')
    results=[];errors=[]
    for index,f in enumerate(files):
        try:
            report(f'Saving {index+1}/{len(files)}: {f["name"]}')
            if dirty(f):raise ValueError('Apply or reset pending color changes first')
            if settings.get('masking_enabled',True) and f.get('mask') and not f.get('mask_applied'):raise ValueError('Apply the cutout or choose Apply pending edits before export')
            with tempfile.TemporaryDirectory(prefix='export-',dir=CACHE) as temp:
                capture=Path(temp);captured_stamp=f.get('work_stamp')
                def current_export_file():
                    live=next((x for x in S['batches'].get(batch['id'],{}).get('files',[]) if x['id']==f['id']),None)
                    if live is None:raise ValueError('Portrait was removed during export')
                    work_path=folder(live)/live['work']
                    try:stamp=work_path.stat().st_mtime_ns
                    except OSError:raise ValueError('Working image changed during export. Review it and export again.') from None
                    if live['revision']!=f['revision'] or live['work']!=f['work'] or stamp!=captured_stamp:
                        raise ValueError('Working image changed during export. Review it and export again.')
                    return live,work_path
                with LOCK:
                    _,work_path=current_export_file();source_path=capture/'source.png';atomic(source_path,work_path.read_bytes())
                    mask_path=None
                    if f.get('mask'):
                        mask_path=capture/'mask.png';atomic(mask_path,(folder(f)/f['mask']).read_bytes())
                    original_path=capture/'original';atomic(original_path,(folder(f)/f['original']).read_bytes())
                    current_export_file()
                captured_source=imaging.load(source_path);captured_mask=Image.open(mask_path).convert('L') if mask_path else None
                import exporting
                opts=batch.get('export_options',{});color_mode=batch.get('color_mode','RGB')
                masking=settings.get('masking_enabled',True)
                cutout=masking and (bool(f.get('mask_applied')) or captured_source.getchannel('A').getextrema()[0]<255)
                fmt=opts.get('format') or settings['cutout_format' if cutout else 'photo_format']
                if fmt=='default':fmt=settings['cutout_format' if cutout else 'photo_format']
                final=out/(Path(f['name']).stem+{'PNG':'.png','JPEG':'.jpg','TIFF':'.tif'}[fmt])
                if final.is_symlink():raise ValueError('Output file is a symbolic link')
                if final.exists() and not overwrite:raise ValueError('File already exists. Enable Replace existing files to replace it.')
                im=imaging.composite(captured_source,captured_mask if masking else None,f['color'],True);im=imaging.render(im,f['transform'],batch['canvas']);raw=exporting.encode(im,fmt,color_mode,settings,batch['canvas']['dpi'],original_path,flatten=not masking or bool(opts.get('flatten')) or (not cutout and (fmt=='JPEG' or color_mode=='CMYK')),background=opts.get('background','#ffffff'))
                with LOCK:
                    current_export_file();atomic(final,raw)
                with Image.open(final) as check:check.load();assert check.size==(batch['canvas']['width'],batch['canvas']['height'])
                sha=digest(final)
                with LOCK:
                    live,_=current_export_file();live['export']=dict(path=str(final),sha256=sha,revision=f['revision']);save()
            results.append(f['name'])
        except Cancelled:raise
        except Exception as e:errors.append(f['name']+': '+str(e))
    if not results and errors:raise ValueError('; '.join(errors[:5]))
    return dict(saved=results,errors=errors,skipped=skipped,folder=str(out))

def commit_work(f,im,preserve_mask=True):
    oldmask=mask(f) if preserve_mask and f.get('mask') and (folder(f)/f['mask']).is_file() else None
    oldapplied=f.get('mask_applied',False)
    oldw=f['width'];old=folder(f)/f['work'];backup='HISTORY/'+ident()+'.png';atomic(folder(f)/backup,old.read_bytes())
    snap(f);f['history'][-1]['work']=backup
    atomic(old,imaging.png(im));f['width'],f['height']=im.size;f['work_stamp']=old.stat().st_mtime_ns;f['transform']['scale']*=oldw/im.width
    f['comparisons']={};f.pop('mask_review_work',None);f.pop('crop_suggestion',None);f['mask']=None;f['mask_applied']=False;f['color']=imaging.color_defaults();f['draft']=imaging.color_defaults();touch(f)
    f['stable_work']='BASELINE/'+ident()+'.png';atomic(folder(f)/f['stable_work'],imaging.png(im))
    if oldmask is not None:
        name='MASKS/'+ident()+'.png';atomic(folder(f)/name,imaging.png(oldmask.resize(im.size,Image.Resampling.LANCZOS)));f['mask']=name;f['mask_applied']=oldapplied
    save()

@lru_cache(maxsize=256)
def thumbnail(path,stamp):
    im=imaging.load(path);im.thumbnail((80,80));return imaging.png(im)

UNLICENSED_ALLOWED=('/api/activate-license','/api/quit','/api/window','/api/close-window','/api/check-updates','/api/print-profiles','/api/storage','/api/buy-license')
def action(path,d):
    if path not in UNLICENSED_ALLOWED:
        import license
        if not license.status(S['settings'])['licensed']:raise ValueError('Activate your Clarette license first.')
    if path=='/api/job-presented':
        with LOCK:
            job=JOBS.get(d.get('job'))
            if not job or job['status'] not in ('done','error') or job.get('presentation_acknowledged'):return {'ok':True}
            job['presentation_acknowledged']=True
            play=bool(WINDOW and S['settings'].get('notification_sound'))
        if play:
            from notifications import play_sound
            threading.Thread(target=play_sound,daemon=True).start()
        return {'ok':True}
    if path in ('/api/mask-detect','/api/mask-paint','/api/mask-apply','/api/refine-edges','/api/apply-cutouts') and not S['settings'].get('masking_enabled',True):raise ValueError('Enable Mask first')
    # Native dialogs/network calls must not hold the image state lock.
    if path in ('/api/choose-path','/api/save-document','/api/provider-models','/api/window','/api/close-window','/api/quit','/api/cancel','/api/storage','/api/check-updates','/api/apply-update'):
        result=actions.handle(sys.modules[__name__],path,d)
    else:
        with LOCK:result=actions.handle(sys.modules[__name__],path,d)
    if result is not actions.UNHANDLED:return result
    if path=='/api/selection':
        with LOCK:
            batch,f=getfile(d);batch['selected_id']=f['id']
        return {'ok':True}
    if path=='/api/voice':
        if not S['settings'].get('voice_commands',False):raise ValueError('Enable Siri & Shortcuts in Clarette Settings first.')
        from voice_actions import command_request
        with LOCK:
            batch=S['batches'].get(S['active'])
            if not batch:raise ValueError('Select a portrait in Clarette first.')
            selected=batch.get('selected_id')
            if not selected:raise ValueError('Select a portrait in Clarette first.')
            target,payload=command_request(d.get('command'),batch['id'],selected)
        return action(target,payload)

    if path=='/api/activate-license':
        import license
        key=d.get('key','').strip();payload=license.verify(key)
        with LOCK:S['settings']['license_key']=key;save()
        return {'ok':True,'email':payload.get('email')}
    if path=='/api/deactivate-license':
        with LOCK:S['settings'].pop('license_key',None);save()
        return {'ok':True}
    if path=='/api/credentials-match':
        from credentials import matches_key
        return {'matches':matches_key(d.get('provider'),d.get('key',''))}
    if path=='/api/credentials':
        from credentials import set_key,delete_key
        provider=d.get('provider')
        if provider not in ('openai','gemini','seedream'):raise ValueError('Unknown provider')
        if d.get('remove'):delete_key(provider)
        else:set_key(provider,d.get('key',''))
        with LOCK:
            S['settings'][provider+'_connected']=not d.get('remove',False);save()
        return {'ok':True}
    if path=='/api/test-connection':
        from cloud import test_connection
        return test_connection(d.get('provider'))
    if path=='/api/clear-batch':
        with LOCK:
            batch=S['batches'][S['active']]
            if any(not saved(f) for f in batch['files']) and not d.get('confirm_unsaved'):raise ValueError('Confirm clearing unsaved portraits')
            if any(j['status']=='running' for j in JOBS.values()):raise ValueError('Wait for processing to finish')
            storage.discard_batch(CACHE,DATA,batch['id'])
            batch['files']=[];batch['removed_files']=[];batch.pop('selected_id',None)
            thumbnail.cache_clear();save()
        return {'ok':True}
    if path=='/api/destination-status':
        with LOCK:
            batch=S['batches'][S['active']];base=batch.get('output_folder') or S['settings'].get('final_folder','')
            name=batch['subfolder'].strip()
            if not base or not name or name in ('.','..') or any(c in name for c in '/\\:'):raise ValueError('Choose a location and valid folder name')
            target=Path(base).expanduser().resolve()/name
            if target.is_symlink():raise ValueError('Choose a regular output folder')
            return {'exists':target.exists(),'path':str(target)}
    if path=='/api/batch-process':
        return start_job('Apply to All',lambda report:process_batch(d,report))
    if path=='/api/cancel':
        with LOCK:
            for job in JOBS.values():
                if job['status']=='running' and job['id']==d.get('job'):
                    job['cancel_requested']=True;job['message']='Stopping safely…'
        return {'ok':True}
    if path=='/api/import':
        payload=[]
        for item in d.get('files',[]):
            raw=base64.b64decode(item['data'],validate=True);name=safe_name(item['name'])
            if name.lower().endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    if sum(x.file_size for x in z.infolist())>500_000_000:raise ValueError('ZIP exceeds 500 MB unpacked')
                    for info in z.infolist():
                        if info.is_dir() or '__MACOSX' in info.filename or Path(info.filename).name.startswith('.'):continue
                        if Path(info.filename).suffix.lower() in ('.jpg','.jpeg','.png','.webp','.tif','.tiff','.bmp'):payload.append((info.filename,z.read(info)))
            else:payload.append((name,raw))
        return import_items(payload,d.get('name') or time.strftime('CLA_%Y-%m-%d'),d.get('append',False))
    if path=='/api/choose-folder':
        if platform.system()!='Darwin':raise ValueError('The folder chooser opens on your Mac. In this remote preview, enter a folder path instead.')
        proc=subprocess.run(['/usr/bin/osascript','-e','POSIX path of (choose folder with prompt "Choose your Clarette Final folder")'],capture_output=True,text=True)
        if proc.returncode:return {'cancelled':True}
        p=proc.stdout.strip()
        with LOCK:S['settings']['final_folder']=p;save()
        return {'path':p}
    if path=='/api/reset-settings':
        if d.get('confirmed') is not True:raise ValueError('Confirm resetting preferences first')
        with LOCK:
            keep={k:copy.deepcopy(v) for k,v in S['settings'].items() if k in ('default_guides','final_folder','openai_connected','gemini_connected','seedream_connected')}
            S['settings']=dict(fresh()['settings'],**keep);save()
        return {'ok':True}
    # /api/settings is handled by actions.py (preferences.validate_settings) --
    # actions.handle() above returns before this if/elif chain is ever
    # reached for that path, so a second block here was unreachable dead
    # code (and, worse, disagreed with the real one: it thought
    # upscale_method:'hypir' was valid, which preferences.validate_settings
    # has never accepted).
    if path=='/api/output-presets-export':
        from output_presets import export_document
        with LOCK:document=export_document(S,d.get('selected_ids'))
        if WINDOW and not d.get('preview'):
            import webview
            chosen=WINDOW.create_file_dialog(webview.FileDialog.SAVE,save_filename='Clarette-output-presets.json',file_types=('JSON files (*.json)',))
            if not chosen:return {'cancelled':True}
            output=Path(chosen[0] if isinstance(chosen,(list,tuple)) else chosen);output.write_text(json.dumps(document,indent=2));return {'saved':True}
        return {'document':document}
    if path in ('/api/output-presets-import','/api/output-presets-preview'):
        from output_presets import validate_document,match_existing
        if len(json.dumps(d.get('document'))) > 262144:raise ValueError('Preset file is too large')
        entries=validate_document(d.get('document'))
        with LOCK:
            plan=[dict(index=i,label=p['label'],width=p['width'],height=p['height'],dpi=p['dpi'],existing_id=match_existing(p,S['presets'])) for i,p in enumerate(entries)]
            if path=='/api/output-presets-preview':return {'entries':plan}
            selected=d.get('selected_indexes',list(range(len(entries))))
            if not isinstance(selected,list) or not selected or any(type(i)!=int or i<0 or i>=len(entries) for i in selected):raise ValueError('Select valid output presets to import')
            selected=list(dict.fromkeys(selected));approved=d.get('replace_existing',[])
            for i in selected:
                if plan[i]['existing_id'] in preferences.BUILTINS:continue
                if plan[i]['existing_id'] and plan[i]['existing_id'] not in approved:raise ValueError('Confirm replacement of '+entries[i]['label']+' before importing')
            for i in selected:
                p=copy.deepcopy(entries[i]);p.pop('import_id',None);key=plan[i]['existing_id'] or ident();
                if key in preferences.BUILTINS:continue
                p['preset_id']=key;S['presets'][key]=p;S['settings'].setdefault('default_guides',{})[key]=copy.deepcopy(p['guide'])
                active=S['batches'].get(S['active'])
                if active and preset_key(active['canvas'])==key:
                    # Replacement changes the preset definition; applying new dimensions is explicit through the selector.
                    if active['canvas']['width']==p['width'] and active['canvas']['height']==p['height']:active['canvas']['guide']=copy.deepcopy(p['guide'])
                    active.setdefault('guide_profiles',{})[key]=copy.deepcopy(p['guide'])
            save()
        return {'imported':len(selected)}
    if path=='/api/guide':
        with LOCK:
            g=validate_guide(d['guide']);batch=S['batches'][S['active']];c=batch['canvas'];key=preset_key(c);c['guide']=g;batch.setdefault('guide_profiles',{})[key]=copy.deepcopy(g)
            if d.get('save_default'):
                S['settings'].setdefault('default_guides',{})[key]=copy.deepcopy(g)
                S['presets'][key]=copy.deepcopy(c)
            save()
        return {'ok':True}
    if path=='/api/notification-test':
        from notifications import send
        return send('Notification test',sound=True)
    if path=='/api/select-batch':
        with LOCK:
            if d['batch'] not in S['batches']:raise ValueError('Batch not found')
            S['active']=d['batch'];S['batches'][d['batch']].pop('closed_at',None);save()
        return {'ok':True}
    if path=='/api/output':
        with LOCK:
            batch=S['batches'][S['active']]
            if 'subfolder' in d:batch['subfolder']=d['subfolder']
            if 'canvas' in d:
                c=d['canvas'];w,h,dpi=int(c['width']),int(c['height']),int(c['dpi'])
                if not 16<=w<=32768 or not 16<=h<=32768 or w*h>imaging.MAX_PIXELS or not 1<=dpi<=1200:raise ValueError('Invalid preset dimensions')
                old=batch['canvas'];c=dict(width=w,height=h,dpi=dpi,headW=float(c.get('headW',.255)),headTop=float(c.get('headTop',.035)),label=c.get('label','Custom'),preset_id=c.get('preset_id') if c.get('preset_id') in S['presets'] else f'custom:{w}x{h}')
                if not .05<=c['headW']<=.95 or not 0<=c['headTop']<=.8:raise ValueError('Invalid head guide')
                profiles=batch.setdefault('guide_profiles',{});oldkey=preset_key(old);newkey=preset_key(c)
                if old.get('guide'):profiles[oldkey]=copy.deepcopy(old['guide'])
                selected_guide=profiles.get(newkey) or S['presets'].get(newkey,{}).get('guide') or S['settings'].get('default_guides',{}).get(newkey)
                if selected_guide:c['guide']=copy.deepcopy(selected_guide)
                batch['canvas']=c
                for f in batch['files']:
                    snap(f);t=f['transform'];k=h/old['height'];t['scale']*=k;t['x']=w/2+(t['x']-old['width']/2)*k;t['y']*=k;touch(f)
            save()
        return {'ok':True}
    if path=='/api/preset':
        with LOCK:
            c=copy.deepcopy(S['batches'][S['active']]['canvas']);c['label']=str(d['label'])[:80];S['presets'][ident()]=c;save()
        return {'ok':True}
    if path=='/api/export-plan':
        with LOCK:
            files=S['batches'][S['active']]['files']
            for f in files:watch(f)
            return dict(eligible=len(files),pending=sum(dirty(f) or bool(f.get('mask') and not f.get('mask_applied')) for f in files),missing=[])
    if path=='/api/apply-cutouts':
        with LOCK:
            count=0
            for f in S['batches'][S['active']]['files']:
                watch(f)
                if f.get('mask') and not f.get('mask_applied'):snap(f);f['mask_applied']=True;touch(f);count+=1
            save();return dict(applied=count)
    if path=='/api/export':
        S['batches'][S['active']]['export_options']={k:d[k] for k in ('format','flatten','background') if k in d}
        return start_job('Export batch',lambda report:export_files(d.get('ids',[]),d.get('overwrite',False),report,d.get('apply_all',False),d.get('folder_mode','add')))
    if path=='/api/clear-saved':
        with LOCK:
            batch=S['batches'][S['active']];removed=[];retained=[]
            for index,f in enumerate(list(batch['files'])):
                try:
                    watch(f)
                    valid=saved(f) and digest(f['export']['path'])==f['export']['sha256']
                except (OSError,ValueError):valid=False
                if valid:
                    batch.setdefault('removed_files',[]).append(dict(file=f,index=index,removed_at=time.time()))
                    batch['files'].remove(f);removed.append(f['name'])
                else:retained.append(f['name'])
            if batch.get('selected_id') not in {f['id'] for f in batch['files']}:
                batch['selected_id']=batch['files'][0]['id'] if batch['files'] else None
            save()
        return dict(removed=removed,retained=retained)
    if path=='/api/open':
        service=d.get('service')
        if service in ('chatgpt','gemini','seedream'):
            url={'chatgpt':'https://chatgpt.com/','gemini':'https://gemini.google.com/','seedream':'https://dreamina.capcut.com/'}[service]
            if not webbrowser.open(url):raise ValueError('Could not open the browser. Open the provider website and use the Prompt button.')
            return dict(ok=True,prompt=S['settings'].get('enhancement_prompt') or PROMPT)
        if platform.system()!='Darwin':raise ValueError('This opens Finder or Photoshop when Clarette is running on your Mac.')
        if service=='final':p=destination(S['batches'][S['active']]);cmd=['open',str(p)]
        else:
            _,f=getfile(d);p=folder(f)/f['work']
            if service in ('photoshop','affinity','photos'):
                import native
                app_name=native.available_apps().get(service)
                if not app_name:raise ValueError('This application is not installed')
                if service not in S['settings']['toolbar_apps']:raise ValueError('Enable this application in Toolbar & Apps first')
                if service=='photos':
                    import photos_bridge
                    with LOCK:
                        photos_batch,photos_portrait=getfile(d)
                        photos_bridge.send(sys.modules[__name__],photos_batch,photos_portrait)
                    return {'ok':True}
                cmd=['open','-a',app_name,str(p)]
            elif service=='working':cmd=['open','-R',str(p)]
            else:raise ValueError('Unknown action')
        subprocess.Popen(cmd);return {'ok':True}
    if path=='/api/quit':
        _quit_app();return {'ok':True}
    if path=='/api/check-updates':
        import updates
        return updates.check()
    if path=='/api/apply-update':
        import updates
        def run(report):
            report('Downloading update…')
            updates.apply(d.get('asset_url'),d.get('asset_name'),report)
            report('Installing… Clarette will restart.')
            _quit_app()
            return {'installing':True}
        return start_job('Update',run)
    with LOCK:
        batch,f=getfile(d)
        if path=='/api/edit':
            if 'position_locked' in d:f['position_locked']=bool(d['position_locked'])
            if 'draft' in d:
                draft=imaging.settings(d['draft'])
                if draft!=f.get('draft'):snap(f);f['draft']=draft
            if 'transform' in d:
                t={k:float(d['transform'][k]) for k in ('scale','x','y')}
                t['rotation']=float(d['transform'].get('rotation',f['transform'].get('rotation',0)))
                if not all(__import__('math').isfinite(v) for v in t.values()) or not .001<=t['scale']<=100:raise ValueError('Invalid position')
                if t!=f['transform'] and f.get('position_locked'):raise ValueError('Unlock the headshot position before changing its placement')
                if t!=f['transform']:snap(f);f['transform']=t;touch(f)
            save();return {'ok':True}
        if path=='/api/color-apply':snap(f);f['history'][-1]['draft']=copy.deepcopy(f['color']);f['color']=imaging.settings(d['color']);f['draft']=copy.deepcopy(f['color']);touch(f);save();return {'ok':True}
        if path=='/api/color-reset':snap(f);f['color']=imaging.color_defaults();f['draft']=copy.deepcopy(f['color']);touch(f);save();return {'color':f['color']}
        if path in ('/api/undo','/api/redo'):
            undo=path=='/api/undo';stack=f.setdefault('history' if undo else 'redo',[])
            if not stack:raise ValueError('Nothing to '+('undo' if undo else 'redo'))
            previous=copy.deepcopy(stack[-1]);current=snapshot(f)
            currentwork=f['work'];oldwork=previous['work']
            if oldwork!=currentwork:
                data=(folder(f)/oldwork).read_bytes()
                backup='HISTORY/'+ident()+'.png';atomic(folder(f)/backup,(folder(f)/currentwork).read_bytes());current['work']=backup
                atomic(folder(f)/currentwork,data);previous['work']=currentwork
            stack.pop();other=f.setdefault('redo' if undo else 'history',[]);other.append(current);del other[:-20]
            f.update(previous);f['work_stamp']=(folder(f)/f['work']).stat().st_mtime_ns;touch(f);save();return {'ok':True}
        if path=='/api/reset-source':commit_work(f,imaging.load(folder(f)/f['original']));f['original_region']=[0,0,*(f.get('original_size') or [f['width'],f['height']])];f.pop('comparisons',None);save();return {'ok':True}
        if path=='/api/replace':
            im=imaging.load(io.BytesIO(base64.b64decode(d['data'],validate=True)))
            compatible=abs(im.width*f['height']-im.height*f['width'])<=max(im.width,im.height)
            had_mask=bool(f.get('mask'));commit_work(f,im,preserve_mask=compatible)
            if had_mask and not compatible:
                f['alignment_note']='Image proportions changed. The previous mask is available in Undo; detect the subject again.';save()
            return {'ok':True}
        if path=='/api/crop':
            import math
            box=[float(x) for x in d['box']]
            if len(box)!=4 or not all(math.isfinite(x) for x in box):raise ValueError('Invalid crop')
            l,t,rr,b=[round(v) for v in box]
            if not (0<=l<rr<=f['width'] and 0<=t<b<=f['height']) or rr-l<16 or b-t<16:raise ValueError('Crop must be inside the image and at least 16 pixels')
            region=f.get('original_region') or [0,0,*(f.get('original_size') or [f['width'],f['height']])];ow,oh=f['width'],f['height']
            newregion=[region[0]+l*region[2]/ow,region[1]+t*region[3]/oh,(rr-l)*region[2]/ow,(b-t)*region[3]/oh]
            oldt=copy.deepcopy(f['transform']);oldcolor=copy.deepcopy(f['color']);olddraft=copy.deepcopy(f.get('draft',f['color']))
            oldmask=mask(f);oldapplied=f.get('mask_applied',False)
            cropped_mask=oldmask.crop((l,t,rr,b)) if oldmask is not None else None
            commit_work(f,source(f).crop((l,t,rr,b)),preserve_mask=False);f['color']=oldcolor;f['draft']=olddraft
            if cropped_mask is not None:
                name='MASKS/'+ident()+'.png';atomic(folder(f)/name,imaging.png(cropped_mask));f['mask']=name;f['mask_applied']=oldapplied
            # Rotation is around the image center. Keep retained source pixels at
            # their existing canvas positions as the crop moves that center.
            nw,nh=rr-l,b-t;dx,dy=(l+rr-ow)/2,(t+b-oh)/2
            angle=math.radians(oldt.get('rotation',0));co,si=math.cos(angle),math.sin(angle);scale=oldt['scale']
            f['transform']=dict(oldt,x=oldt['x']+scale*((ow-nw)/2+co*dx-si*dy),y=oldt['y']+scale*((oh-nh)/2+si*dx+co*dy))
            f['original_region']=newregion;save();return {'ok':True}
        if path=='/api/mask-apply':
            if not f.get('mask'):raise ValueError('Detect or paint a mask first')
            snap(f);f['mask_applied']=True;touch(f);save();return {'ok':True}
        if path in ('/api/enhance','/api/cloud-enhance','/api/refine-edges') and dirty(f):raise ValueError('Apply or reset pending color changes before processing')
        if path=='/api/enhance':
            engine=d.get('enhancement_provider',S['settings'].get('enhancement_provider','classical'))
            if engine not in ('classical','restore','edsr','hypir','osediff','flowsr','seesr'):raise ValueError('Select a local enhancement engine')
            if engine=='edsr' and int(d.get('scale',1)) not in (2,4):raise ValueError('EDSR needs a 2× or 4× upscale factor')
            if engine not in ('classical','edsr'):
                from optional_engines import statuses
                status=statuses(S['settings'],MODELS)[engine]
                if status['status']!='Ready':raise ValueError(status['message'])
        if path=='/api/cloud-enhance':
            import cloud
            cloud.preflight(d.get('provider'),d.get('cloud_model'),d.get('prompt'))
            if not d.get('confirmed_upload'):raise ValueError('Confirm image upload and possible API charges')
        if path=='/api/rotate':
            angle=float(d.get('angle',0))
            if not __import__('math').isfinite(angle) or abs(angle)>360:raise ValueError('Invalid rotation')
            t=copy.deepcopy(f['transform']);t['rotation']=angle;snap(f);f['transform']=t;touch(f);save();return {'ok':True}
        captured=copy.deepcopy(f);bid=batch['id'];canvas=copy.deepcopy(batch['canvas'])
    def current_job_file():
        _,live=getfile(dict(batch=bid,id=captured['id']))
        if live['revision']!=captured['revision'] or (folder(live)/live['work']).stat().st_mtime_ns!=captured['work_stamp']:
            raise ValueError('The Working image changed during processing. Review the new source and run this operation again.')
        return live
    def work(report):
        if path in ('/api/enhance','/api/refine-edges') and dirty(captured):
            raise ValueError('Apply Color before processing this image.')
        if path=='/api/refine-edges' and not captured.get('mask'):raise ValueError('Detect or paint a mask first')
        with tempfile.TemporaryDirectory(prefix='job-',dir=CACHE) as temp:
            reference=source(captured)
            immutable_source=Path(temp)/'source.png';atomic(immutable_source,imaging.png(reference))
            request={**d,'op':path,'source':str(folder(captured)/captured['work']),
                     'mask':str(folder(captured)/captured['mask']) if captured.get('mask') else None,
                     'models':str(MODELS),'output':temp,'color':captured['color'],'method':S['settings'].get('upscale_method','neural'),
                     'restore_location':S['settings'].get('restore_location',''),'engine_location':S['settings'].get(d.get('enhancement_provider','')+'_location',''),'enhancement_provider':d.get('enhancement_provider',S['settings'].get('enhancement_provider','classical')),
                     'quality_cutout':S['settings'].get('quality_cutout',True),'auto_guide':S['settings'].get('auto_guide',True),'model':S['settings']['model'],'accelerate':S['settings'].get('accelerate',False),
                     'face_restore':S['settings'].get('face_restore',False)}
            request['source']=str(immutable_source)
            if path in ('/api/refine-edges','/api/mask-detect') and reference.getchannel('A').getextrema()[0]<255:
                original=imaging.load(folder(captured)/captured['original'])
                region=captured.get('original_region') or [0,0,*original.size]
                x,y,w,h=region
                background=original.crop((x,y,x+w,y+h)).resize(reference.size,Image.Resampling.LANCZOS)
                if background.getchannel('A').getextrema()[0]==255:
                    restored=Image.alpha_composite(background,reference)
                    atomic(immutable_source,imaging.png(restored))
                else:request['transparent_refine']=True
            detection=captured.get('detection')
            if not isinstance(detection,dict):detection={}
            if (path=='/api/mask-detect' and detection.get('stamp')==captured['work_stamp']
                    and detection.get('model')==request['model'] and detection.get('quality')==request['quality_cutout']
                    and _safe_relative(detection.get('mask')) and (folder(captured)/detection['mask']).is_file()):
                report('Restoring cached subject detection…')
                result={'mask':str(folder(captured)/detection['mask'])}
            else:result=ENGINE.call(request,report)
            report.check()
            newmask=Image.open(result['mask']).convert('L') if result.get('mask') else None
            processed=imaging.load(result['work']) if result.get('work') else None
            if path=='/api/cloud-enhance' and processed is not None:
                # A paid result survives any later alignment/edit conflict for manual import.
                paid_copy=folder(captured)/'CLOUD_RETURNS'/(ident()+'.png');atomic(paid_copy,imaging.png(processed))
        report.check()
        if path=='/api/color-auto':
            with LOCK:
                report.check();live=current_job_file();snap(live);live['draft']=result['color'];touch(live);save()
            return {'color':True}
        if path in ('/api/detect','/api/crop-suggest'):
            found=result['faces']
            if not found:raise ValueError('The detector ran but found no face. Use Head Box for this image.')
            if len(found)>1:report('Multiple faces found; fitting the largest face. Check the result.')
            face=found[0];t=fit_face(face,canvas)
            if path=='/api/detect' and captured.get('position_locked'):raise ValueError('Unlock the headshot position before Auto Fit')
            with LOCK:
                report.check();live=current_job_file();snap(live)
                if path=='/api/crop-suggest':
                    live['crop_suggestion']={'face':face,'transform':t,'full_body_likely':face['h']/captured['height']<.22}
                else:live['transform']=t
                touch(live);save()
            return {'faces':len(found),'confidence':face['confidence']}
        elif path in ('/api/mask-detect','/api/mask-paint'):pass
        elif path=='/api/refine-edges':
            if not captured.get('mask'):raise ValueError('Detect or paint a mask first')
            if dirty(captured):raise ValueError('Apply Color before refining edge colors')
            with LOCK:
                report.check();live=current_job_file();review=mask_review_path(live)
                review_image=imaging.color(imaging.load(folder(live)/review) if review else source(live),live['color'])
                commit_work(live,processed)
                review='HISTORY/'+ident()+'.png';atomic(folder(live)/review,imaging.png(review_image));live['mask_review_work']=review
                live['comparisons']=live.get('comparisons') or {};live['comparisons']['refinement']={k:copy.deepcopy(v) for k,v in live['history'][-1].items() if k!='comparisons'}
                name='MASKS/'+ident()+'.png';atomic(folder(live)/name,imaging.png(newmask));live['mask']=name;live['mask_applied']=False;save()
            return {'mask':True}
        elif path in ('/api/enhance','/api/cloud-enhance'):
            if dirty(captured):raise ValueError('Apply or reset pending color changes before enhancement')
            from providers import normalize_result
            result=normalize_result(processed,reference) if path=='/api/cloud-enhance' else processed
            with LOCK:
                report.check()
                try:live=current_job_file()
                except ValueError:
                    if path=='/api/cloud-enhance':raise ValueError('Working source changed. The paid result was saved for Import Enhanced Image at '+str(paid_copy)) from None
                    raise
                oldmask=live.get('mask');oldapplied=live.get('mask_applied');same_size=result.size==(live['width'],live['height']);commit_work(live,result)
                live['comparisons']=live.get('comparisons') or {};live['comparisons']['enhancement']={k:copy.deepcopy(v) for k,v in live['history'][-1].items() if k!='comparisons'}
                save()
                if same_size:live['mask']=oldmask;live['mask_applied']=oldapplied;save()
                if path=='/api/cloud-enhance':
                    live['alignment_note']=result.info.get('alignment');save();paid_copy.unlink(missing_ok=True)
            return {'width':result.width,'height':result.height}
        else:raise ValueError('Unknown operation')
        with LOCK:
            report.check();live=current_job_file()
            review=mask_review_path(live)
            if review:live['mask_review_work']=review
            if path=='/api/mask-detect' and processed is not None:
                review=mask_review_path(live);color=copy.deepcopy(live['color']);draft=copy.deepcopy(live.get('draft',color));commit_work(live,processed);live['color']=color;live['draft']=draft
                live['mask_review_work']=review or live['history'][-1]['work']
                live['comparisons']['refinement']={k:copy.deepcopy(v) for k,v in live['history'][-1].items() if k!='comparisons'}
            else:snap(live)
            if path=='/api/mask-paint' and captured.get('mask'):
                previous={k:copy.deepcopy(v) for k,v in live['history'][-1].items() if k!='comparisons'};previous['work']='HISTORY/'+ident()+'.png';atomic(folder(live)/previous['work'],(folder(live)/live['work']).read_bytes());live['comparisons']=live.get('comparisons') or {};live['comparisons']['refinement']=previous
            if path=='/api/mask-detect' and result.get('faces') and result['faces'][0]['h']/captured['height']<.22:
                live['crop_suggestion']={'face':result['faces'][0],'full_body_likely':True}
            name='MASKS/'+ident()+'.png';atomic(folder(live)/name,imaging.png(newmask));live['mask']=name;live['mask_applied']=False
            if path=='/api/mask-detect':live['detection']={'stamp':live['work_stamp'],'model':request['model'],'quality':request['quality_cutout'],'mask':name}
            touch(live);save()
        return {'mask':True}
    return start_job({'/api/detect':'Auto Fit','/api/crop-suggest':'Suggest headshot','/api/mask-detect':'Detect subject','/api/mask-paint':'Refine mask','/api/enhance':'Enhance detail','/api/refine-edges':'Refine edges','/api/color-auto':'Auto Color','/api/cloud-enhance':'Cloud enhancement'}.get(path,'Process image'),work)


def process_batch(options,report):
    enabled=[op for op in ('color','enhance','cutout') if options.get(op)]
    if not enabled:raise ValueError('Choose at least one operation')
    with LOCK:
        bid=S['active'];files=copy.deepcopy(S['batches'][bid]['files']);settings=copy.deepcopy(S['settings']);options=copy.deepcopy(options)
    engine=options.get('enhancement_provider',settings.get('enhancement_provider','classical'))
    scale=int(options.get('scale',1))
    if 'enhance' in enabled:
        if engine not in ('classical','restore','edsr','hypir','osediff','flowsr','seesr'):
            raise ValueError('Apply All supports local enhancement engines only. Use individual cloud enhancement to confirm each upload and possible API charge.')
        if engine=='edsr' and scale not in (2,4):raise ValueError('EDSR needs a 2× or 4× upscale factor')
        if engine not in ('classical','edsr'):
            from optional_engines import statuses
            status=statuses(settings,MODELS)[engine]
            if status['status']!='Ready':raise ValueError(status['message'])
    completed=[];errors=[]
    for index,captured in enumerate(files):
        try:
            report(f"Portrait {index+1}/{len(files)}: {captured['name']}")
            for op in enabled:
                operation={'color':'/api/color-auto','enhance':'/api/enhance','cutout':'/api/mask-detect'}[op]
                with tempfile.TemporaryDirectory(prefix='batch-',dir=CACHE) as temp:
                    with LOCK:
                        report.check();_,live=getfile(dict(batch=bid,id=captured['id']));watch(live);captured=copy.deepcopy(live)
                        immutable_source=Path(temp)/'source.png';atomic(immutable_source,(folder(captured)/captured['work']).read_bytes())
                    request=dict(op=operation,source=str(immutable_source),output=temp,models=str(MODELS),color=captured.get('draft',captured['color']),method=settings.get('upscale_method','neural'),model=settings['model'],accelerate=settings.get('accelerate',False),auto_guide=False,quality_cutout=settings.get('quality_cutout',True),scale=scale,amount=int(options.get('amount',50)),enhancement_provider=engine,engine_location=settings.get(engine+'_location',''),restore_location=settings.get('restore_location',''),face_restore=settings.get('face_restore',False))
                    result=ENGINE.call(request,report);report.check()
                    with LOCK:
                        report.check();_,live=getfile(dict(batch=bid,id=captured['id']))
                        if live['revision']!=captured['revision'] or (folder(live)/live['work']).stat().st_mtime_ns!=captured['work_stamp']:
                            raise ValueError('Image changed during processing. Review the new Working source and run Apply All again.')
                        if op=='color':snap(live);live['color']=result['color'];live['draft']=copy.deepcopy(result['color']);touch(live)
                        elif op=='enhance':
                            oldmask=live.get('mask');oldapplied=live.get('mask_applied');im=imaging.load(result['work']);same=im.size==(live['width'],live['height']);commit_work(live,im)
                            if same:live['mask']=oldmask;live['mask_applied']=oldapplied
                        else:
                            applied_color=imaging.settings(live.get('draft',live['color']))
                            if result.get('work'):commit_work(live,imaging.load(result['work']))
                            else:snap(live)
                            name='MASKS/'+ident()+'.png';atomic(folder(live)/name,Path(result['mask']).read_bytes());live['mask']=name;live['mask_applied']=True;live['color']=applied_color;live['draft']=copy.deepcopy(applied_color);touch(live)
                        save()
            completed.append(captured['name'])
        except Cancelled:raise
        except Exception as e:errors.append(captured['name']+': '+str(e)[:250])
    return dict(completed=completed,errors=errors)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,data,status=200,kind='application/json'):
        if kind=='application/json':data=json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        try:
            parsed=urllib.parse.urlparse(self.path);p=parsed.path;qs={k:v[0] for k,v in urllib.parse.parse_qs(parsed.query).items()}
            # Reject DNS rebinding and cross-origin credential access.
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'):return self.send({'error':'Local access only'},403)
            if p=='/api/state':return self.send(state(settings_only=qs.get('view')=='settings'))
            if p=='/api/ping':return self.send(dict(app='Clarette',version=VERSION))
            if p=='/api/image':
                with LOCK:_,f=getfile(qs);f=copy.deepcopy(f)
                kind=qs.get('kind','work')
                if qs.get('thumb') and kind=='work':
                    path=folder(f)/f['work'];return self.send(thumbnail(str(path),path.stat().st_mtime_ns),kind='image/png')
                if kind in ('enhancement','refinement'):
                    previous=(f.get('comparisons') or {}).get(kind)
                    if not previous:raise ValueError('No comparison snapshot for this operation yet')
                    im=imaging.load(folder(f)/previous['work'])
                    oldmask=Image.open(folder(f)/previous['mask']).convert('L') if previous.get('mask') else None
                    im=imaging.composite(im,oldmask,previous['color'],kind=='refinement')
                elif kind=='mask-review':
                    name=mask_review_path(f);im=imaging.load(folder(f)/name) if name else source(f)
                elif kind=='original':im=imaging.load(folder(f)/f.get('baseline',f['original']))
                elif kind=='first-original':im=imaging.load(folder(f)/f['original'])
                elif kind=='mask':im=mask(f) or Image.new('L',(f['width'],f['height']),0)
                else:im=source(f)
                if kind=='cutout':im=imaging.composite(im,mask(f),f['color'],True)
                elif kind=='applied':im=imaging.color(im,f['color'])
                if qs.get('thumb'):im.thumbnail((80,80))
                return self.send(imaging.png(im),kind='image/png')
            rel='index.html' if p=='/' else p.lstrip('/');file=(WEB_ROOT/rel).resolve()
            if WEB_ROOT not in file.parents or not file.is_file():return self.send({'error':'Not found'},404)
            return self.send(file.read_bytes(),kind=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        except Exception as e:return self.send({'error':str(e)},400)
    def do_POST(self):
        try:
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'):return self.send({'error':'Local access only'},403)
            if self.headers.get('X-Glass-Token')!=TOKEN:return self.send({'error':'Refresh Clarette to reconnect.'},403)
            n=int(self.headers.get('Content-Length','0'))
            if n>150_000_000:raise ValueError('Import is too large. Add smaller batches under 100 MB.')
            d=json.loads(self.rfile.read(n) or b'{}');p=urllib.parse.urlparse(self.path).path
            if p=='/api/quit':return self.send(action(p,d))
            with LOCK:
                if any(j['status']=='running' for j in JOBS.values()) and p not in ('/api/open','/api/cancel','/api/quit','/api/job-presented'):raise ValueError('An operation is running. Please wait before making changes.')
            return self.send(action(p,d))
        except Exception as e:
            traceback.print_exc();return self.send({'error':str(e)},400)

def _check_update_later():
    # A few seconds after launch, not blocking startup; only in the packaged
    # build (a dev checkout has no bundle for the frontend's "install" flow
    # to replace anyway). Silent about failures -- a flaky network check
    # should never surface as an error the user didn't ask for.
    global PENDING_UPDATE
    import updates
    if not updates.is_packaged():return
    time.sleep(3)
    try:
        result=updates.check()
        if result.get('available'):PENDING_UPDATE=result
    except Exception:traceback.print_exc()

def _quit_app():
    request_shutdown()
    if WINDOW:threading.Thread(target=WINDOW.destroy,daemon=True).start()
    elif SERVER:threading.Thread(target=SERVER.shutdown,daemon=True).start()

def request_shutdown():
    # Cancellation is signalled without waiting for a busy image operation's lock.
    ENGINE.stop_requested.set()
    for job in list(JOBS.values()):
        if job['status']=='running':job['cancel_requested']=True
    threading.Thread(target=ENGINE.close,daemon=False).start()

class ReuseServer(ThreadingHTTPServer):
    allow_reuse_address=True
    daemon_threads=True
    block_on_close=False

def main():
    global SERVER,WINDOW
    a=argparse.ArgumentParser();a.add_argument('--host',default='127.0.0.1');a.add_argument('--port',type=int,default=int(os.environ.get('CLARETTE_PORT','8767')));a.add_argument('--strictPort',action='store_true');a.add_argument('--native',action='store_true');a.add_argument('--no-browser',action='store_true');args=a.parse_args()
    # Hold a process lock for the session lifetime to prevent concurrent state writers.
    import fcntl
    instance_lock=(DATA/'instance.lock').open('a')
    try:fcntl.flock(instance_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('Clarette is already running. Switch to its existing window.')
    storage.migrate(DATA,CACHE,S)
    storage.clean(CACHE,S)
    save()
    SERVER=ReuseServer((args.host,args.port),Handler);url=f'http://127.0.0.1:{args.port}'
    from voice_actions import publish_connection
    publish_connection(DATA,url,TOKEN)
    threading.Thread(target=_check_update_later,daemon=True).start()
    if args.native:
        import webview
        threading.Thread(target=SERVER.serve_forever,daemon=True).start()
        geometry={}
        try:
            geometry=json.loads((DATA/'window.json').read_text())
            geometry={k:max(low,min(10000,int(geometry[k]))) for k,low in (('width',1100),('height',740))}
        except (OSError,ValueError,TypeError,KeyError):geometry={'width':1500,'height':1000}
        WINDOW=webview.create_window('Clarette · Headshot Workflow',url,width=geometry['width'],height=geometry['height'],min_size=(1100,740),background_color='#17191f',confirm_close=False)
        def resized(width,height):
            geometry.update(width=width,height=height)
        WINDOW.events.resized+=resized
        def closing():
            try:atomic(DATA/'window.json',json.dumps(geometry).encode())
            except (OSError,TypeError):pass
            # Never open nested native dialogs while Cocoa is closing the window.
            request_shutdown()
            import native
            native.close_auxiliary_windows()
            return True
        WINDOW.events.closing+=closing
        WINDOW.events.closed+=request_shutdown
        try:
            import native
            webview.start(lambda:native.install(sys.modules[__name__],url),private_mode=False,storage_path=str(CACHE/'webview'))
        finally:
            request_shutdown();SERVER.shutdown();SERVER.server_close();ENGINE.shutdown()

    else:
        if not args.no_browser:webbrowser.open(url)
        print('Clarette',VERSION,'port',args.port,flush=True)
        try:SERVER.serve_forever()
        finally:request_shutdown();SERVER.server_close();ENGINE.shutdown()
if __name__=='__main__':
    if '--image-worker' in sys.argv:
        from image_worker import worker_main
        worker_main()
    else:main()
