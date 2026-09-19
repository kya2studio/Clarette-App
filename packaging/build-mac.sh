#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
 echo 'Build on an Apple Silicon Mac with native arm64 Python 3.13.'; exit 1
fi
python3 -c 'import platform,sys; assert platform.machine()=="arm64" and (3,11)<=sys.version_info[:2]<(3,14)'
python3 -m venv .build-runtime
.build-runtime/bin/python -m pip install -r requirements.txt 'pyinstaller>=6.14,<7'
.build-runtime/bin/python -m PyInstaller --clean --noconfirm packaging/GlassStudio.spec
/usr/bin/ditto -c -k --sequesterRsrc --keepParent 'dist/Clarette.app' 'dist/Clarette_Apple_Silicon_unsigned.zip'
mkdir -p dist/dmg-stage
/usr/bin/ditto 'dist/Clarette.app' 'dist/dmg-stage/Clarette.app'
ln -sfn /Applications dist/dmg-stage/Applications
/usr/bin/hdiutil create -volname 'Clarette' -srcfolder dist/dmg-stage -ov -format UDZO 'dist/Clarette_Apple_Silicon_unsigned.dmg'
echo 'Unsigned standalone app and DMG built. Test on your Mac before sharing. Developer ID signing and notarization are optional paid distribution steps.' 
