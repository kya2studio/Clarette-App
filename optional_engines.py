"""Optional third-party engines use isolated, explicitly configured runtimes.

The app ships no pretrained third-party diffusion weights. A package's own
adapter implements the documented Clarette request/result protocol.
"""
import json,os,subprocess,sys
from pathlib import Path
from dataclasses import asdict

NAMES={'edsr':'EDSR','hypir':'HYPIR','osediff':'OSEDiff','flowsr':'FlowSR','seesr':'SeeSR'}
SOURCES={'osediff':'https://github.com/cswry/OSEDiff','flowsr':'https://github.com/jiaqixuac/FlowSR','seesr':'https://github.com/cswry/SeeSR','hypir':'https://github.com/XPixelGroup/HYPIR','edsr':'https://github.com/Saafke/EDSR_Tensorflow'}

def package_status(engine,location):
    from managed_engines import installed_path
    managed_root=installed_path(engine)
    root=Path(location).expanduser() if location else managed_root
    managed=root.resolve() in (managed_root.resolve(),(managed_root/'clarette-enhancer.json').resolve())
    ownership=dict(managed=managed,external=not managed,location=str(root))
    manifest=root/'clarette-enhancer.json' if root.is_dir() else root
    if not manifest.is_file():return dict(ownership,status='Missing',message='Adapter manifest not found.',version=None)
    try:
        data=json.loads(manifest.read_text())
        if data.get('api_version')!=1 or data.get('engine')!=engine:raise ValueError('Adapter engine or API version does not match')
        for key in ('entrypoint','checkpoint'):
            p=(manifest.parent/data[key]).resolve()
            if manifest.parent.resolve() not in p.parents or not p.is_file():raise ValueError('Missing '+key+' inside this package')
            data[key]=str(p)
        runtime=Path(data['python']).expanduser()
        if not runtime.is_file() or not os.access(runtime,os.X_OK):raise ValueError('Python runtime is missing or not executable')
        data['python']=str(runtime)
        if data['entrypoint'][-3:]!='.py':raise ValueError('Adapter must be a Python module')
        import platform
        if data.get('platforms') and sys.platform not in data['platforms']:raise ValueError('This package does not support '+sys.platform)
        if data.get('architectures') and platform.machine() not in data['architectures']:raise ValueError('This package does not support '+platform.machine())
        return dict(data,**ownership,status='Ready',message='Experimental adapter configured; inference compatibility is checked on use.',version=data.get('version','Unknown'))
    except (ValueError,KeyError,TypeError,OSError) as e:return dict(ownership,status='Incompatible',message=str(e),version=None)

def statuses(settings,models):
    from providers import restore_status,bundled_restoration_status
    import hypir_engine
    restore_location=settings.get('restore_location','')
    result={'restore':restore_status(restore_location) if restore_location else bundled_restoration_status(),
            'edsr':dict(status='Ready' if (Path(models)/'EDSR_x2.pb').is_file() else 'Download on first use',message='Local neural upscaling with conservative detail.'),
            'hypir':dict(status='Ready' if hypir_engine.available(settings.get('hypir_location','')) else 'Missing',
                        message='Optional experimental restoration. Strength blends with the source.' if hypir_engine.available(settings.get('hypir_location',''))
                        else 'Noncommercial use only under the bundled HYPIR license. For a commercial license, contact jinjin.gu@suppixel.ai.')}
    result.update({k:package_status(k,settings.get(k+'_location','')) for k in ('osediff','flowsr','seesr')})
    return result

class ExternalAdapterProvider:
    def __init__(self,engine):self.engine=engine
    def enhance(self,request,report,cancel_token):
        config=package_status(self.engine,request.model_location)
        if config['status']!='Ready':raise ValueError(config['message'])
        request_file=Path(request.output_dir)/'adapter-request.json'
        request_file.write_text(json.dumps(dict(request=asdict(request),config=config)))
        runner=Path(__file__).with_name('adapter_runner.py')
        report('Starting '+NAMES[self.engine]+' in its configured runtime…');cancel_token.check()
        env=os.environ.copy();env['PYTHONNOUSERSITE']='1';env['HF_HUB_OFFLINE']='1';env['TRANSFORMERS_OFFLINE']='1'
        proc=subprocess.Popen([config['python'],'-u',str(runner),str(request_file)],stdout=subprocess.PIPE,text=True,env=env)
        output=None
        try:
            for line in proc.stdout:
                cancel_token.check()
                try:message=json.loads(line)
                except ValueError:continue
                if message.get('progress'):report(message['progress'])
                if message.get('error'):raise ValueError(message['error'])
                if message.get('output_path'):output=message['output_path']
            if proc.wait()!=0 or not output:raise ValueError(NAMES[self.engine]+' did not return an image. Check its runtime and model package.')
            from imaging import load
            image=load(output)
            # Engine adapters must preserve aspect ratio; normalize before mask restoration.
            from providers import normalize_result
            return normalize_result(image,load(request.input_path))
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

class LocalOSEDiffProvider(ExternalAdapterProvider):
    def __init__(self):super().__init__('osediff')
class LocalFlowSRProvider(ExternalAdapterProvider):
    def __init__(self):super().__init__('flowsr')
class LocalSeeSRProvider(ExternalAdapterProvider):
    def __init__(self):super().__init__('seesr')
