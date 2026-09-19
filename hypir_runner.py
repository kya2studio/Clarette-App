"""HYPIR's optional Python environment. Paths and progress use JSON IPC."""
import json, sys, time
protocol=sys.stdout;sys.stdout=sys.stderr
def emit(**value): protocol.write(json.dumps(value)+'\n');protocol.flush()
model=None
for line in sys.stdin:
    try:
        d=json.loads(line)
        import torch
        from PIL import Image
        from torchvision.transforms.functional import to_tensor
        if model is None:
            emit(progress='Loading HYPIR portrait restoration…')
            sys.path.insert(0,d['config']['repository'])
            from HYPIR.enhancer.sd2 import SD2Enhancer
            torch.set_num_threads(4)
            device='mps' if torch.backends.mps.is_available() else 'cpu'
            model=SD2Enhancer(d['config']['base_model'],d['config']['weights'],'to_k,to_q,to_v,to_out.0,conv,conv1,conv2,conv_shortcut,conv_out,proj_in,proj_out,ff.net.2,ff.net.0.proj'.split(','),256,200,200,device)
            model.weight_dtype=torch.float32
            model.init_models()
        image=Image.open(d['source']).convert('RGBA');scale=int(d['scale'])
        emit(progress='HYPIR: reconstructing portrait detail…')
        torch.manual_seed(231)
        started=time.monotonic()
        restored=model.enhance(to_tensor(image.convert('RGB')).unsqueeze(0),'A natural detailed photograph of the same person, realistic skin and hair texture.',upscale=scale,patch_size=512,stride=256,return_type='pil')[0].convert('RGB')
        size=(image.width*scale,image.height*scale)
        if restored.size!=size: raise ValueError('HYPIR returned unexpected image dimensions')
        baseline=image.resize(size,Image.Resampling.LANCZOS)
        result=Image.blend(baseline.convert('RGB'),restored,float(d['amount'])/100).convert('RGBA')
        result.putalpha(baseline.getchannel('A'));result.save(d['output'])
        emit(done=True,seconds=time.monotonic()-started)
    except Exception as error:
        import traceback
        traceback.print_exc();emit(error=str(error)[:700])
