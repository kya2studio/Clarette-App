"""Track only portraits explicitly sent to Photos; consume saved edits under the app lock."""
import atexit
import json
import queue
import subprocess
from pathlib import Path

_sessions = {}
_events = queue.Queue()

def close():
    for session in list(_sessions.values()):
        if session['process'].poll() is None:
            session['process'].terminate()
    _sessions.clear()

atexit.register(close)

def send(app, batch, portrait):
    import threading
    key = (batch['id'], portrait['id'])
    existing = _sessions.get(key)
    if existing and existing['process'].poll() is None:
        subprocess.Popen(['open', '-a', 'Photos'])
        return
    folder = app.folder(portrait)
    exchange = folder / 'PHOTOS_RETURNS'
    exchange.mkdir(exist_ok=True)
    source = exchange / 'sent.png'
    app.atomic(source, app.imaging.png(app.imaging.color(app.imaging.load(folder / portrait['work']), portrait.get('draft', portrait['color']))))
    helper = Path(__file__).resolve().parent / 'photos' / 'PhotosBridge'
    process = subprocess.Popen([str(helper), str(source), str(exchange)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    session = {'process': process, 'revision': portrait.get('revision'), 'exchange': exchange}
    _sessions[key] = session
    def receive():
        for line in process.stdout:
            try:
                event = json.loads(line)
                _events.put((key, session, event))
            except ValueError:
                pass
        if process.wait() and _sessions.get(key) is session:
            _events.put((key, session, {'error': 'Photos connection ended. Check Photos access in macOS Privacy & Security.'}))
    threading.Thread(target=receive, daemon=True).start()

def receive_pending(app):
    # State calls already hold the editor lock; never change a source during processing.
    if any(job['status'] == 'running' for job in app.JOBS.values()):
        return
    while True:
        try:
            key, session, event = _events.get_nowait()
        except queue.Empty:
            break
        if _sessions.get(key) is not session:
            continue
        batch = app.S['batches'].get(key[0])
        portrait = next((item for item in (batch or {}).get('files', []) if item['id'] == key[1]), None)
        if portrait is None:
            session['process'].terminate(); _sessions.pop(key, None)
            continue
        if 'error' in event:
            portrait['photos_error'] = str(event['error']); continue
        if 'edited' not in event:
            continue
        path = Path(event['edited']).resolve()
        if path.parent != session['exchange'].resolve() or not path.is_file():
            continue
        if portrait.get('revision') != session['revision']:
            portrait['photos_error'] = 'Photos edit kept in the working folder under PHOTOS_RETURNS. This portrait changed in Clarette; import the returned image to replace it.'
            continue
        try:
            image = app.imaging.load(path)
            app.commit_work(portrait, image, preserve_mask=False)
            baseline = 'BASELINE/' + app.ident() + '.png'
            app.atomic(app.folder(portrait) / baseline, app.imaging.png(image))
            portrait['baseline'] = baseline
            portrait['original_region'] = [0, 0, image.width, image.height]
            portrait['photos_returned'] = portrait.get('photos_returned', 0) + 1
            portrait.pop('photos_error', None)
            session['revision'] = portrait.get('revision')
            app.save()
            path.unlink()
        except Exception as error:
            portrait['photos_error'] = 'Photos edit could not be imported: ' + str(error)
