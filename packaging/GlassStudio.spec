# Run on Apple Silicon macOS. The build machine supplies Python, not the user.
from PyInstaller.utils.hooks import collect_all, collect_submodules
from pathlib import Path
root=Path(SPECPATH).parent
datas=[(str(root/'engine-packages'),'engine-packages'),(str(root/'web'),'web'),(str(root/'models'),'models'),(str(root/'hypir_runner.py'),'.'),(str(root/'adapter_runner.py'),'.'),(str(root/'HYPIR-LICENSE.txt'),'.')];binaries=[(str(root/'photos/PhotosBridge'),'photos')];hiddenimports=['webview.platforms.cocoa','image_worker','voice_actions','imaging','cv2','support','output_presets','guides','notifications','UserNotifications','credentials','cloud','Security','requests','release','preferences','storage','exporting','providers','actions','shortcuts','native','photos_bridge','optional_engines','managed_engines','hypir_engine','restoration','face_restore','license']
for package in ('rembg','pymatting','onnxruntime'):
    d,b,h=collect_all(package);datas+=d;binaries+=b;hiddenimports+=h
hiddenimports+=collect_submodules('webview')
a=Analysis([str(root/'desktop.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,runtime_hooks=[str(root/'packaging/runtime_readonly.py')])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Clarette',console=False,target_arch='arm64')
coll=COLLECT(exe,a.binaries,a.datas,name='Clarette')
app=BUNDLE(coll,name='Clarette.app',bundle_identifier='com.clarette.headshots',icon=str(root/'ClaretteIcon.icns'),info_plist={'CFBundleShortVersionString':'1.0.1','CFBundleVersion':'1001','NSHighResolutionCapable':True,'NSPhotoLibraryUsageDescription':'Clarette sends the portrait you select to Photos and brings its saved edits back into your batch.','NSPhotoLibraryAddUsageDescription':'Clarette adds the portrait you select so you can edit it in Photos.','LSMinimumSystemVersion':'12.0'})
