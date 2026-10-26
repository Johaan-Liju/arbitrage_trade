"""Run both services on loopback; stop owned child processes on Ctrl+C."""
from pathlib import Path
import os
import shutil
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
for port in (8000,3000):
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',port))==0:
            raise SystemExit(f'Port {port} is occupied. Stop the existing service first; no process was killed.')
node=shutil.which('node')
if not node:
    raise SystemExit('Node.js is required')
commands=[([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],ROOT),
          ([node,str(ROOT/'frontend/node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port','3000'],ROOT/'frontend')]
children=[]
try:
    for command,cwd in commands:
        children.append(subprocess.Popen(command,cwd=cwd,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
    print('GoldLens: http://127.0.0.1:3000 | API: http://127.0.0.1:8000/api/health',flush=True)
    while all(p.poll() is None for p in children):
        time.sleep(.5)
except KeyboardInterrupt:
    pass
finally:
    for process in children:
        if process.poll() is None:
            process.terminate()
    for process in children:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
