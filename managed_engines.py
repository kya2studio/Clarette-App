"""Verified engine templates with isolated, replaceable model downloads."""
import hashlib,json,shutil,tempfile,subprocess,time,os,signal
from pathlib import Path

TEMPLATES=Path(__file__).resolve().parent/'engine-packages'
ENGINES={'osediff','flowsr','seesr'}

def prepare_package(stage,python,report):
    """Convert trusted bundled engine weights without blocking cancellation."""
    report('Preparing compact SeeSR weights…')
    log=stage/'installation.log'
    with log.open('w') as stream:
        proc=subprocess.Popen([str(python),'-u',str(stage/'postinstall.py')],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while proc.poll() is None:
                report.check();time.sleep(.1)
            if proc.returncode:raise ValueError('SeeSR preparation failed: '+log.read_text()[-600:])
            report.check()
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()

def installed_path(engine):
    if engine not in ENGINES:raise ValueError('Unknown enhancement engine')
    return Path.home()/'Library/Application Support/Clarette/engines'/engine

def install(engine,report):
    if engine not in ENGINES or not (TEMPLATES/engine/'downloads.json').is_file():
        raise ValueError('A verified installer is not available for this engine yet')
    shared=Path.home()/'Library/Application Support/Clarette/hypir-evaluation'
    if not (shared/'python/bin/python3').is_file() or not (shared/'sd21-base/unet').is_dir():
        raise ValueError('The shared local enhancement runtime must be installed first.')
    target=installed_path(engine)
    if target.is_symlink() or target.parent.is_symlink():raise ValueError('Model location cannot be a symbolic link')
    if target.exists():raise ValueError('This engine is already installed')
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+engine+'-',dir=target.parent))
    try:
        shutil.copytree(TEMPLATES/engine,stage,dirs_exist_ok=True)
        from imaging import download
        for item in json.loads((stage/'downloads.json').read_text()):
            path=stage/item['path']
            if stage.resolve() not in path.resolve().parents:raise ValueError('Invalid download path')
            path.parent.mkdir(parents=True,exist_ok=True)
            if item.get('bytes',1001)<1000:
                # Model metadata can legitimately be smaller than imaging.download's minimum.
                import requests
                with requests.get(item['url'],stream=True,timeout=(20,90)) as response:
                    response.raise_for_status();content=b''
                    for block in response.iter_content(1024):
                        report.check();content+=block
                        if len(content)>item['bytes']:raise ValueError('Model metadata has an unexpected size')
                path.write_bytes(content)
            else:download(item['url'],path,report)
            report.check()
            with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=item['sha256']:raise ValueError('Model download verification failed')
        if engine=='seesr':prepare_package(stage,shared/'python/bin/python3',report)
        from optional_engines import package_status
        status=package_status(engine,str(stage))
        if status['status']!='Ready':raise ValueError('Installed model package is incomplete: '+status['message'])
        report.check();stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {'installed':engine}

def uninstall(engine):
    target=installed_path(engine)
    if target.is_symlink() or target.parent.is_symlink():raise ValueError('Invalid model location')
    if target.exists():shutil.rmtree(target)
    return {'ok':True}
