"""Version 1 commands, shared by native menus, windows and the main editor."""
import copy
import json
import time
from pathlib import Path
import preferences
import storage
from providers import restore_status

UNHANDLED=object()

def batch_name(value):
    value=str(value).strip()
    if not value or len(value)>120 or value in ('.','..') or any(c in value for c in '/\\:') or any(ord(c)<32 for c in value): raise ValueError('Enter a valid batch name without slashes')
    return value

def new_batch(a,name=None,output=None):
    name=batch_name(time.strftime('CLA_%Y-%m-%d') if name is None else name);base=Path(output or a.S['settings']['final_folder']).expanduser().resolve()
    original=name;i=2
    used={b['subfolder'] for b in a.S['batches'].values() if b.get('output_folder',str(base))==str(base)}
    while (base/name).exists() or name in used: name=f'{original} {i}';i+=1
    bid=a.ident();batch=dict(id=bid,name=name,subfolder=name,output_folder=str(base),canvas=dict(copy.deepcopy(preferences.BUILTINS['landscape']),preset_id='landscape'),files=[],created=time.time(),color_mode='RGB')
    a.S['batches'][bid]=batch;a.S['active']=bid;a.save();return batch

def handle(a,path,d):
    if path in ('/api/remove-portrait','/api/restore-portrait'):
        if any(j['status']=='running' for j in a.JOBS.values()):raise ValueError('Wait for processing to finish')
        batch=a.S['batches'].get(d.get('batch'))
        if not batch:raise ValueError('Batch not found')
        removed=batch.setdefault('removed_files',[])
        if path=='/api/remove-portrait':
            index=next((i for i,f in enumerate(batch['files']) if f['id']==d.get('id')),None)
            if index is None:raise ValueError('Portrait not found')
            f=batch['files'].pop(index);removed.append(dict(file=f,index=index,removed_at=time.time()))
            if batch.get('selected_id')==f['id']:batch['selected_id']=batch['files'][min(index,len(batch['files'])-1)]['id'] if batch['files'] else None
        else:
            if not removed:raise ValueError('No removed portrait to restore')
            entry=removed[-1];f=entry['file']
            if any(Path(other['name']).stem.casefold()==Path(f['name']).stem.casefold() for other in batch['files']):
                raise ValueError('A portrait with this output name is already in the batch. Remove it before restoring this portrait.')
            removed.pop();batch['files'].insert(min(entry['index'],len(batch['files'])),f)
        a.save();return {'ok':True,'id':f['id']}
    if path=='/api/reset-presets':
        if not d.get('confirmed'):raise ValueError('Confirm resetting built-in presets')
        a.S['presets'].update(copy.deepcopy(preferences.BUILTINS))
        for key in preferences.BUILTINS:a.S['settings'].get('default_guides',{}).pop(key,None)
        a.save();return {'ok':True}
    if path=='/api/choose-path':
        if not a.WINDOW: raise ValueError('Use the native Clarette app to choose a local path')
        import webview
        kind=webview.FileDialog.FOLDER if d.get('kind')=='folder' else webview.FileDialog.OPEN
        paths=a.WINDOW.create_file_dialog(kind,allow_multiple=False)
        return {'path':paths[0] if paths else None}
    if path=='/api/window-fit':
        import native
        native.fit_window(d['kind'],d['height']);return {'ok':True}
    if path=='/api/close-window':
        import native
        native.close_window(d['kind']);return {'ok':True}
    if path=='/api/fullscreen':
        import native
        native.toggle_maximize(a)
        return {'ok':True}
    if path=='/api/feedback':
        import platform,urllib.parse,webbrowser
        query=urllib.parse.urlencode({'subject':'Clarette Feedback - v'+a.VERSION,'body':'Clarette '+a.VERSION+' ('+a.BUILD+')\nmacOS '+platform.mac_ver()[0]+'\n\nFeedback:\n'})
        webbrowser.open('mailto:hi@kleberdavila.com?'+query);return {'ok':True}
    if path=='/api/save-document':
        import webview
        if not a.WINDOW:return {'document':d['document']}
        if d['document'].get('format') not in ('clarette-preferences','clarette-output-presets'):raise ValueError('Invalid document')
        paths=a.WINDOW.create_file_dialog(webview.FileDialog.SAVE,save_filename=d['document']['format']+'.json',file_types=('JSON (*.json)',))
        if not paths:return {'cancelled':True}
        a.atomic(Path(paths[0]),json.dumps(d['document'],indent=2).encode());return {'saved':True}
    if path in ('/api/install-model','/api/remove-model','/api/disconnect-model'):
        if any(j['status']=='running' for j in a.JOBS.values()):raise ValueError('Wait for the current operation to finish before changing installed models')
    if path=='/api/disconnect-model':
        engine=d.get('engine')
        if engine not in ('osediff','flowsr','seesr'):raise ValueError('Unknown enhancement engine')
        if not d.get('confirmed'):raise ValueError('Confirm disconnecting this external model')
        a.S['settings'][engine+'_location']='';a.save();return {'ok':True}
    if path=='/api/install-model':
        if d.get('engine') in ('osediff','flowsr','seesr'):
            import managed_engines
            engine=d['engine']
            if not (managed_engines.TEMPLATES/engine/'downloads.json').is_file():raise ValueError('A verified installer is not available for this engine yet')
            if engine=='flowsr' and not d.get('noncommercial_confirmed'):raise ValueError('FlowSR is licensed for noncommercial use only')
            def install_managed(report):
                result=managed_engines.install(engine,report)
                # Activate only a fully verified, atomically published package.
                with a.LOCK:
                    a.S['settings'][engine+'_location']='';a.save()
                return result
            return a.start_job('Install '+engine,install_managed)
        if d.get('engine')!='edsr':raise ValueError('A supported Mac installer is not available for this engine yet')
        def install(report):
            target=a.MODELS/'EDSR_x2.pb'
            if target.is_symlink():raise ValueError('Model location cannot be a symbolic link')
            a.imaging.download('https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x2.pb',target,report)
            report.check()
            return {'installed':'edsr'}
        return a.start_job('Install EDSR',install)
    if path=='/api/models':
        result=[]
        if a.MODELS.exists():
            for p in a.MODELS.iterdir():
                if not p.is_symlink():result.append(dict(name=p.name,bytes=storage.size(p) if p.is_dir() else p.stat().st_size))
        return {'models':result}
    if path=='/api/remove-model':
        if not d.get('confirmed'):raise ValueError('Confirm removal of this optional downloaded model')
        if d.get('engine') in ('osediff','flowsr','seesr'):
            import managed_engines
            from optional_engines import package_status
            engine=d['engine'];location=a.S['settings'].get(engine+'_location','')
            if location and package_status(engine,location)['external']:
                raise ValueError('This model is in an external folder. Disconnect it to keep its files.')
            a.ENGINE.close()
            result=managed_engines.uninstall(engine)
            a.S['settings'][engine+'_location']='';a.save();return result
        name=d['name'];p=a.MODELS/name
        if Path(name).name!=name or name in ('.','..') or p.is_symlink():raise ValueError('Invalid model path')
        a.ENGINE.close()
        import shutil
        if p.is_dir():shutil.rmtree(p)
        elif p.is_file():p.unlink()
        return {'ok':True}
    if path=='/api/provider-models':
        import cloud
        return cloud.test_connection(d['provider'])
    if path=='/api/new-batch': return {'batch':new_batch(a,d.get('name'),d.get('output'))['id']}
    if path=='/api/rename-batch':
        b=a.S['batches'][a.S['active']];b['name']=batch_name(d['name']);b['subfolder']=b['name'];a.save();return {'ok':True}
    if path=='/api/batch-folder':
        b=a.S['batches'][a.S['active']];b['output_folder']=str(Path(d['path']).expanduser());a.save();return {'ok':True}
    if path=='/api/close-batch':
        b=a.S['batches'][a.S['active']]
        if any(not a.saved(f) for f in b['files']) and not d.get('confirmed'): raise ValueError('Confirm closing this batch with unsaved edits. It remains recoverable for seven days.')
        b['closed_at']=time.time();a.S['active']=None;a.save();return {'ok':True}
    if path=='/api/color-mode':
        if d['mode'] not in ('RGB','CMYK'): raise ValueError('Invalid color mode')
        if d['mode']=='CMYK':
            from exporting import validate
            validate('TIFF','CMYK',False,a.S['settings'])
        a.S['batches'][a.S['active']]['color_mode']=d['mode'];a.save();return {'ok':True}
    if path=='/api/settings':
        a.S['settings']=preferences.validate_settings(d,a.S['settings']);a.save();return {'ok':True}
    if path=='/api/reset-general':
        for k in ('notifications','notification_sound'): a.S['settings'][k]=preferences.defaults()[k]
        a.save();return {'ok':True}
    if path=='/api/workspace':
        ws=preferences.validate_workspace2(a.S.get('workspace2',preferences.default_workspace2()));op=d.get('operation','select')
        if op=='select':
            key=d.get('id')
            if key not in preferences.WORKSPACE_PRESETS and key not in ws['custom']: raise ValueError('Workspace not found')
            ws['active']=key
        elif op in ('save','create'):
            # 'save' while a built-in preset is active forks it into a new custom
            # workspace (presets stay protected); 'save' while already on a custom
            # workspace overwrites it in place. 'create' always makes a new one
            # (used by the "New Workspace..." window).
            layout=preferences.validate_dockview_layout(d['layout'])
            if op=='create' or ws['active'] in preferences.WORKSPACE_PRESETS:
                # Only 'create' (the explicit "New Workspace..." menu action) may
                # fork while locked; a bare 'save' -- the debounced autosave that
                # fires on any layout change, including a remote-driven preset
                # switch replaying through the local dockview instance -- must not
                # silently spawn a new custom workspace behind a locked one.
                if op=='save' and ws.get('locked'): raise ValueError('Unlock the workspace to save changes')
                key=a.ident();name=str(d.get('name','')).strip() or 'Custom Layout'
                based_on=ws['active'] if ws['active'] in preferences.WORKSPACE_PRESETS else None
                ws['custom'][key]=dict(name=name,layout=layout,basedOn=based_on);ws['active']=key
            else:
                if ws.get('locked'): raise ValueError('Unlock the workspace to save changes')
                key=ws['active'];ws['custom'][key]=dict(ws['custom'][key],layout=layout)
        elif op=='rename':
            if ws['active'] not in ws['custom']: raise ValueError('Built-in workspace names are protected')
            name=str(d.get('name','')).strip()
            if not name or len(name)>80: raise ValueError('Enter a workspace name under 80 characters')
            ws['custom'][ws['active']]=dict(ws['custom'][ws['active']],name=name)
        elif op=='delete':
            if ws['active'] not in ws['custom']: raise ValueError('Built-in workspaces cannot be deleted')
            del ws['custom'][ws['active']];ws['active']='landscape'
        elif op=='lock': ws['locked']=bool(d.get('locked'))
        elif op=='reset':
            # Discard customizations to the current layout, reverting to the preset it
            # forked from (or the default, if it wasn't a fork of anything in particular).
            if ws['active'] in ws['custom']:
                based_on=ws['custom'][ws['active']].get('basedOn') or 'landscape'
                del ws['custom'][ws['active']];ws['active']=based_on
        elif op=='restore-default': ws['active']='landscape'
        else: raise ValueError('Unknown workspace operation')
        a.S['workspace2']=preferences.validate_workspace2(ws);a.save()
        import native
        native.refresh_menus()
        return {'active':a.S['workspace2']['active']}
    if path=='/api/preset-manage':
        key=d.get('id');op=d['operation']
        if op in ('delete','rename','edit') and key in preferences.BUILTINS: raise ValueError('Built-in presets are protected')
        if op=='delete': a.S['presets'].pop(key,None)
        else:
            from output_presets import validate_document
            from guides import guide_for
            p=copy.deepcopy(d.get('preset') or a.S['presets'].get(key) or a.S['batches'][a.S['active']]['canvas'])
            p['label']=d.get('name',p['label']);p['guide']=p.get('guide') or guide_for(p)
            p=validate_document(dict(format='clarette-output-presets',version=1,presets=[p]))[0];p.pop('import_id',None)
            if op in ('create','duplicate'): key=a.ident()
            a.S['presets'][key]=p
        a.save();return {'id':key}
    if path=='/api/preferences-export': return {'document':preferences.portable(a.S)}
    if path=='/api/preferences-import':
        doc=d['document']
        if doc.get('format')!='clarette-preferences' or doc.get('version') not in (1,2): raise ValueError('Choose a Clarette preferences file')
        if not d.get('confirmed'): raise ValueError('Confirm replacing preferences')
        settings=preferences.validate_settings(doc.get('settings',{}),a.S['settings'])
        # Preferences files exported before the Dockview rewrite (version 1) carried an
        # `orientation`/`order`/`sizes` workspace shape that no longer means anything;
        # there's nothing safe to migrate, so those imports just fall back to Default.
        workspace2,_=preferences.recover_workspace2(doc.get('workspace2') if doc.get('version')==2 else None)
        from output_presets import validate_document
        from guides import guide_for
        presets={}
        for k,v in doc.get('presets',{}).items():
            p=dict(v,guide=v.get('guide') or guide_for(v));p=validate_document(dict(format='clarette-output-presets',version=1,presets=[p]))[0];p.pop('import_id',None);presets[k]=p
        from shortcuts import validate
        shortcuts=validate(doc.get('shortcuts',{}))
        a.S['settings']=settings;a.S['workspace2']=workspace2;a.S['presets']={**presets,**copy.deepcopy(preferences.BUILTINS)};a.S['shortcuts']=shortcuts
        a.save();return {'ok':True}
    if path=='/api/shortcuts':
        from shortcuts import validate
        a.S['shortcuts']=validate(d['shortcuts']);a.save()
        import native
        native.refresh_menus()
        return {'ok':True}
    if path=='/api/print-profiles':
        from exporting import installed_cmyk_profiles
        return {'profiles':installed_cmyk_profiles()}
    if path=='/api/storage': return dict(cache_location=str(a.CACHE),cache_bytes=storage.size(a.CACHE),model_bytes=storage.size(a.MODELS)+storage.size(a.DATA/'hypir-evaluation')+storage.size(a.DATA/'engines'),legacy_bytes=storage.size(a.DATA/'batches'))
    if path=='/api/empty-cache':
        if not d.get('confirmed'): raise ValueError('Confirm emptying unused caches')
        removed=storage.clean(a.CACHE,a.S,empty=True)
        for b in a.S['batches'].values():
            for f in b['files']: removed+=storage.prune_item(a.folder(f),f)
        a.save();return {'removed':removed}
    if path=='/api/restore-status': return restore_status(a.S['settings'].get('restore_location',''))
    if path=='/api/window':
        import native
        return native.open_window(a,d['kind'],d.get('payload',{}))
    return UNHANDLED
