"""Clarette storage with a one-time, non-destructive legacy migration."""
import os, json, shutil, tempfile, fcntl
from pathlib import Path

def support_dir(home=None, environ=None):
    env=os.environ if environ is None else environ
    override=env.get('CLARETTE_DATA') or env.get('GLASS_STUDIO_DATA')
    if override:
        target=Path(override).expanduser().resolve();target.mkdir(parents=True,exist_ok=True);return target
    parent=Path(home or Path.home())/'Library/Application Support'
    target=parent/'Clarette';legacy=parent/'Glass Studio'
    if target.exists():return target
    parent.mkdir(parents=True,exist_ok=True)
    if not legacy.is_dir():target.mkdir(exist_ok=True);return target
    # Keep the old installation intact and refuse a live-session migration.
    with (legacy/'instance.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Quit Glass Studio before opening Clarette so its edits can be migrated safely.')
        stage=Path(tempfile.mkdtemp(prefix='.clarette-migration-',dir=parent))
        try:
            shutil.copytree(legacy,stage,dirs_exist_ok=True,ignore=shutil.ignore_patterns('runtime','numba-cache','webview','instance.lock','*.log'))
            session=stage/'session.json'
            if session.exists():
                def rewrite(v):
                    if isinstance(v,str) and v.startswith(str(legacy)+'/'):return str(target)+v[len(str(legacy)):]
                    if isinstance(v,list):return [rewrite(x) for x in v]
                    if isinstance(v,dict):return {k:rewrite(x) for k,x in v.items()}
                    return v
                session.write_text(json.dumps(rewrite(json.loads(session.read_text())),indent=2))
            if not target.exists():stage.rename(target)
        finally:
            if stage.exists():shutil.rmtree(stage)
    return target
