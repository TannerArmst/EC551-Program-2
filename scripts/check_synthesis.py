#!/usr/bin/env python3
"""Generic synthesis check; this does not replace FPGA place/route and timing."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
p=argparse.ArgumentParser()
p.add_argument('build',type=Path)
p.add_argument('--top',choices=['hls_core','nexys3_top','nexys_a7_top'],default='hls_core')
a=p.parse_args()
if not shutil.which('yosys'):
    sys.exit('Install yosys to run this check.')
root=a.build.resolve()
files=(root/'sources.f').read_text().splitlines()
# File names here are compiler-owned constants, never equation text.
script='read_verilog '+' '.join(files)+f'; hierarchy -check -top {a.top}; proc; opt; check -assert; synth -top {a.top}; check -assert; stat'
with (root/f'synthesis_{a.top}.log').open('w') as log:
    result=subprocess.run(['yosys','-p',script],cwd=root,stdout=log,stderr=subprocess.STDOUT)
print(f'Synthesis log: {root}/synthesis_{a.top}.log')
sys.exit(result.returncode)
