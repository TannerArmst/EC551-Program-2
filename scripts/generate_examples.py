#!/usr/bin/env python3
"""Recreate the committed example artifacts from their equation sources."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
def generate(name,out,*flags):
    subprocess.run([sys.executable,'hls.py',f'examples/{name}.eqn','--out',f'build/{out}',*flags],cwd=root,check=True)
generate('assignment','demo')
generate('reassignment','reassignment')
generate('sharing','sharing','--const','C=2','--const','D=1')
for mode in ('asap','constrained-asap','alap','constrained-alap','custom'):
    generate('parallel','schedules/'+mode,'--mode',mode)
