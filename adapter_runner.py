"""Entry point executed with an optional engine's own Python, never shell=True."""
import importlib.util,json,sys
from pathlib import Path
protocol=sys.stdout;sys.stdout=sys.stderr

def emit(value):protocol.write(json.dumps(value)+'\n');protocol.flush()
try:
    d=json.loads(Path(sys.argv[1]).read_text());config=d['config'];request=d['request']
    sys.path.insert(0,str(Path(config['entrypoint']).parent))
    spec=importlib.util.spec_from_file_location('clarette_optional_adapter',config['entrypoint']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class CancelToken:
        def check(self):pass # Desktop cancellation terminates this process group.
    result=module.enhance(input_path=request['input_path'],output_dir=request['output_dir'],checkpoint=config['checkpoint'],mode=request['mode'],scale=request['scale'],strength=request['strength'],preserve_identity=request['preserve_identity'],progress_callback=lambda s:emit({'progress':str(s)}),cancel_token=CancelToken())
    path=result.get('output_path') if isinstance(result,dict) else result
    if not isinstance(path,str):raise ValueError('Adapter must return an output image path')
    if not Path(path).is_file():raise ValueError('Adapter output is missing')
    emit({'output_path':path})
except Exception as error:
    emit({'error':str(error)[:700]});sys.exit(1)
