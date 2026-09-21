"""One registry shared with the native menus and all web windows."""
DEFAULTS={
 'settings':'Meta+,','new-batch':'Meta+n','close-batch':'Meta+w','import':'Meta+i','clear':'Meta+Backspace',
 'working':'Meta+Shift+o','export':'Meta+Shift+e','undo':'Meta+z','redo':'Meta+y',
 'fullscreen':'Meta+Shift+f','brush':'b','erase':'e','move':'m','lasso':'l','lock':'n',
 'guides':'g','rotate':'r','transparency':'t','fit':'Home',
 'auto-fit':'','auto-color':'','enhance':'','compare':'','preview-color':'',
 'rotate-left':'','rotate-right':'','reset-rotation':'Shift+MMB','crop':'c',
 'brush-size':'Meta+Wheel','rotate-wheel':'Shift+Wheel',
 'prompt':'','chatgpt':'','gemini':'','photoshop':'','affinity':'','photos':'',
 'import-zip':'','final':'','batch-folder':'','rename-batch':'','help':'','shortcuts':'','feedback':'',
 'workspace-landscape':'','workspace-portrait':'',
 'workspace-new':'','workspace-rename':'','workspace-delete':'','workspace-save':'','workspace-lock':'','workspace-reset':'','workspace-restore-default':'',
}

def validate(overrides):
    if not isinstance(overrides,dict) or any(k not in DEFAULTS for k in overrides): raise ValueError('Unknown shortcut action')
    result={**DEFAULTS,**overrides};used={}
    for action,key in result.items():
        if not isinstance(key,str) or len(key)>45: raise ValueError('Invalid shortcut')
        if key:
            if key in used: raise ValueError('Shortcut conflict: '+action+' and '+used[key])
            used[key]=action
    return result
