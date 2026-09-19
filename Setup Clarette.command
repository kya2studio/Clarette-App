#!/bin/bash
set -eu
GLASS_ROOT="$(cd "$(dirname "$0")" && pwd)"
# Works from either the distribution folder or the app Resources folder.
if [ -f "$GLASS_ROOT/requirements.txt" ]; then GLASS_REQ="$GLASS_ROOT/requirements.txt"; else GLASS_REQ="$GLASS_ROOT/Clarette.app/Contents/Resources/requirements.txt"; fi
GLASS_SUPPORT="$HOME/Library/Application Support/Clarette"
GLASS_BASE=""
for candidate in /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3; do
 if [ -x "$candidate" ] && "$candidate" -c 'import sys; assert (3,11)<=sys.version_info[:2]<(3,14)' >/dev/null 2>&1; then GLASS_BASE="$candidate"; break; fi
done
if [ -z "$GLASS_BASE" ]; then
 echo 'Clarette needs Python 3.11, 3.12, or 3.13.'
 echo 'Install a compatible Python from python.org, or ask your IT team if this is a managed Mac.'
 echo 'No computer settings have been changed.'
 read -r -p 'Press Return to close. ' _
 exit 1
fi
CLARETTE_RES="$(dirname "$GLASS_REQ")"
"$GLASS_BASE" -c 'import sys;sys.path.insert(0,sys.argv[1]);from support import support_dir;support_dir()' "$CLARETTE_RES"
mkdir -p "$GLASS_SUPPORT"
if [ ! -x "$GLASS_SUPPORT/runtime/bin/python" ]; then "$GLASS_BASE" -m venv "$GLASS_SUPPORT/runtime"; fi
GLASS_PY="$GLASS_SUPPORT/runtime/bin/python"
echo 'Installing Clarette image tools. This can take several minutes.'
if ! "$GLASS_PY" -m pip install --upgrade pip || ! "$GLASS_PY" -m pip install -r "$GLASS_REQ"; then
 echo 'Setup did not finish. Read the error above. You can run this setup again.'
 read -r -p 'Press Return to close. ' _
 exit 1
fi
# Ensure the contrib build supplies dnn_superres even if another dependency installed OpenCV.
if ! "$GLASS_PY" -c 'import cv2; assert hasattr(cv2,"dnn_superres")' >/dev/null 2>&1; then
 "$GLASS_PY" -m pip install --force-reinstall --no-deps 'opencv-contrib-python-headless>=4.10,<5'
fi
"$GLASS_PY" -c 'import PIL,numpy,cv2,rembg,webview; assert hasattr(cv2,"dnn_superres"); print("Clarette tools are ready.")'
echo 'Setup complete. Opening Clarette. You can close this Terminal window.'
if [ -d "$GLASS_ROOT/Clarette.app" ]; then
 /usr/bin/open "$GLASS_ROOT/Clarette.app"
elif [ -d "$GLASS_ROOT/../../Contents" ]; then
 /usr/bin/open "$GLASS_ROOT/../.."
fi
