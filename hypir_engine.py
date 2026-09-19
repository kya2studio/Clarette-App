"""Optional HYPIR runtime, isolated from the small desktop environment."""
import json, os, queue, subprocess, threading
from pathlib import Path
from support import support_dir

PROCESS = None
MESSAGES = None

def configuration(location=''):
    path = Path(location).expanduser() if location else support_dir() / 'hypir-runtime.json'
    if not path.is_file():
        raise ValueError('HYPIR runtime is not installed for this Clarette session.')
    config = json.loads(path.read_text())
    for key in ('python', 'repository', 'base_model', 'weights'):
        if not Path(config[key]).exists():
            raise ValueError('HYPIR runtime is incomplete: ' + key)
    return config

def available(location=''):
    try: configuration(location); return True
    except (OSError, ValueError, KeyError): return False

def enhance(im, scale, amount, report, location=''):
    global PROCESS, MESSAGES
    import tempfile
    from PIL import Image
    config = configuration(location)
    if scale not in (1, 2, 4) or not 0 <= amount <= 100:
        raise ValueError('Invalid HYPIR scale or strength')
    if im.width * im.height * scale * scale > 8_000_000:
        raise ValueError('HYPIR evaluation supports up to 8 megapixels. Crop the headshot or choose a smaller scale.')
    if amount == 0:
        return im.resize((im.width*scale, im.height*scale), Image.Resampling.LANCZOS)
    if PROCESS is None or PROCESS.poll() is not None:
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(config['packages'])
        from storage import cache_dir
        env['HF_HOME'] = str(cache_dir(support_dir())/'hf-cache')
        env['HF_HUB_OFFLINE'] = '1'
        env['NUMBA_CACHE_DIR'] = str(cache_dir(support_dir())/'numba-cache')
        PROCESS = subprocess.Popen([config['python'], '-u', str(Path(__file__).with_name('hypir_runner.py'))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1, env=env)
        MESSAGES = queue.Queue()
        def read(proc, messages):
            for line in proc.stdout:
                try: messages.put(json.loads(line))
                except ValueError: pass
            messages.put({'error':'HYPIR stopped before finishing. Your previous edit is preserved.'})
        threading.Thread(target=read,args=(PROCESS,MESSAGES),daemon=True).start()
    from storage import cache_dir
    with tempfile.TemporaryDirectory(prefix='hypir-', dir=cache_dir(support_dir())) as temp:
        source=Path(temp)/'source.png';output=Path(temp)/'result.png';im.save(source)
        PROCESS.stdin.write(json.dumps(dict(config=config,source=str(source),output=str(output),scale=scale,amount=amount))+'\n');PROCESS.stdin.flush()
        while True:
            try: item=MESSAGES.get(timeout=.15)
            except queue.Empty: continue
            if 'progress' in item: report(item['progress'])
            elif 'error' in item: raise ValueError(item['error'])
            else:
                with Image.open(output) as result: return result.convert('RGBA')
