#!/usr/bin/env python3
"""Run Python tests and (when installed) generated RTL simulations."""
import argparse
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hls

def run(args,cwd=ROOT):
    subprocess.run(args,cwd=cwd,check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--require-rtl',action='store_true',help='fail rather than skip missing Icarus')
    ap.add_argument('--random-rtl',type=int,default=8)
    a=ap.parse_args()
    run([sys.executable,'-m','unittest','discover','-s','tests','-v'])
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        if a.require_rtl: sys.exit('Icarus missing: cannot run required RTL checks')
        print('SKIP RTL: install iverilog and vvp; Python tests passed.')
        return
    count=0
    with tempfile.TemporaryDirectory() as d:
        d=Path(d)
        cases=[(f.stem,f.read_text()) for f in sorted((ROOT/'examples').glob('*.eqn'))]
        rng=random.Random(77551)
        for trial in range(a.random_rtl):
            names=['A','B','C']
            eq=[]
            for i in range(20):
                dst=rng.choice(['X','Y','Z'])
                eq.append(f'{dst}={rng.choice(names)}{rng.choice("+-*")}{rng.choice(names)}')
                if dst not in names: names.append(dst)
            cases.append((f'random{trial}','\n'.join(eq)))
        for name,text in cases:
            p=hls.parse(text)
            for mode in hls.MODES:
                t,l,c=hls.schedule(p,mode,{'add':1,'sub':1,'mul':1})
                target=d/f'{name}_{mode}'
                width=[4,8,16,32,64][count%5]
                hls.emit(p,t,l,c,mode,width,target,vectors=5)
                hls.simulate(target)
                count+=1
        # A padded backward schedule exercises leading idle phases.
        p=hls.parse('X=A+B\nY=X*B')
        t,l,c=hls.schedule(p,'constrained-alap',latency=7)
        hls.emit(p,t,l,c,'constrained-alap',16,d/'padded',vectors=4)
        hls.simulate(d/'padded'); count+=1
        # Full board runtime against the exact assignment example.
        p=hls.parse((ROOT/'examples'/'assignment.eqn').read_text())
        t,l,c=hls.schedule(p)
        target=d/'board'
        hls.emit(p,t,l,c,'constrained-asap',16,target,vectors=1)
        run(['iverilog','-g2005','-Wall','-s','board_testbench','-o','board.vvp',
             *(target/'sources.f').read_text().splitlines(),str(ROOT/'tests'/'board_testbench.v')],cwd=target)
        run(['vvp','board.vvp'],cwd=target)
        # Both physical wrappers must elaborate independently.
        for top in ('nexys3_top','nexys_a7_top'):
            run(['iverilog','-g2005','-Wall','-s',top,'-o',top+'.vvp',
                 *(target/'sources.f').read_text().splitlines()],cwd=target)
    print(f'PASS: Python tests, {count} generated RTL simulations, board integration, both board wrappers')

if __name__=='__main__': main()
