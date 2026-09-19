"""Console-free entry point for the standalone macOS build."""
import os,sys
from pathlib import Path
from support import support_dir
if '--voice-action' in sys.argv:
    sys.stdout=os.fdopen(os.dup(1),'w',buffering=1);sys.stderr=os.fdopen(os.dup(2),'w',buffering=1)
    from voice_actions import main
    main(sys.argv[sys.argv.index('--voice-action')+1:])
elif '--image-worker' in sys.argv:
    # Windowed bootloaders may set Python streams to None; OS pipes still exist.
    sys.stdin=os.fdopen(os.dup(0),'r');sys.stdout=os.fdopen(os.dup(1),'w',buffering=1)
    support=support_dir();support.mkdir(parents=True,exist_ok=True)
    sys.stderr=open(support/'engine.log','a',buffering=1)
    from image_worker import worker_main
    worker_main()
else:
    support=support_dir();support.mkdir(parents=True,exist_ok=True)
    sys.stdout=sys.stderr=(support/'clarette.log').open('a',buffering=1)
    import app
    sys.argv=[sys.argv[0],'--native']+sys.argv[1:]
    app.main()
