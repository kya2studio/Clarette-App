"""Image operations. Source pixels and editable masks never depend on preview size."""
import io, math, os, threading, hashlib
from pathlib import Path
from support import support_dir
from storage import cache_dir
os.environ.setdefault('NUMBA_CACHE_DIR',str(cache_dir(support_dir())/'numba-cache'))
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageCms, ImageDraw
Image.MAX_IMAGE_PIXELS=60_000_000
def memory_limit():
    try:
        memory=os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
    except (ValueError,OSError):memory=8*1024**3
    return min(120_000_000,max(32_000_000,int(memory*.12/64)))
MAX_PIXELS=memory_limit()
Image.MAX_IMAGE_PIXELS=MAX_PIXELS
LOCK=threading.RLock()
SESSIONS={}
UPSCALERS={}
FACE_DETECTORS={}

def color_defaults():
    return dict(rgb=[[0,0],[1,1]],red=[[0,0],[1,1]],green=[[0,0],[1,1]],blue=[[0,0],[1,1]],hue=0,saturation=0,shadows=0,highlights=0,temperature=0,tint=0)

def load(path):
    with Image.open(path) as src:
        src.load();im=ImageOps.exif_transpose(src)
        if im.width*im.height>MAX_PIXELS:raise ValueError(f'Image exceeds the safe processing budget of {MAX_PIXELS//1000000} megapixels on this Mac.')
        if im.info.get('icc_profile'):
            try:
                alpha=im.getchannel('A') if 'A' in im.getbands() else None
                profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
                im=ImageCms.profileToProfile(im if im.mode in ('RGB','CMYK','LAB') else im.convert('RGB'),ImageCms.ImageCmsProfile(io.BytesIO(im.info['icc_profile'])),profile,outputMode='RGB')
                im.info['icc_profile']=profile.tobytes()
                if alpha is not None:im.putalpha(alpha)
            except Exception:raise ValueError('Cannot convert the embedded color profile to sRGB. Convert the source in a color-managed editor first.') from None
        return im.convert('RGBA')

def png(im,dpi=72):
    out=io.BytesIO();im.save(out,format='PNG',dpi=(dpi,dpi),compress_level=1);return out.getvalue()

def settings(c):
    out=color_defaults()
    for ch in ('rgb','red','green','blue'):
        pts=sorted([[float(x),float(y)] for x,y in c.get(ch,out[ch])])
        if not 2<=len(pts)<=20 or any(not math.isfinite(x+y) or not 0<=x<=1 or not 0<=y<=1 for x,y in pts) or any(b[0]<=a[0] for a,b in zip(pts,pts[1:])):raise ValueError('Invalid curve points')
        out[ch]=pts
    for ch in ('hue','saturation','shadows','highlights','temperature','tint'):
        value=float(c.get(ch,0));limit=180 if ch=='hue' else 100
        if not math.isfinite(value):raise ValueError('Invalid color adjustment')
        out[ch]=max(-limit,min(limit,value))
    return out

def curve_values(x,points):
    p=np.asarray(points,dtype=np.float64);h=np.diff(p[:,0]);d=np.diff(p[:,1])/h;m=np.zeros(len(p));m[0]=d[0];m[-1]=d[-1]
    for j in range(1,len(p)-1):
        if d[j-1]*d[j]>0:
            w1=2*h[j]+h[j-1];w2=h[j]+2*h[j-1];m[j]=(w1+w2)/(w1/d[j-1]+w2/d[j])
    v=np.clip(np.asarray(x),p[0,0],p[-1,0]);i=np.clip(np.searchsorted(p[:,0],v,side='right')-1,0,len(h)-1);t=(v-p[i,0])/h[i];t2=t*t;t3=t2*t
    return np.clip((2*t3-3*t2+1)*p[i,1]+(t3-2*t2+t)*h[i]*m[i]+(-2*t3+3*t2)*p[i+1,1]+(t3-t2)*h[i]*m[i+1],0,1)

