import importlib
import sys
import traceback

mods = ['config','fetcher','analyzer','formatter','utils','writer']
failed = []
for m in mods:
    try:
        importlib.import_module(m)
        print('OK', m)
    except Exception:
        print('FAIL', m)
        traceback.print_exc()
        failed.append(m)

if failed:
    print('SMOKE_FAILED', failed)
    sys.exit(2)

print('SMOKE_OK')
