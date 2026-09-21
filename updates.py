"""GitHub Releases-based update check + self-install for the packaged
(unsigned, non-notarized) macOS build. Never touches any host but
api.github.com/repos/kya2studio/Clarette-App and that release's own asset
download URL."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

import release

REPO = 'kya2studio/Clarette-App'
API_URL = f'https://api.github.com/repos/{REPO}/releases/latest'
_TIMEOUT = 10
_HEADERS = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Clarette-App-UpdateCheck'}


def _version_tuple(v):
    parts = []
    for p in str(v).split('.'):
        digits = ''.join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_packaged():
    return bool(getattr(sys, 'frozen', False)) and sys.platform == 'darwin'


def app_bundle_path():
    """The .app bundle containing the running executable, or None outside
    the packaged build (dev mode has no bundle to replace)."""
    if not is_packaged():
        return None
    for parent in Path(sys.executable).resolve().parents:
        if parent.suffix == '.app':
            return parent
    return None


def check():
    """{'available','version','current','notes','url','asset_url','asset_name'}
    on success, or {'error': message} -- never raises, so a flaky network
    check can't take down /api/state or the update window."""
    try:
        r = requests.get(API_URL, headers=_HEADERS, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return {'error': 'Could not reach GitHub: ' + str(e)}
    if r.status_code == 404:
        return {'available': False, 'current': release.VERSION, 'notes': '', 'message': 'No releases have been published yet.'}
    if not r.ok:
        return {'error': f'GitHub returned an error ({r.status_code}).'}
    try:
        data = r.json()
    except ValueError:
        return {'error': 'GitHub returned an unexpected response.'}
    tag = str(data.get('tag_name') or '').strip()
    latest = tag[1:] if tag[:1] in 'vV' else tag
    if not latest:
        return {'error': 'The latest release has no version tag.'}
    asset = next((a for a in data.get('assets') or [] if str(a.get('name', '')).lower().endswith('.zip')), None)
    return {
        'available': _version_tuple(latest) > _version_tuple(release.VERSION),
        'version': latest,
        'current': release.VERSION,
        'notes': (data.get('body') or '').strip(),
        'url': data.get('html_url'),
        'asset_url': asset.get('browser_download_url') if asset else None,
        'asset_name': asset.get('name') if asset else None,
    }


def _download(url, dest, report=None):
    with requests.get(url, headers={'User-Agent': _HEADERS['User-Agent']}, stream=True, timeout=(10, 120)) as r:
        r.raise_for_status()
        total = int(r.headers.get('Content-Length') or 0)
        written = 0
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if report and total:
                    report(f'Downloading update… {written * 100 // total}%')


# Waits for the current Clarette process to fully quit, then swaps the
# downloaded build into place and relaunches it. Backs up the old bundle
# (moved aside, not deleted) until the copy actually succeeds, so a failed
# or interrupted swap leaves the previous working install recoverable
# instead of a half-copied, unlaunchable app.
_INSTALL_SCRIPT = '''#!/bin/sh
PID="$1"; OLD_APP="$2"; NEW_APP="$3"; BACKUP="$4"; WORKDIR="$5"
while kill -0 "$PID" 2>/dev/null; do sleep 0.3; done
sleep 0.5
rm -rf "$BACKUP"
mv "$OLD_APP" "$BACKUP" 2>/dev/null
if ditto "$NEW_APP" "$OLD_APP"; then
  rm -rf "$BACKUP"
else
  rm -rf "$OLD_APP"
  mv "$BACKUP" "$OLD_APP"
fi
open "$OLD_APP"
rm -rf "$WORKDIR"
rm -- "$0"
'''


def apply(asset_url, asset_name, report=None):
    """Downloads the release asset, verifies it contains a .app bundle, and
    spawns a detached script that waits for this process to exit, swaps the
    bundle at app_bundle_path(), and relaunches it. Caller is responsible for
    then quitting the app (this function does not -- it only stages the
    swap)."""
    if not asset_url:
        raise ValueError('This release has no downloadable build attached.')
    app_path = app_bundle_path()
    if not app_path:
        raise ValueError('Auto-install only runs in the packaged app.')
    report = report or (lambda message: None)
    work = Path(tempfile.mkdtemp(prefix='clarette-update-'))
    zip_path = work / (asset_name or 'update.zip')
    _download(asset_url, zip_path, report)
    report('Preparing the update…')
    extract_dir = work / 'extracted'
    shutil.unpack_archive(str(zip_path), str(extract_dir))
    candidates = list(extract_dir.glob('*.app'))
    if not candidates:
        raise ValueError('The downloaded update did not contain a Clarette.app bundle.')
    new_app = candidates[0]
    script_path = work / 'install.sh'
    script_path.write_text(_INSTALL_SCRIPT)
    script_path.chmod(0o755)
    backup = app_path.with_name(app_path.name + '.pre-update-backup')
    subprocess.Popen(
        ['/bin/sh', str(script_path), str(os.getpid()), str(app_path), str(new_app), str(backup), str(work)],
        start_new_session=True,
    )