def color(im,c):
    c=settings(c)
    if c==color_defaults():return im.copy()
    a=np.array(im);rgb=np.empty((*a.shape[:2],3),np.float32);x=np.arange(256)/255
    # Curves are byte-indexed lookup tables, identical to the live preview.
    for i,ch in enumerate(('red','green','blue')):
        lut=curve_values(curve_values(x,c[ch]),c['rgb']).astype(np.float32);rgb[:,:,i]=lut[a[:,:,i]]
    rgb*=np.array([1+c['temperature']*.0015+c['tint']*.0005,1-c['tint']*.001,1-c['temperature']*.0015+c['tint']*.0005],np.float32);np.clip(rgb,0,1,out=rgb)
    lum=rgb@np.array([.2126,.7152,.0722],np.float32)
    delta=(c['shadows']/100*.45*(1-lum)**3+c['highlights']/100*.35*lum**3)[:,:,None]
    rgb=np.clip(rgb+delta,0,1)
    if c['hue'] or c['saturation']:
        import cv2
        hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV);hsv[:,:,0]=(hsv[:,:,0]+c['hue'])%360;hsv[:,:,1]=np.clip(hsv[:,:,1]*(1+c['saturation']/100),0,1)
        rgb=cv2.cvtColor(hsv,cv2.COLOR_HSV2RGB)
    a[:,:,:3]=np.uint8(np.clip(np.rint(rgb*255),0,255));return Image.fromarray(a)

def auto_color(im):
    """Conservative luminance correction; chroma requires distributed neutral evidence."""
    small=im.copy();small.thumbnail((512,512));a=np.array(small);rgb=a[:,:,:3].astype(float)/255
    lum=rgb@np.array([.2126,.7152,.0722]);valid=(a[:,:,3]>240)&(lum>.08)&(lum<.95)
    c=color_defaults()
    # Identity control points keep manual channel curves neutral by default.
    for ch in ('red','green','blue'):c[ch]=[[0,0],[.5,.5],[1,1]]
    if not np.any(valid):return c
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    skin=(r>g*1.02)&(r>b*1.07)&(r-b>.025)&(g>b*.8)
    spread=rgb.max(2)-rgb.min(2)
    neutral=valid&~skin&(lum>.3)&(spread<.14)&(spread/np.maximum(lum,.01)<.24)
    # Require references across brightness ranges, not a single colored background.
    samples=rgb[neutral]
    if len(samples)>max(100,valid.sum()*.08) and np.std(samples.mean(1))>.08:
        estimate=np.median(samples/np.maximum(samples.mean(1,keepdims=True),.01),axis=0)
        if np.max(np.abs(estimate-1))>.035:
            gains=np.clip(1/estimate,.97,1.03)
            for i,ch in enumerate(('red','green','blue')):c[ch][1][1]=float(.5*gains[i])
    vals=lum[valid];mid=float(np.median(vals));low,high=np.quantile(vals,[.05,.95])
    c['shadows']=round(np.clip((.38-mid)*24,-3,8))
    c['highlights']=round(np.clip((.9-high)*35,-7,0))
    # A shared curve adjusts exposure without shifting one color independently.
    delta=float(np.clip((.42-mid)*.12,-.025,.035))
    c['rgb']=[[0,0],[.5,.5+delta],[1,1]]
    return c

def download(url,path,report=lambda s:None):
    import requests
    path=Path(path)
    if path.exists() and path.stat().st_size>1000:return path
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.download')
    try:
        with requests.get(url,stream=True,timeout=(20,90)) as r:
            r.raise_for_status();total=int(r.headers.get('Content-Length',0));n=0
            with temp.open('wb') as f:
                for block in r.iter_content(1024*1024):
                    f.write(block);n+=len(block);report(f'Downloading model: {n//1048576} MB'+(f' / {total//1048576} MB' if total else ''))
        if temp.stat().st_size<1000:raise ValueError('Model download was incomplete')
        temp.replace(path)
    finally:temp.unlink(missing_ok=True)
    return path

