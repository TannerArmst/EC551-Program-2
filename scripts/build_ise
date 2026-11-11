#!/usr/bin/env python3
"""Nexys 3 batch synthesis/place/route/bitstream using an installed ISE 14.7.
Run in an ISE command shell so xst/ngdbuild/map/par/trce/bitgen are on PATH.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
p=argparse.ArgumentParser()
p.add_argument('build',type=Path)
a=p.parse_args()
source=a.build.resolve()
repo=Path(__file__).resolve().parents[1]
work=source/'fpga_build'/'ise'
work.mkdir(parents=True,exist_ok=True)
part='xc6slx16-3-csg324'
commands=['xst','ngdbuild','map','par','trce','bitgen']
for command in commands:
    if not shutil.which(command): sys.exit(f'{command} missing: use an ISE 14.7 command shell')
# Copy into a fixed-name workspace to avoid path/space quoting in XST project files.
files=(source/'sources.f').read_text().splitlines()
for file in files: shutil.copyfile(source/file,work/file)
shutil.copyfile(repo/'constraints'/'nexys3.ucf',work/'board.ucf')
(work/'project.prj').write_text(''.join(f'verilog work "{f}"\n' for f in files))
(work/'synth.xst').write_text(f'run\n-ifn project.prj\n-ifmt mixed\n-ofn top\n-ofmt NGC\n-p {part}\n-top nexys3_top\n-opt_mode Speed\n-opt_level 1\n')
def run(argv):
    print('Running',' '.join(argv),flush=True)
    subprocess.run(argv,cwd=work,check=True)
run(['xst','-ifn','synth.xst','-ofn','synthesis.log'])
run(['ngdbuild','-p',part,'-uc','board.ucf','top.ngc','top.ngd'])
run(['map','-w','-p',part,'-o','mapped.ncd','top.ngd','top.pcf'])
run(['par','-w','mapped.ncd','routed.ncd','top.pcf'])
run(['trce','-v','10','-o','timing.twr','routed.ncd','top.pcf'])
run(['bitgen','-w','routed.ncd','nexys3_top.bit'])
print(f'Generated {work}/nexys3_top.bit. Read timing.twr; require all constraints met before programming.')
