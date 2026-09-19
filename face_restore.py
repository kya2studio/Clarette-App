"""GFPGAN-based face restoration, layered on top of whatever main enhancement
already ran -- same pattern as Real-ESRGAN's own optional --face_enhance flag.

Reuses the face landmarks the app's existing YuNet detector (imaging.faces)
already computes, aligns them to GFPGAN's canonical 512x512 face template with
a similarity transform, runs the restoration network, then warps the result
back into the original photo with a soft feathered blend so there is no
hard-edged paste.
"""
from pathlib import Path
import numpy as np
from PIL import Image

MODEL=Path(__file__).resolve().parent/'models/GFPGANv1.4.onnx'

# Standard 5-point FFHQ template GFPGAN was trained against (xinntao/facexlib).
TEMPLATE=np.array([[192.98138,239.94708],[318.90277,240.19360],[256.63416,314.01935],
                   [201.26117,371.41043],[313.08905,371.15118]],dtype=np.float32)

_SESSION=None

def _order_by_x(points):
    return points[np.argsort(points[:,0])]

def restore_face(im,landmarks5,strength=100,accelerate=False):
    """im: PIL RGBA image. landmarks5: 5x2 array-like in the same pixel space as
    im, order right-eye/left-eye/nose/right-mouth-corner/left-mouth-corner (the
    order imaging.faces() returns) -- but matched to the template by relative
    image position, not by that label, since detector left/right conventions
    vary. Returns a new PIL RGBA image, or the original if strength is 0."""
    global _SESSION
    strength=max(0,min(100,float(strength)))/100
    if not strength:return im
    if not MODEL.is_file():raise ValueError('The bundled face-restoration model is missing. Reinstall Clarette.')
    import cv2
    pts=np.asarray(landmarks5,dtype=np.float32)
    if pts.shape!=(5,2):raise ValueError('Expected 5 face landmarks')
    eyes=_order_by_x(pts[0:2]);mouth=_order_by_x(pts[3:5])
    src=np.array([eyes[0],eyes[1],pts[2],mouth[0],mouth[1]],dtype=np.float32)
    matrix,_=cv2.estimateAffinePartial2D(src,TEMPLATE,method=cv2.LMEDS)
    if matrix is None:raise ValueError('Could not align this face for restoration')

    rgb=np.asarray(im.convert('RGB'))
    aligned=cv2.warpAffine(rgb,matrix,(512,512),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)

    if _SESSION is None:
        import onnxruntime as ort
        providers=['CPUExecutionProvider']
        if accelerate and 'CoreMLExecutionProvider' in ort.get_available_providers():providers.insert(0,'CoreMLExecutionProvider')
        _SESSION=ort.InferenceSession(str(MODEL),providers=providers)

    feed=(aligned.astype(np.float32)/255.0*2-1).transpose(2,0,1)[None]
    out=_SESSION.run(None,{'face':feed})[0][0]
    restored=np.clip((out.transpose(1,2,0)+1)/2*255,0,255).astype(np.uint8)

    # Soft oval mask covering the face (not a hard rectangle), feathered at the edges.
    mask=np.zeros((512,512),np.float32)
    cv2.ellipse(mask,(256,270),(180,225),0,0,360,1.0,-1)
    feather=(512//12)|1
    mask=cv2.GaussianBlur(mask,(feather,feather),0)

    inverse=cv2.invertAffineTransform(matrix)
    h,w=rgb.shape[:2]
    warped_face=cv2.warpAffine(restored,inverse,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    warped_mask=cv2.warpAffine(mask,inverse,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    weight=(warped_mask*strength)[...,None]

    blended=rgb.astype(np.float32)*(1-weight)+warped_face.astype(np.float32)*weight
    result=Image.fromarray(np.clip(blended,0,255).astype(np.uint8),'RGB').convert('RGBA')
    result.putalpha(im.getchannel('A'))
    return result
