#!/usr/bin/env python3
"""Compute expected SSA values before a board demo (independent of scheduling)."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hls
p=argparse.ArgumentParser()
p.add_argument('equations',type=Path)
p.add_argument('--value',action='append',default=[],metavar='NAME=VALUE')
p.add_argument('--width',type=int,default=16)
p.add_argument('--manifest',type=Path,help='take width and static inputs from generated manifest')
a=p.parse_args()
try:
    program=hls.parse(a.equations.read_text())
    width=a.width
    values={}
    if a.manifest:
        m=json.loads(a.manifest.read_text())
        width=m['width']; values.update(m['board_static_inputs'])
    if not 4<=width<=64: raise hls.HLSError('width must be 4..64')
    for item in a.value:
        name,v=item.split('=',1)
        values[name]=int(v,16 if v.lower().startswith('0x') else 10)
    unknown=set(values)-set(program.input_names)
    missing=set(program.input_names)-set(values)
    if unknown: raise hls.HLSError(f'unknown inputs: {sorted(unknown)}')
    if missing: raise hls.HLSError(f'specify --value for: {sorted(missing)}')
    if any(v<0 or v>=1<<width for v in values.values()): raise hls.HLSError('input out of range')
    env=hls.evaluate(program,values,width)
    for node in program.nodes:
        av,bv=(v if isinstance(v,int) else env[v] for v in (node.a,node.b))
        mask=(1<<width)-1; av&=mask; bv&=mask
        raw=av+bv if node.op=='+' else av-bv if node.op=='-' else av*bv
        if not 0<=raw<=mask:
            print(f'NOTE: {node.dst} wraps at {width} bits (mathematical value {raw}); choose smaller/nonnegative demo values.',file=sys.stderr)
        print(f'{node.dst:20s} = {env[node.dst]:20d} = 0x{env[node.dst]:0{(width+3)//4}X}')
    print('Final outputs:',', '.join(f'{name}={env[s]}' for name,s in program.outputs.items()))
except (OSError,ValueError,KeyError) as exc:
    sys.exit(f'error: {exc}')
