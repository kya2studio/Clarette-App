"""Persistent, cancellable image engine. JSON IPC carries paths, never image buffers."""
import atexit, json, os, queue, signal, subprocess, sys, threading
from pathlib import Path

class Cancelled(Exception): pass

class ImageWorker:
    def __init__(self):
        self.proc=None
        self.lock=threading.Lock()
        self.lifecycle_lock=threading.RLock()
        self.stop_requested=threading.Event()
        atexit.register(self.close)
    def shutdown(self):
        self.stop_requested.set()
        self.close()
    def close(self):
        # Serialize spawn, IPC writes, and teardown. A concurrent closer must
        # wait for the same child to exit rather than losing its process handle.
        with self.lifecycle_lock:
            proc=self.proc
            if not proc:return
            try:
                if proc.poll() is None:
                    # Idle workers exit normally on EOF. Busy native inference
                    # gets a bounded chance to finish before process-group stop.
                    try:proc.stdin.close()
                    except (OSError,ValueError):pass
                    try:proc.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        try:os.killpg(proc.pid,signal.SIGTERM) if os.name=='posix' else proc.terminate()
                        except ProcessLookupError:pass
                        try:proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            try:os.killpg(proc.pid,signal.SIGKILL) if os.name=='posix' else proc.kill()
                            except ProcessLookupError:pass
                            proc.wait(timeout=1)
                for stream in (proc.stdin,proc.stdout):
                    if stream:
                        try:stream.close()
                        except (OSError,ValueError):pass
            finally:self.proc=None
    def call(self,request,report):
        with self.lock:
            try:
                with self.lifecycle_lock:
                    report.check()
                    if self.stop_requested.is_set():raise Cancelled('Clarette is closing. Previous edits are preserved.')
                    if not self.proc or self.proc.poll() is not None:
                        self.close()
                        env=os.environ.copy()
                        for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
                            env[key]=str(min(4,os.cpu_count() or 2))
                        command=([sys.executable,'--image-worker'] if getattr(sys,'frozen',False)
                                 else [sys.executable,'-u',str(Path(__file__).resolve())])
                        self.proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1,env=env,start_new_session=(os.name=='posix'))
                        self.messages=queue.Queue()
                        def read(proc,messages):
                            try:
                                for line in proc.stdout:
                                    try: messages.put(json.loads(line))
                                    except ValueError: pass
                            finally: messages.put({'error':'The image engine stopped unexpectedly. Your edits are preserved. Try again with the Fast preview model.'})
                        threading.Thread(target=read,args=(self.proc,self.messages),daemon=True).start()
                    proc,messages=self.proc,self.messages
                    proc.stdin.write(json.dumps(request)+'\n');proc.stdin.flush()
                while True:
                    report.check()
                    if self.stop_requested.is_set():raise Cancelled('Clarette is closing. Previous edits are preserved.')
                    try: item=messages.get(timeout=.1)
                    except queue.Empty: continue
                    if 'progress' in item: report(item['progress'])
                    elif 'error' in item: raise RuntimeError(item['error'])
                    else: return item['result']
            except (Cancelled,BrokenPipeError):
                self.close();raise

