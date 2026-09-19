"""Enhancement adapters. Optional Restore engines implement manifest API version 1.

No model or Python package is downloaded or executed during status inspection.
The user-selected local adapter executes only after an explicit Enhance action.
"""
import importlib.util
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class EnhanceRequest:
    input_path: str
    output_dir: str
    scale: int=1
    strength: float=.35
    mode: str='balanced'
    preserve_identity: bool=True
    model_location: str=''
    method: str='fast'

class EnhancementProvider:
    supports_outpaint=False
    def enhance(self,request,progress_callback,cancel_token): raise NotImplementedError

def bundled_restoration_status():
    """Status for the general-purpose Real-ESRGAN model shipped inside the app itself,
    used when no external Clarette Restore adapter package is configured."""
    from pathlib import Path
    model=Path(__file__).resolve().parent/'models/realesr-general-x4v3.onnx'
    if model.is_file():
        return dict(status='Ready',version='realesr-general-x4v3',external=False,
                    message='Built-in general photo restoration (Real-ESRGAN, BSD-3-Clause). Works well for mild-to-moderate detail loss; a custom-trained model can still be configured above.')
    return dict(status='Missing',version=None,external=False,message='Clarette Restore is not installed. Choose an engine package containing clarette-restore.json.')

def restore_status(location):
    if not location: return dict(status='Missing',version=None,message='Clarette Restore is not installed. Choose an engine package containing clarette-restore.json.')
    root=Path(location).expanduser();manifest=root/'clarette-restore.json' if root.is_dir() else root
    if not manifest.is_file(): return dict(status='Missing',version=None,message='Model package not found.')
    try:
        data=json.loads(manifest.read_text())
        if data.get('api_version')!=1: raise ValueError('Requires adapter API version 1')
        entry=(manifest.parent/data['entrypoint']).resolve();checkpoint=(manifest.parent/data['checkpoint']).resolve()
        if manifest.parent.resolve() not in entry.parents or manifest.parent.resolve() not in checkpoint.parents: raise ValueError('Engine files must be inside its package')
        if entry.suffix!='.py' or not entry.is_file() or not checkpoint.is_file(): raise ValueError('Missing adapter or checkpoint')
        return dict(status='Ready',version=str(data.get('version','Unknown')),entrypoint=str(entry),checkpoint=str(checkpoint),message='Experimental local adapter; runtime compatibility is checked on use.')
    except Exception as e: return dict(status='Incompatible',version=None,message=str(e))

class LocalClaretteRestoreProvider(EnhancementProvider):
    def enhance(self,request,progress_callback,cancel_token):
        status=restore_status(request.model_location)
        if status['status']!='Ready': raise ValueError(status['message'])
        cancel_token.check();progress_callback('Loading Clarette Restore…')
        spec=importlib.util.spec_from_file_location('clarette_restore_adapter',status['entrypoint'])
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        if not callable(getattr(module,'enhance',None)): raise ValueError('Clarette Restore adapter does not expose enhance()')
        result=module.enhance(input_path=request.input_path,output_dir=request.output_dir,checkpoint=status['checkpoint'],
                              mode=request.mode,scale=request.scale,strength=request.strength,preserve_identity=request.preserve_identity,
                              progress_callback=progress_callback,cancel_token=cancel_token)
        cancel_token.check()
        from imaging import load
        path=result.get('output_path') if isinstance(result,dict) else result
        if not isinstance(path,(str,Path)): raise ValueError('Restore adapter must return an output image path')
        return load(path)

class ClassicalProvider(EnhancementProvider):
    def enhance(self,request,progress_callback,cancel_token):
        import imaging
        cancel_token.check()
        return imaging.enhance(imaging.load(request.input_path),Path(request.output_dir)/'models',request.scale,request.strength*100,progress_callback,request.method)

class CloudOpenAIProvider(EnhancementProvider):
    provider='openai'
    def enhance_image(self,image,model,prompt,progress_callback):
        from cloud import enhance
        return enhance(image,self.provider,model,prompt,progress_callback)

class CloudGeminiProvider(CloudOpenAIProvider): provider='gemini'
class CloudSeedreamProvider(CloudOpenAIProvider): provider='seedream'

def normalize_result(result,reference):
    """Align a returned image using robust feature geometry, never anisotropic scaling.

    Strong feature consensus permits a similarity transform. Otherwise keep the
    aspect ratio with a conservative centered fit and flag it for visual review.
    """
    import cv2
    import numpy as np
    from PIL import Image,ImageOps,ImageChops
    rw,rh=reference.size
    scale=min(result.width/rw,result.height/rh)
    target=(max(1,round(rw*scale)),max(1,round(rh*scale)))
    out=None
    try:
        a=reference.convert('RGB');b=result.convert('RGB');a.thumbnail((1000,1000));b.thumbnail((1000,1000))
        orb=cv2.ORB_create(nfeatures=2000)
        ka,da=orb.detectAndCompute(cv2.cvtColor(np.array(a),cv2.COLOR_RGB2GRAY),None)
        kb,db=orb.detectAndCompute(cv2.cvtColor(np.array(b),cv2.COLOR_RGB2GRAY),None)
        if da is not None and db is not None:
            matches=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db,da,k=2)
            good=[pair[0] for pair in matches if len(pair)==2 and pair[0].distance<.7*pair[1].distance]
            if len(good)>=12:
                src=np.float32([kb[m.queryIdx].pt for m in good])*result.width/b.width
                dst=np.float32([ka[m.trainIdx].pt for m in good])*target[0]/a.width
                matrix,inliers=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=4*scale)
                if matrix is not None and inliers.mean()>.55 and inliers.sum()>=12:
                    factor=float(np.hypot(matrix[0,0],matrix[0,1]))
                    # Reject implausible mappings rather than distorting or losing the subject.
                    if .35<factor<3 and abs(np.arctan2(matrix[1,0],matrix[0,0]))<.35:
                        premult=np.array(result.convert('RGBa'))
                        out=Image.fromarray(cv2.warpAffine(premult,matrix,target,flags=cv2.INTER_LANCZOS4),'RGBa').convert('RGBA')
    except cv2.error:pass
    if out is None:
        fitted=ImageOps.contain(result,target,Image.Resampling.LANCZOS)
        out=Image.new('RGBA',target);out.alpha_composite(fitted,((target[0]-fitted.width)//2,(target[1]-fitted.height)//2))
        out.info['alignment']='Aspect preserved; review framing and mask alignment.'
    else:out.info['alignment']='Aligned to source features; review facial detail.'
    if reference.getchannel('A').getextrema()[0]<255:
        out.putalpha(ImageChops.multiply(out.getchannel('A'),reference.getchannel('A').resize(target,Image.Resampling.LANCZOS)))
    return out