def faces(im,models,report=lambda s:None):
    import cv2
    with LOCK:
        path=download('https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',Path(models)/'yunet.onnx',report)
        scale=min(1,1600/max(im.size));w,h=[max(32,round(v*scale)) for v in im.size]
        bgr=cv2.resize(cv2.cvtColor(np.asarray(im.convert('RGB')),cv2.COLOR_RGB2BGR),(w,h))
        key=str(path)
        if key not in FACE_DETECTORS:FACE_DETECTORS[key]=cv2.FaceDetectorYN.create(str(path),'',(w,h),.65,.3,5000)
        detector=FACE_DETECTORS[key];detector.setInputSize((w,h));_,found=detector.detect(bgr)
        if found is None:return []
        return sorted([dict(x=float(f[0]/scale),y=float(f[1]/scale),w=float(f[2]/scale),h=float(f[3]/scale),eye_y=float((f[5]+f[7])/(2*scale)),confidence=float(f[-1]),
                            landmarks=[[float(f[4+2*i]/scale),float(f[5+2*i]/scale)] for i in range(5)]) for f in found],key=lambda f:f['w']*f['h'],reverse=True)

def segment(im,models,engine,report=lambda s:None,accelerate=False):
    if engine not in ('birefnet-general-lite','birefnet-general','birefnet-portrait','u2netp'):raise ValueError('Unknown cutout model')
    alpha=im.getchannel('A')
    key=hashlib.sha256(im.tobytes()+str(im.size).encode()+engine.encode()+b'fresh-alpha-v1').hexdigest()
    cache=cache_dir(support_dir())/'mask-cache'/f'{key}.png'
    if cache.exists():
        report('Reusing this source’s cached subject detection…')
        with Image.open(cache) as cached:return cached.convert('L')
    with LOCK:
        os.environ['U2NET_HOME']=str(Path(models)/'rembg');os.environ.setdefault('OMP_NUM_THREADS','4')
        from rembg import new_session, remove
        report('Loading cutout model. First use downloads model files; this can take several minutes.')
        import onnxruntime as ort
        providers=['CPUExecutionProvider']
        if accelerate and 'CoreMLExecutionProvider' in ort.get_available_providers():providers.insert(0,'CoreMLExecutionProvider')
        session_key=(engine,tuple(providers))
        if session_key not in SESSIONS:
            # Bound resident model memory on production laptops.
            SESSIONS.clear()
            try:SESSIONS[session_key]=new_session(engine,providers=providers)
            except Exception:
                if len(providers)==1:raise
                report('Apple acceleration unavailable for this model; using CPU…')
                SESSIONS[session_key]=new_session(engine,providers=['CPUExecutionProvider'])
        report('Detecting the subject, hair and accessories…')
        try:prediction=remove(Image.alpha_composite(Image.new('RGBA',im.size,'#808080'),im).convert('RGB'),session=SESSIONS[session_key],only_mask=True,post_process_mask=False)
        except Exception:
            if len(providers)==1:raise
            report('Retrying detection on CPU…');SESSIONS[session_key]=new_session(engine,providers=['CPUExecutionProvider'])
            prediction=remove(Image.alpha_composite(Image.new('RGBA',im.size,'#808080'),im).convert('RGB'),session=SESSIONS[session_key],only_mask=True,post_process_mask=False)
        mask=prediction.convert('L').resize(im.size,Image.Resampling.LANCZOS)
        values=np.asarray(mask)
        coverage=float(np.mean(values>127));uncertain=coverage>.985 or coverage<.002
        if uncertain:
            if engine!='birefnet-general':
                report('Selection looks empty or covers the whole image. Retrying General…')
                # Release the reentrant lock safely; alternative session is cached normally.
                return segment(im,models,'birefnet-general',report,accelerate)
            raise ValueError('Subject detection could not separate the foreground. Existing mask preserved; use Keep/Remove or try another source.')
        result=Image.fromarray(np.minimum(np.array(mask),np.array(im.getchannel('A'))))
        cache.parent.mkdir(parents=True,exist_ok=True);temp=cache.with_suffix('.tmp');result.save(temp,format='PNG');temp.replace(cache)
        # Keep the reusable cache bounded; it contains masks only.
        for old in sorted(cache.parent.glob('*.png'),key=lambda f:f.stat().st_mtime,reverse=True)[64:]:old.unlink(missing_ok=True)
        return result