def worker_main():
    # Keep native-library messages away from the IPC stream.
    protocol=sys.stdout;sys.stdout=sys.stderr
    import imaging
    from PIL import Image
    import cv2
    cv2.setNumThreads(2)
    def send(item): protocol.write(json.dumps(item)+'\n');protocol.flush()
    def report(message): send({'progress':message})
    for line in sys.stdin:
        try:
            d=json.loads(line);op=d['op'];out=Path(d['output']);out.mkdir(parents=True,exist_ok=True)
            report('Reading source pixels…');im=imaging.load(d['source']);models=Path(d['models'])
            m=None
            if op in ('/api/mask-paint','/api/refine-edges'):
                m=Image.open(d['mask']).convert('L') if d.get('mask') else Image.new('L',im.size,0)
            result={}
            if op=='/api/color-auto':
                report('Balancing headshot color…');result={'color':imaging.auto_color(im)}
            elif op=='/api/cloud-enhance':
                from cloud import enhance
                rgb=enhance(imaging.color(im,d['color']),d['provider'],d['cloud_model'],d['prompt'],report)
                rgb.save(out/'work.png');result={'work':str(out/'work.png')}
            elif op in ('/api/detect','/api/crop-suggest'):

                result={'faces':imaging.faces(im,models,report)}
            elif op=='/api/mask-detect':
                matte=imaging.segment(im,models,d['model'],report,d.get('accelerate',False));result={}
                if d.get('quality_cutout',False) and im.getchannel('A').getextrema()[0]==255:
                    try:
                        _,matte=imaging.refine_edges(im,matte,radius=4,decontaminate=False,report=report)
                    except ValueError as error:
                        report('Keeping detected mask: '+str(error))
                matte.save(out/'mask.png');result['mask']=str(out/'mask.png')
                if d.get('auto_guide',True):
                    try:
                        report('Checking headshot composition…');result['faces']=imaging.faces(im,models,report)
                    except Exception: result['guide_unavailable']=True
            elif op=='/api/mask-paint':
                report('Updating mask…');matte=imaging.paint(im,m,d.get('strokes',[]));matte.save(out/'mask.png');result={'mask':str(out/'mask.png')}
            elif op=='/api/refine-edges':
                rgb,matte=imaging.refine_edges(imaging.color(im,d['color']),m,d.get('radius',8),d.get('decontaminate',True),report)
                rgb.save(out/'work.png');matte.save(out/'mask.png');result={'work':str(out/'work.png'),'mask':str(out/'mask.png')}
            elif op=='/api/enhance':
                if d.get('enhancement_provider')=='hypir':
                    import hypir_engine
                    rgb=hypir_engine.enhance(imaging.color(im,d['color']),int(d.get('scale',1)),int(d.get('amount',35)),report,location=d.get('engine_location',''))
                elif d.get('enhancement_provider') in ('osediff','flowsr','seesr'):
                    from optional_engines import ExternalAdapterProvider
                    from providers import EnhanceRequest
                    prepared=out/'input.png';imaging.color(im,d['color']).save(prepared)
                    class CancelToken:
                        def check(self):pass
                    rgb=ExternalAdapterProvider(d['enhancement_provider']).enhance(EnhanceRequest(str(prepared),str(out),int(d.get('scale',1)),float(d.get('amount',35))/100,model_location=d.get('engine_location','')),report,CancelToken())
                elif d.get('enhancement_provider')=='restore':
                    restore_location=d.get('restore_location','')
                    if restore_location:
                        from providers import LocalClaretteRestoreProvider,EnhanceRequest
                        prepared=out/'input.png';imaging.color(im,d['color']).save(prepared)
                        class CancelToken:
                            def check(self):pass # Parent cancellation terminates the isolated process group.
                        rgb=LocalClaretteRestoreProvider().enhance(EnhanceRequest(str(prepared),str(out),int(d.get('scale',1)),float(d.get('amount',35))/100,model_location=restore_location),report,CancelToken())
                    else:
                        # No custom-trained adapter configured: use the general-purpose
                        # Real-ESRGAN model bundled with the app (models/RealESRGAN_x4plus.onnx).
                        import restoration
                        scale=int(d.get('scale',1))
                        rgb=restoration.restore(imaging.color(im,d['color']),scale=scale if scale in (1,2,4) else 2,strength=int(d.get('amount',35)),report=report,accelerate=d.get('accelerate',False))
                else:
                    rgb=imaging.enhance(imaging.color(im,d['color']),models,int(d.get('scale',1)),int(d.get('amount',35)),report,method='neural' if d.get('enhancement_provider')=='edsr' else d.get('method','fast'))
                if d.get('face_restore'):
                    # Optional additional pass, same idea as Real-ESRGAN's own --face_enhance flag:
                    # sharpen/upscale the whole photo above, then separately restore just the face.
                    report('Restoring face detail…')
                    faces=imaging.faces(rgb,models,report)
                    if faces:
                        import face_restore
                        rgb=face_restore.restore_face(rgb,faces[0]['landmarks'],strength=int(d.get('amount',35)),accelerate=d.get('accelerate',False))
                rgb.save(out/'work.png');result={'work':str(out/'work.png')}
            else: raise ValueError('Unknown image operation')
            report('Preparing preview…');send({'result':result})
        except Exception as e:
            import traceback
            traceback.print_exc();send({'error':str(e)[:700]})

if __name__=='__main__':worker_main()
