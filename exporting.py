"""Profile-managed output with explicit alpha and metadata handling."""
import io
import json
from PIL import Image, ImageCms, PngImagePlugin
from release import VERSION

SRGB=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))

def validate(fmt,mode,alpha,settings):
    if fmt not in ('JPEG','PNG','TIFF'): raise ValueError('Choose JPEG, PNG or TIFF')
    if mode not in ('RGB','CMYK'): raise ValueError('Choose RGB or CMYK')
    if alpha and fmt=='JPEG': raise ValueError('JPEG cannot retain transparency. Choose PNG or TIFF, or explicitly flatten onto a background.')
    if mode=='CMYK':
        if fmt=='PNG': raise ValueError('PNG requires RGB. Choose TIFF or JPEG for CMYK.')
        if alpha: raise ValueError('CMYK with alpha is not supported. Use RGB TIFF/PNG or explicitly flatten.')
        path=settings.get('print_profile')
        if not path: raise ValueError('Choose a CMYK print ICC profile in Output & Metadata first.')
        try:
            profile=ImageCms.getOpenProfile(path)
            if profile.profile.xcolor_space.strip()!='CMYK': raise ValueError()
        except Exception: raise ValueError('The print profile must be a valid CMYK ICC file.') from None

def metadata(original,policy):
    result={}
    if not original or policy=='strip': return result
    with Image.open(original) as src:
        exif=src.getexif()
        if policy=='copyright':
            keep={315,33432,270};exif=Image.Exif()
            for k,v in src.getexif().items():
                if k in keep: exif[k]=v
        # Geometry was baked into source coordinates at import.
        for k in (274,256,257,40962,40963):
            if k in exif: del exif[k]
        if exif: result['exif']=exif.tobytes()
        xmp=src.info.get('xmp') or src.info.get('XML:com.adobe.xmp')
        if xmp and policy=='preserve': result['xmp']=xmp.encode() if isinstance(xmp,str) else xmp
    return result

def encode(im,fmt,mode,settings,dpi=72,original=None,flatten=False,background='#ffffff'):
    alpha='A' in im.getbands() and im.getchannel('A').getextrema()[0]<255
    if flatten and alpha:
        bg=Image.new('RGBA',im.size,background);bg.alpha_composite(im);im=bg.convert('RGB');alpha=False
    validate(fmt,mode,alpha,settings)
    profile=SRGB
    if mode=='CMYK':
        profile=ImageCms.getOpenProfile(settings['print_profile'])
        im=ImageCms.profileToProfile(im.convert('RGB'),SRGB,profile,outputMode='CMYK')
    elif not alpha: im=im.convert('RGB')
    info=metadata(original,settings.get('metadata_mode','preserve'))
    kwargs=dict(dpi=(dpi,dpi))
    if settings.get('embed_profile',True): kwargs['icc_profile']=profile.tobytes()
    if info.get('exif'): kwargs['exif']=info['exif']
    xmp=info.get('xmp')
    if fmt=='PNG':
        png=PngImagePlugin.PngInfo()
        if xmp: png.add_itxt('XML:com.adobe.xmp',xmp.decode(errors='replace'))
        if settings.get('processing_metadata'): png.add_text('Software','Clarette '+VERSION)
        kwargs['pnginfo']=png
    elif fmt=='TIFF':
        kwargs['compression']=settings.get('tiff_compression','tiff_lzw')
        tags={}
        if xmp: tags[700]=xmp
        if settings.get('processing_metadata'): tags[305]='Clarette '+VERSION
        if tags: kwargs['tiffinfo']=tags
    else:
        kwargs.update(quality=settings.get('jpeg_quality',95),subsampling=0)
        if xmp: kwargs['xmp']=xmp
        if settings.get('processing_metadata'): kwargs['comment']=('Clarette '+VERSION).encode()
    out=io.BytesIO();im.save(out,format=fmt,**kwargs);return out.getvalue()


def installed_cmyk_profiles():
    from pathlib import Path
    result=[];seen=set()
    for root in [Path('/System/Library/ColorSync/Profiles'),Path('/Library/ColorSync/Profiles'),Path.home()/'Library/ColorSync/Profiles']:
        if not root.is_dir():continue
        for path in root.rglob('*'):
            if path.suffix.lower() not in ('.icc','.icm') or not path.is_file():continue
            try:
                real=str(path.resolve())
                if real in seen:continue
                seen.add(real);profile=ImageCms.getOpenProfile(str(path))
                if profile.profile.xcolor_space.strip()=='CMYK':result.append({'path':str(path),'name':ImageCms.getProfileDescription(profile).strip() or path.stem})
            except (OSError,ValueError):continue
    return sorted(result,key=lambda p:p['name'])