def paint(im,mask,strokes):
    result=mask.copy();unknown=Image.new('L',im.size);ud=ImageDraw.Draw(unknown)
    for stroke in strokes:
        if stroke['mode'] not in ('keep','remove','refine'):raise ValueError('Invalid brush mode')
        pts=[(max(0,min(im.width-1,float(x)*im.width)),max(0,min(im.height-1,float(y)*im.height))) for x,y in stroke['points']]
        if not pts:continue
        polygon=stroke.get('shape')=='polygon'
        if polygon and len(pts)<3:continue
        radius=0 if polygon else max(1,min(400,float(stroke.get('size',30))))/2
        hardness=max(0,min(100,float(stroke.get('hardness',85))))/100
        feather=max(0,min(30,float(stroke.get('feather',0)))) if polygon else radius*(1-hardness)*.45
        # Feather only the affected region; avoid allocating a supersampled full image.
        pad=math.ceil(radius+feather*3+3)
        box=(max(0,math.floor(min(x for x,y in pts))-pad),max(0,math.floor(min(y for x,y in pts))-pad),min(im.width,math.ceil(max(x for x,y in pts))+pad+1),min(im.height,math.ceil(max(y for x,y in pts))+pad+1))
        coverage=Image.new('L',(box[2]-box[0],box[3]-box[1]),0);d=ImageDraw.Draw(coverage)
        local=[(x-box[0],y-box[1]) for x,y in pts]
        if polygon:d.polygon(local,fill=255)
        else:
            d.line(local,fill=255,width=max(1,round(radius*2)),joint='curve')
            for x,y in local:d.ellipse((x-radius,y-radius,x+radius,y+radius),fill=255)
        if stroke['mode']=='refine':unknown.paste(255,box,coverage)
        else:
            if feather:coverage=coverage.filter(ImageFilter.GaussianBlur(feather))
            fill=Image.new('L',coverage.size,255 if stroke['mode']=='keep' else 0)
            result.paste(Image.composite(fill,result.crop(box),coverage),box[:2])
    box=unknown.getbbox()
    if box:
        if im.getchannel('A').getextrema()[0]<255:raise ValueError('Refine Hair needs the original photo with its background. Keep/Remove remain available for transparent sources.')
        x0,y0,x1,y1=box;box=(max(0,x0-40),max(0,y0-40),min(im.width,x1+40),min(im.height,y1+40))
        crop=im.crop(box).convert('RGB');m=result.crop(box);u=unknown.crop(box);scale=min(1,1000/max(crop.size));sz=tuple(max(1,round(v*scale)) for v in crop.size)
        rgb=np.asarray(crop.resize(sz)).astype(float)/255;a=np.asarray(m.resize(sz)).astype(float)/255
        tri=np.where(a>.95,1.,np.where(a<.05,0.,.5));tri[np.asarray(u.resize(sz,Image.Resampling.NEAREST))>0]=.5
        if not (np.any(tri==0) and np.any(tri==1)):raise ValueError('Refine Hair needs kept subject and removed background beside the brushed edge. Add Keep/Remove marks nearby first.')
        from pymatting import estimate_alpha_cf
        alpha=estimate_alpha_cf(rgb,tri);refined=Image.fromarray(np.uint8(np.clip(alpha*255,0,255))).resize(crop.size,Image.Resampling.LANCZOS)
        result.paste(Image.composite(refined,m,u),box[:2])
    return result

