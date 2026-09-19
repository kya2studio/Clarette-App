"""Local Real-ESRGAN restoration using the bundled, verified ONNX conversion."""
from pathlib import Path
import hashlib,math
import numpy as np
from PIL import Image
_SESSION=None
MODEL=Path(__file__).resolve().parent/'models/RealESRGAN_x4plus.onnx'
FAST_MODEL=Path(__file__).resolve().parent/'models/realesr-general-x4v3.onnx'

def restore(im,scale=2,strength=70,report=lambda s:None,model_path=None,accelerate=False):
    global _SESSION
    if scale not in (1,2,4):raise ValueError('Choose 1×, 2× or 4×')
    if im.width*im.height*scale*scale>32000000:raise ValueError('Restoration exceeds 32 megapixels; choose a smaller scale.')
    strength=float(strength)
    if not math.isfinite(strength):raise ValueError('Invalid restoration strength')
    strength=max(0,min(100,strength))/100
    base=im.resize((im.width*scale,im.height*scale),Image.Resampling.LANCZOS)
    if not strength:return base
    path=Path(model_path or MODEL)
    if not path.is_file():raise ValueError('The bundled restoration model is missing. Reinstall Clarette.')
    if _SESSION is None or _SESSION[0]!=str(path):
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
        providers=['CPUExecutionProvider']
        if accelerate and 'CoreMLExecutionProvider' in ort.get_available_providers():providers.insert(0,'CoreMLExecutionProvider')
        _SESSION=(str(path),ort.InferenceSession(str(path),sess_options=options,providers=providers))
    session=_SESSION[1];rgb=np.asarray(im.convert('RGB'));h,w=rgb.shape[:2];result=np.empty((h*scale,w*scale,3),np.uint8)
    tile=128;pad=36;total=math.ceil(w/tile)*math.ceil(h/tile);done=0
    for y in range(0,h,tile):
        for x in range(0,w,tile):
            x1,y1=min(w,x+tile),min(h,y+tile);l,t,r,b=max(0,x-pad),max(0,y-pad),min(w,x1+pad),min(h,y1+pad)
            report(f'Restoring detail and compression artifacts: tile {done+1}/{total}')
            feed=np.ascontiguousarray(rgb[t:b,l:r].transpose(2,0,1)[None],dtype=np.float32)/255
            prediction=session.run(None,{'image':feed})[0][0].transpose(1,2,0)
            patch=Image.fromarray(np.uint8(np.rint(np.clip(prediction,0,1)*255)))
            if scale!=4:patch=patch.resize(((r-l)*scale,(b-t)*scale),Image.Resampling.LANCZOS)
            result[y*scale:y1*scale,x*scale:x1*scale]=np.asarray(patch)[(y-t)*scale:(y1-t)*scale,(x-l)*scale:(x1-l)*scale];done+=1
    restored=Image.fromarray(result)
    if strength<1:restored=Image.blend(base.convert('RGB'),restored,strength)
    restored=restored.convert('RGBA');restored.putalpha(base.getchannel('A'));return restored
