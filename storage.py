"""Managed caches. Cleanup traverses only application-owned, non-symlink paths."""
import os
import time
import shutil
from pathlib import Path

RETENTION=7*24*60*60

def cache_dir(data):
    override=os.environ.get('CLARETTE_CACHE')
    if override: root=Path(override).expanduser().resolve()
    elif os.environ.get('CLARETTE_DATA') or os.environ.get('GLASS_STUDIO_DATA'): root=Path(data)/'cache'
    else: root=Path.home()/'Library/Caches/com.clarette.headshots'
    root.mkdir(parents=True,exist_ok=True)
    return root

def references(value):
    found=set()
    if isinstance(value,dict):
        for k,v in value.items():
            if k in ('work','mask','baseline','original','stable_work','mask_review_work') and isinstance(v,str): found.add(v)
            elif isinstance(v,(dict,list)): found.update(references(v))
    elif isinstance(value,list):
        for item in value: found.update(references(item))
    return found

def prune_item(root,record):
    root=Path(root)
    if root.is_symlink(): return 0
    keep=references(record);removed=0
    for directory in ('HISTORY','MASKS','BASELINE'):
        parent=root/directory
        if parent.is_symlink() or not parent.is_dir(): continue
        for p in parent.iterdir():
            if not p.is_symlink() and p.is_file() and p.relative_to(root).as_posix() not in keep:
                removed+=p.stat().st_size;p.unlink()
    return removed

def size(root):
    total=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if not (Path(directory)/d).is_symlink()]
        for name in files:
            p=Path(directory)/name
            if not p.is_symlink():
                try: total+=p.stat().st_size
                except FileNotFoundError: pass
    return total

def clean(cache,state,empty=False,now=None):
    now=time.time() if now is None else now;removed=0
    # Saved sessions stay recoverable. Only explicitly closed/abandoned records expire.
    for bid,batch in list(state['batches'].items()):
        if bid==state.get('active') or not batch.get('closed_at'): continue
        if now-batch['closed_at']<RETENTION: continue
        p=Path(cache)/'batches'/bid
        if p.is_symlink() or '/' in bid or '..' in bid: continue
        if p.is_dir(): removed+=size(p);shutil.rmtree(p)
        del state['batches'][bid]
    for bid,batch in state['batches'].items():
        keep=[]
        for entry in batch.get('removed_files',[]):
            if now-entry['removed_at']<RETENTION:keep.append(entry);continue
            fid=entry['file']['id'];p=Path(cache)/'batches'/bid/'items'/fid
            if any(Path(x).name!=x or x in ('.','..') for x in (bid,fid)) or any(parent.is_symlink() for parent in (p,p.parent,p.parent.parent)):keep.append(entry);continue
            if p.is_dir():removed+=size(p);shutil.rmtree(p)
        batch['removed_files']=keep
    for name in ('mask-cache','upscale-cache','previews'):
        p=Path(cache)/name
        if empty and p.is_dir() and not p.is_symlink(): removed+=size(p);shutil.rmtree(p)
        elif p.is_dir() and not p.is_symlink():
            for entry in p.iterdir():
                if entry.is_file() and not entry.is_symlink() and now-entry.stat().st_mtime>RETENTION:
                    removed+=entry.stat().st_size;entry.unlink()
    for p in Path(cache).glob('job-*'):
        if p.is_dir() and not p.is_symlink() and now-p.stat().st_mtime>RETENTION:
            removed+=size(p);shutil.rmtree(p)
    return removed

def migrate(data,cache,state):
    """Copy-before-switch migration; legacy source is preserved until explicitly reviewed."""
    for batch in state['batches'].values():
        old=Path(data)/'batches'/batch['id'];new=Path(cache)/'batches'/batch['id']
        if old.is_dir() and not old.is_symlink() and not new.exists():
            stage=new.with_name(new.name+'.migration');stage.parent.mkdir(parents=True,exist_ok=True)
            if stage.is_symlink():raise ValueError('Unsafe legacy migration staging path')
            if stage.exists(): shutil.rmtree(stage)
            if any(p.is_symlink() for p in old.rglob('*')):raise ValueError('Legacy batch contains symbolic links; migration needs review before opening')
            shutil.copytree(old,stage,symlinks=False)
            stage.rename(new)
    return state


def discard_batch(cache,data,bid):
    """Permanently remove owned pixels; never follow paths from image/export records."""
    import json
    if not isinstance(bid,str) or Path(bid).name!=bid or bid in ('.','..'):raise ValueError('Invalid batch id')
    roots=[Path(cache)/'batches'/bid,Path(data)/'batches'/bid]
    roots += [Path(cache)/name for name in ('mask-cache','upscale-cache','previews')]
    for root in roots:
        if root.is_symlink() or root.parent.is_symlink():raise ValueError('Unsafe managed cache path')
    for root in roots:
        if root.is_dir():shutil.rmtree(root)
    # Recovery metadata must not resurrect deliberately discarded batches.
    for path in Path(data).glob('session-recovery-*.json'):
        if path.is_symlink():continue
        try:record=json.loads(path.read_text())
        except (OSError,ValueError):continue
        if isinstance(record,dict) and isinstance(record.get('batches'),dict) and bid in record['batches']:
            record['batches'].pop(bid)
            if record.get('active')==bid:record['active']=None
            temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(record));temporary.replace(path)
