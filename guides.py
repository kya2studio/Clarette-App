"""Normalized output guides and uniform, landmark-aware headshot fitting."""
import math

def guide_for(canvas):
    return dict(canvas.get('guide') or dict(cx=.5,top=canvas.get('headTop',.035),width=canvas.get('headW',.255),height=min(.95,canvas['width']*canvas.get('headW',.255)*1.18/canvas['height']),eyes=.45))

def validate_guide(value):
    g={k:float(value[k]) for k in ('cx','top','width','height','eyes')}
    if not all(math.isfinite(v) for v in g.values()) or not .03<=g['width']<=1 or not .03<=g['height']<=1 or not .1<=g['eyes']<=.9 or g['cx']-g['width']/2<0 or g['cx']+g['width']/2>1 or g['top']<0 or g['top']+g['height']>1.000001:raise ValueError('Keep the face guide inside the output canvas')
    return g

def fit_face(face,canvas):
    g=guide_for(canvas);w,h=canvas['width'],canvas['height']
    eye=face.get('eye_y',face['y']+face['h']*.4);chin=face['y']+face['h']
    target_chin=(g['top']+g['height'])*h
    s=min(g['width']*w/face['w'],g['height']*(1-g['eyes'])*h/max(1,chin-eye))
    return dict(scale=s,x=g['cx']*w-(face['x']+face['w']/2)*s,y=target_chin-chin*s)

def preset_key(canvas):
    return canvas.get('preset_id') or f"{canvas['width']}x{canvas['height']}"