def enhance(im,models,scale=2,amount=25,report=lambda s:None,method='neural'):
    import cv2
    if scale not in (1,2,4):raise ValueError('Choose 1×, 2× or 4×')
    if im.width*im.height*scale*scale>MAX_PIXELS:raise ValueError(f'This upscale exceeds the safe processing budget of {MAX_PIXELS//1000000} megapixels. Choose a smaller scale.')
    if method not in ('neural','fast'):raise ValueError('Unknown upscale method')
    out=im.copy();cache=None
    if scale>1:
        key=hashlib.sha256(im.tobytes()+str(im.size).encode()+str(scale).encode()+method.encode()).hexdigest()
        cache=cache_dir(support_dir())/'upscale-cache'/f'{key}.png'
        if cache.exists():
            report('Reusing the upscaled source…')
            return detail(load(cache),amount)
    if scale>1 and method=='fast':
        report('Fast high-quality resize…');out=im.resize((im.width*scale,im.height*scale),Image.Resampling.LANCZOS)
    elif scale>1:
        with LOCK:
            p=download('https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x2.pb',Path(models)/'EDSR_x2.pb',report)
            if str(p) not in UPSCALERS:
                sr=cv2.dnn_superres.DnnSuperResImpl_create();sr.readModel(str(p));sr.setModel('edsr',2);UPSCALERS[str(p)]=sr
            sr=UPSCALERS[str(p)];cv2.setNumThreads(min(4,os.cpu_count() or 2))
            for pass_index in range(int(math.log2(scale))):
                a=cv2.cvtColor(np.asarray(out.convert('RGB')),cv2.COLOR_RGB2BGR);h,w=a.shape[:2];dest=np.empty((h*2,w*2,3),np.uint8)
                tile=192;pad=24;n=0;total=math.ceil(h/tile)*math.ceil(w/tile)
                for y in range(0,h,tile):
                    for x in range(0,w,tile):
                        x1,y1=min(w,x+tile),min(h,y+tile);l,t=max(0,x-pad),max(0,y-pad);r,b=min(w,x1+pad),min(h,y1+pad)
                        pred=sr.upsample(a[t:b,l:r]);dest[y*2:y1*2,x*2:x1*2]=pred[(y-t)*2:(y1-t)*2,(x-l)*2:(x1-l)*2];n+=1
                        report(f'Neural upscale {pass_index+1}/{int(math.log2(scale))}: tile {n}/{total}')
                alpha=out.getchannel('A').resize((w*2,h*2),Image.Resampling.LANCZOS);out=Image.fromarray(cv2.cvtColor(dest,cv2.COLOR_BGR2RGB)).convert('RGBA');out.putalpha(alpha)
    if cache is not None:
        cache.parent.mkdir(parents=True,exist_ok=True);temp=cache.with_suffix('.tmp');out.save(temp,format='PNG',compress_level=1);temp.replace(cache)
        for old in sorted(cache.parent.glob('*.png'),key=lambda p:p.stat().st_mtime,reverse=True)[4:]:old.unlink(missing_ok=True)
    report('Enhancing existing fine detail…')
    return detail(out,amount)


def composite(im,mask,c,applied=True):
    out=color(im,c)
    if mask is not None and applied:out.putalpha(Image.fromarray(np.minimum(np.array(out.getchannel('A')),np.array(mask.resize(im.size)))))
    return out

def render(im,t,canvas):
    w,h=int(canvas['width']),int(canvas['height']);s=float(t['scale']);x=float(t['x']);y=float(t['y'])
    if not 16<=w<=32768 or not 16<=h<=32768 or w*h>MAX_PIXELS or not 0<s<=100 or not all(math.isfinite(v) for v in (s,x,y)):raise ValueError('Invalid canvas or position')
    angle=math.radians(float(t.get('rotation',0)))
    co,si=math.cos(angle),math.sin(angle);cx,cy=im.width/2,im.height/2
    ox,oy=x+s*cx,y+s*cy
    matrix=(co/s,si/s,cx-(co*ox+si*oy)/s,-si/s,co/s,cy+(si*ox-co*oy)/s)
    # Premultiplied resampling avoids colored fringes at transparent boundaries.
    return im.convert('RGBa').transform((w,h),Image.Transform.AFFINE,matrix,resample=Image.Resampling.BICUBIC).convert('RGBA')


def detail(im,amount=50):
    """Luminance detail enhancement with noise threshold and bounded edge overshoot."""
    import cv2
    strength=max(0,min(100,float(amount)))/100
    if not strength:return im.copy()
    a=np.array(im);rgb=a[:,:,:3].astype(np.float32)/255
    y=rgb@np.array([.2126,.7152,.0722],np.float32)
    fine=y-cv2.GaussianBlur(y,(0,0),.75)
    medium=y-cv2.GaussianBlur(y,(0,0),2.0)
    # Estimate noise from low-gradient pixels so skin texture is not over-sharpened.
    gx=cv2.Sobel(y,cv2.CV_32F,1,0);gy=cv2.Sobel(y,cv2.CV_32F,0,1);flat=gx*gx+gy*gy<.0025
    noise=float(np.median(np.abs(fine[flat]))/.6745) if np.count_nonzero(flat)>64 else 0
    threshold=max(.003,min(.015,noise*1.25))
    fine=np.sign(fine)*np.maximum(np.abs(fine)-threshold,0)
    delta=strength*(1.5*fine+.35*medium)
    low=cv2.erode(y,np.ones((3,3),np.uint8))-.008
    high=cv2.dilate(y,np.ones((3,3),np.uint8))+.008
    enhanced=np.clip(y+delta,low,high)
    a[:,:,:3]=np.uint8(np.rint(np.clip(rgb+(enhanced-y)[:,:,None],0,1)*255))
    return Image.fromarray(a)


def refine_edges(im,mask,radius=8,decontaminate=True,report=lambda s:None):
    """Refine only a narrow uncertain boundary, at source resolution in padded tiles."""
    import cv2
    from pymatting import estimate_alpha_cf, estimate_foreground_ml
    if im.getchannel('A').getextrema()[0]<255:
        raise ValueError('Refine edges needs the original photo with its background. This source already has transparency; use Keep/Remove, or reimport the original photo.')
    radius=max(1,min(30,int(radius)))
    a=np.asarray(mask).astype(float)/255
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1))
    fg=cv2.erode((a>.98).astype(np.uint8),kernel)>0
    bg=cv2.erode((a<.02).astype(np.uint8),kernel)>0
    unknown=~(fg|bg)
    if not np.any(fg) or not np.any(bg):raise ValueError('Refine edges needs a kept subject and removed background. Paint Keep and Remove first.')
    rgb=np.asarray(im.convert('RGB')).astype(float)/255
    result=a.copy();colors=rgb.copy();h,w=a.shape;tile=384;pad=max(48,radius*3)
    boxes=[(x,y,min(w,x+tile),min(h,y+tile)) for y in range(0,h,tile) for x in range(0,w,tile) if unknown[y:min(h,y+tile),x:min(w,x+tile)].any()]
    for index,(x,y,x1,y1) in enumerate(boxes):
        report(f'Refining hair transparency: region {index+1}/{len(boxes)}')
        l,t,r,b=max(0,x-pad),max(0,y-pad),min(w,x1+pad),min(h,y1+pad)
        tri=np.where(fg[t:b,l:r],1.,np.where(bg[t:b,l:r],0.,.5))
        if not np.any(tri==0) or not np.any(tri==1):continue
        crop=rgb[t:b,l:r];alpha=estimate_alpha_cf(crop,tri,cg_kwargs={'maxiter':400})
        yy,xx=slice(y-t,y1-t),slice(x-l,x1-l)
        result[y:y1,x:x1]=alpha[yy,xx]
        if decontaminate:
            foreground=estimate_foreground_ml(crop,alpha)
            # Keep the interior's color exact; correct only uncertain edge pixels.
            weight=((tri==.5)&(alpha>.01)&(alpha<.99))[:,:,None]
            colors[y:y1,x:x1]=(foreground*weight+crop*(1-weight))[yy,xx]
    refined=Image.fromarray(np.uint8(np.rint(np.clip(result,0,1)*255)))
    corrected=Image.fromarray(np.uint8(np.rint(np.clip(colors,0,1)*255))).convert('RGBA');corrected.putalpha(im.getchannel('A'))
    return corrected,refined
