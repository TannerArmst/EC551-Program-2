#!/usr/bin/env python3
"""EC551 HLS: sequential equations -> SSA DAG -> schedule/binding -> Verilog-2001.
No Python dependencies. All arithmetic units have one enabled-cycle latency.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys

KINDS = {'+': 'add', '-': 'sub', '*': 'mul'}
MODES = ('asap', 'constrained-asap', 'alap', 'constrained-alap', 'custom')
ATOM = r'(?:[A-Za-z_][A-Za-z_0-9]*|0[xX][0-9A-Fa-f]+|[0-9]+)'
EQUATION = re.compile(rf'^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*({ATOM})\s*([+*-])\s*({ATOM})\s*;?$')

class HLSError(ValueError):
    pass

@dataclass(frozen=True)
class Node:
    id: int
    original: str
    dst: str
    a: str | int
    op: str
    b: str | int
    deps: tuple[int, ...]

@dataclass
class Program:
    nodes: list[Node]
    inputs: list[str]  # SSA names, first-use order
    input_names: list[str]
    outputs: dict[str, str]  # last assigned version of EACH destination

    def ssa(self):
        return '\n'.join(f'{n.dst} = {n.a} {n.op} {n.b}' for n in self.nodes) + '\n'


def parse(text: str) -> Program:
    versions, current, producer = {}, {}, {}
    nodes, inputs, names = [], [], []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#', 1)[0].split('//', 1)[0].strip()
        if not line:
            continue
        m = EQUATION.fullmatch(line)
        if not m:
            raise HLSError(f'line {line_no}: expected DEST = ARG (+|-|*) ARG; got {line!r}')
        if len(nodes) == 20:
            raise HLSError('maximum of 20 equations exceeded')
        lhs, a, op, b = m.groups()
        def resolve(token):
            if token[0].isdigit():
                return int(token, 16 if token.lower().startswith('0x') else 10)
            if token not in current:
                current[token] = token + '_0'
                inputs.append(current[token])
                names.append(token)
            return current[token]
        # Resolve BOTH operands before updating lhs (X=X+1 reads old X).
        aa, bb = resolve(a), resolve(b)
        versions[lhs] = versions.get(lhs, 0) + 1
        dst = f'{lhs}_{versions[lhs]}'
        deps = tuple(sorted({producer[x] for x in (aa, bb) if x in producer}))
        nodes.append(Node(len(nodes), lhs, dst, aa, op, bb, deps))
        current[lhs] = dst
        producer[dst] = nodes[-1].id
    if not nodes:
        raise HLSError('input contains no equations')
    outputs = {n.original: current[n.original] for n in nodes}
    return Program(nodes, inputs, names, outputs)


def graph(p):
    successors = {n.id: [] for n in p.nodes}
    for n in p.nodes:
        for d in n.deps:
            successors[d].append(n.id)
    earliest, height = {}, {}
    for n in p.nodes:
        earliest[n.id] = 1 + max((earliest[d] for d in n.deps), default=0)
    for n in reversed(p.nodes):
        height[n.id] = 1 + max((height[s] for s in successors[n.id]), default=0)
    return successors, earliest, height


def schedule(p, mode='constrained-asap', limits=None, latency=None):
    if mode not in MODES:
        raise HLSError(f'unknown schedule mode {mode}')
    if latency is not None and not 1 <= latency <= 4095:
        raise HLSError('latency bound must be between 1 and 4095')
    constrained = mode in ('constrained-asap', 'constrained-alap', 'custom')
    limits = dict(limits or {})
    if any(k not in KINDS.values() for k in limits):
        raise HLSError('unknown resource type')
    caps = {k: limits.get(k, 1) if constrained else 20 for k in KINDS.values()}
    if any(type(v) is not int or v < 0 for v in caps.values()):
        raise HLSError('resource limits must be nonnegative integers')
    for n in p.nodes:
        if caps[KINDS[n.op]] == 0:
            raise HLSError(f'program requires a {KINDS[n.op]} but its limit is zero')
    succ, earliest, height = graph(p)
    critical = max(earliest.values())
    if latency is not None and latency < critical:
        raise HLSError(f'latency {latency} is below critical path {critical}')
    times, pending = {}, set(range(len(p.nodes)))
    backward = mode in ('alap', 'constrained-alap')
    t = 1
    while pending:
        used = Counter()
        # times are distance from end in the backward scheduler.
        ready = [i for i in pending if all(d in times and times[d] < t
                  for d in (succ[i] if backward else p.nodes[i].deps))]
        if mode == 'custom':
            # Longest remaining path first; high fanout breaks ties.
            ready.sort(key=lambda i: (-height[i], -len(succ[i]), i))
        else:
            ready.sort(reverse=backward)
        for i in ready:
            k = KINDS[p.nodes[i].op]
            if used[k] < caps[k]:
                times[i] = t
                used[k] += 1
                pending.remove(i)
        t += 1
    length = max(times.values())
    if latency is not None and length > latency:
        raise HLSError(f'{mode} needs {length} cycles, exceeding bound {latency}; '
                       'try custom scheduling or a larger bound (list scheduling is heuristic)')
    if backward:
        length = latency or length
        times = {i: length + 1 - c for i, c in times.items()}
    # Forward modes interpret --latency as a maximum, without trailing padding.
    validate(p, times, caps)
    return times, length, caps


def validate(p, times, caps):
    if set(times) != {n.id for n in p.nodes}:
        raise HLSError('schedule must contain every node exactly once')
    use = Counter()
    for n in p.nodes:
        if times[n.id] < 1 or any(times[d] >= times[n.id] for d in n.deps):
            raise HLSError('invalid dependency ordering')
        use[times[n.id], KINDS[n.op]] += 1
    if any(v > caps[k] for (_, k), v in use.items()):
        raise HLSError('resource limit violated')


def bind(p, times):
    used, binding, peaks = Counter(), {}, Counter()
    for n in sorted(p.nodes, key=lambda n: (times[n.id], n.id)):
        k = KINDS[n.op]
        unit = used[times[n.id], k]
        binding[n.id] = (k, unit)
        used[times[n.id], k] += 1
        peaks[k] = max(peaks[k], unit + 1)
    return binding, {k: peaks[k] for k in KINDS.values()}


def evaluate(p, values, width=16):
    mask = (1 << width) - 1
    env = {ssa: values[name] & mask for name, ssa in zip(p.input_names, p.inputs)}
    for n in p.nodes:
        a, b = (x if isinstance(x, int) else env[x] for x in (n.a, n.b))
        a, b = a & mask, b & mask
        env[n.dst] = {'+': lambda: a+b, '-': lambda: a-b, '*': lambda: a*b}[n.op]() & mask
    return env


def literal(w, n):
    return f"{w}'h{n & ((1 << w)-1):x}"


def emit(p, times, length, caps, mode, width, out, constants=None, switch_inputs=None, seed=551, vectors=24):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    constants = constants or {}
    if not 4 <= width <= 64:
        raise HLSError('bit width must be between 4 and 64')
    if vectors < 1 or vectors > 1000:
        raise HLSError('--vectors must be between 1 and 1000')
    if any(name not in p.input_names for name in constants):
        raise HLSError('--const names must be external inputs (see input_names in manifest)')
    if any(v < 0 or v >= (1 << width) for v in constants.values()):
        raise HLSError('constant input does not fit selected width')
    selected = switch_inputs if switch_inputs is not None else [x for x in p.input_names if x not in constants][:2]
    if len(selected) > 2 or len(set(selected)) != len(selected) or any(x not in p.input_names or x in constants for x in selected):
        raise HLSError('--switch-inputs must be at most two distinct external inputs without --const')
    initial = {name: constants.get(name, 1) for name in p.input_names}
    binding, peaks = bind(p, times)
    units = [(k, u) for k in KINDS.values() for u in range(peaks[k])]
    reg_names = {name: f'r{i}' for i, name in enumerate(p.inputs + [n.dst for n in p.nodes])}
    ni, no = max(1, len(p.inputs)), len(p.outputs)
    phase_width = max(1, (length+1).bit_length())
    manifest = dict(width=width, mode=mode, latency=length, critical_path=max(graph(p)[1].values()),
                    resource_limits=caps, resources_instantiated=peaks,
                    input_names=p.input_names, input_ssa=p.inputs, outputs=p.outputs,
                    board_switch_inputs=selected, board_static_inputs={k:v for k,v in initial.items() if k not in selected},
                    arithmetic='unsigned modulo 2**width, one enabled cycle per operation',
                    units=[{'selector':i, 'type':k, 'instance':u} for i,(k,u) in enumerate(units)],
                    register_selectors=[{'selector':i, 'ssa':n.dst} for i,n in enumerate(p.nodes)],
                    schedule=[dict(id=n.id, dst=n.dst, a=n.a, op=n.op, b=n.b, deps=n.deps,
                                   cycle=times[n.id], unit=f'{binding[n.id][0]}{binding[n.id][1]}') for n in p.nodes])
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (out/'ssa.txt').write_text(p.ssa())
    rows = ['cycle,node,equation,functional_unit']
    for n in sorted(p.nodes, key=lambda n:(times[n.id], n.id)):
        rows.append(f'{times[n.id]},{n.id},{n.dst}={n.a}{n.op}{n.b},{binding[n.id][0]}{binding[n.id][1]}')
    (out/'schedule.csv').write_text('\n'.join(rows)+'\n')
    dot = ['digraph DAG {', 'rankdir=TB;']
    # Quote all user-derived identifiers as JSON strings in DOT.
    for s in p.inputs:
        dot.append(f'{json.dumps(s)} [shape=box,label={json.dumps(s+" (input)")}];')
    for n in p.nodes:
        label = f'{n.dst} = {n.a} {n.op} {n.b} | cycle {times[n.id]} | {binding[n.id][0]}{binding[n.id][1]}'
        dot.append(f'{json.dumps(n.dst)} [label={json.dumps(label)}];')
        for a in dict.fromkeys((n.a, n.b)):
            if isinstance(a, str):
                dot.append(f'{json.dumps(a)} -> {json.dumps(n.dst)};')
    dot.append('}')
    (out/'dag.dot').write_text('\n'.join(dot)+'\n')
    root = Path(__file__).resolve().parent
    for file in ('functional_units.v', 'board_support.v'):
        shutil.copyfile(root/'rtl'/file, out/file)

    # Explicit sequencer. phase=0 idle, 1..L scheduled states, L+1 complete.
    control = f'''`timescale 1ns/1ps
module hls_control(input clk, input rst, input start, input en,
    output reg busy, output reg done, output reg [{phase_width-1}:0] phase);
always @(posedge clk) begin
    if (rst) begin busy <= 0; done <= 0; phase <= 0; end
    else if (start && !busy) begin busy <= 1; done <= 0; phase <= 1; end
    else if (busy && en) begin
        if (phase == {length}) begin busy <= 0; done <= 1; phase <= {length+1}; end
        else phase <= phase + 1'b1;
    end
end
endmodule
'''
    (out/'hls_control.v').write_text(control)
    dp = [f'''`timescale 1ns/1ps
module hls_datapath(input clk, input rst, input load, input advance,
    input [{phase_width-1}:0] phase, input [{ni*width-1}:0] inputs_bus,
    input [5:0] debug_sel, output [{no*width-1}:0] outputs_bus,
    output reg [{width-1}:0] fu_debug, output reg [{width-1}:0] reg_debug);''']
    dp += [f'reg [{width-1}:0] {r}; // {ssa}' for ssa,r in reg_names.items()]
    for k,u in units:
        dp += [f'reg [{width-1}:0] {k}{u}_a, {k}{u}_b;',
               f'wire [{width-1}:0] {k}{u}_y;',
               f'reg [{width-1}:0] {k}{u}_last;',
               f'hls_{k} #(.W({width})) fu_{k}{u}(.a({k}{u}_a), .b({k}{u}_b), .y({k}{u}_y));']
    def ref(a):
        return literal(width, a) if isinstance(a,int) else reg_names[a]
    dp += ['// Operand muxes share each physical FU across scheduled operations.', 'always @* begin']
    for k,u in units:
        dp += [f'  {k}{u}_a = 0; {k}{u}_b = 0;']
    dp += ['  case (phase)']
    for c in range(1,length+1):
        dp += [f'    {c}: begin']
        for n in p.nodes:
            if times[n.id] == c:
                k,u = binding[n.id]
                dp += [f'      {k}{u}_a = {ref(n.a)}; {k}{u}_b = {ref(n.b)};']
        dp += ['    end']
    dp += ['    default: begin end', '  endcase', 'end',
           'always @(posedge clk) begin', '  if (rst) begin']
    dp += [f'    {r} <= 0;' for r in reg_names.values()]
    dp += [f'    {k}{u}_last <= 0;' for k,u in units]
    dp += ['  end else if (load) begin']
    for i,s in enumerate(p.inputs):
        dp += [f'    {reg_names[s]} <= inputs_bus[{i*width} +: {width}];']
    dp += [f'    {reg_names[n.dst]} <= 0;' for n in p.nodes]
    dp += [f'    {k}{u}_last <= 0;' for k,u in units]
    dp += ['  end else if (advance) begin', '    case (phase)']
    for c in range(1,length+1):
        dp += [f'      {c}: begin']
        for n in p.nodes:
            if times[n.id] == c:
                k,u = binding[n.id]
                dp += [f'        {reg_names[n.dst]} <= {k}{u}_y; // {n.dst}',
                       f'        {k}{u}_last <= {k}{u}_y;']
        dp += ['      end']
    dp += ['      default: begin end', '    endcase', '  end', 'end']
    dp += [f'assign outputs_bus[{i*width} +: {width}] = {reg_names[s]}; // {name}'
           for i,(name,s) in enumerate(p.outputs.items())]
    dp += ['// Hold each FU\'s last committed result for inspection between button presses.',
           'always @* begin', '  fu_debug = 0; reg_debug = 0;', '  case (debug_sel)']
    dp += [f'    {i}: fu_debug = {k}{u}_last;' for i,(k,u) in enumerate(units)]
    dp += ['    default: fu_debug = 0;', '  endcase', '  case (debug_sel)']
    dp += [f'    {i}: reg_debug = {reg_names[n.dst]}; // {n.dst}' for i,n in enumerate(p.nodes)]
    dp += ['    default: reg_debug = 0;', '  endcase', 'end', 'endmodule']
    (out/'hls_datapath.v').write_text('\n'.join(dp)+'\n')
    core = f'''`timescale 1ns/1ps
module hls_core(input clk, input rst, input start, input en,
    input [{ni*width-1}:0] inputs_bus, input [5:0] debug_sel,
    output busy, output done, output [{no*width-1}:0] outputs_bus,
    output [{width-1}:0] fu_debug, output [{width-1}:0] reg_debug,
    output [{phase_width-1}:0] phase);
hls_control ctrl(.clk(clk), .rst(rst), .start(start), .en(en),
    .busy(busy), .done(done), .phase(phase));
hls_datapath dp(.clk(clk), .rst(rst), .load(start && !busy),
    .advance(en && busy), .phase(phase), .inputs_bus(inputs_bus),
    .debug_sel(debug_sel), .outputs_bus(outputs_bus), .fu_debug(fu_debug), .reg_debug(reg_debug));
endmodule
'''
    (out/'hls_core.v').write_text(core)
    board = [f'''`timescale 1ns/1ps
// Nexys A7-100T runtime with an 8-switch, 4-digit interface.
module board_runtime #(parameter DEBOUNCE=2000000)(input clk,
    input [7:0] sw, input btn_reset, input btn_start, input btn_step, input btn_run,
    output [7:0] led, output [6:0] seg, output [3:0] an, output dp);
reg [7:0] por = 0;
always @(posedge clk) if (!(&por)) por <= por + 1'b1;
wire power_reset = !(&por);
wire reset_level, reset_pulse, start_level, start_pulse, step_level, step_pulse, run_level, run_pulse;
button_filter #(.COUNT(DEBOUNCE)) br(clk, power_reset, btn_reset, reset_level, reset_pulse);
wire rst = power_reset | reset_level;
button_filter #(.COUNT(DEBOUNCE)) bs(clk, rst, btn_start, start_level, start_pulse);
button_filter #(.COUNT(DEBOUNCE)) bt(clk, rst, btn_step, step_level, step_pulse);
button_filter #(.COUNT(DEBOUNCE)) bu(clk, rst, btn_run, run_level, run_pulse);
(* ASYNC_REG = "TRUE" *) reg [7:0] sw_meta, sw_sync;
always @(posedge clk) begin
    if (rst) begin sw_meta <= 0; sw_sync <= 0; end
    else begin sw_meta <= sw; sw_sync <= sw_meta; end
end
wire busy, done;
wire [{phase_width-1}:0] phase;
wire [{width-1}:0] fu_debug, reg_debug;
wire [{no*width-1}:0] outputs_bus;
wire [{ni*width-1}:0] inputs_bus;
reg auto_run;
always @(posedge clk) begin
    if (rst) auto_run <= 0;
    else if (!busy) auto_run <= 0;
    else if (run_pulse) auto_run <= 1;
end
''']
    if not p.inputs:
        board += ['assign inputs_bus = 0;']
    for i,name in enumerate(p.input_names):
        val = f'sw_sync[{selected.index(name)*4} +: 4]' if name in selected else literal(width,initial[name])
        board += [f'assign inputs_bus[{i*width} +: {width}] = {val}; // {name}']
    board += [f'''hls_core core(.clk(clk), .rst(rst), .start(start_pulse), .en(step_pulse | auto_run | run_pulse),
    .inputs_bus(inputs_bus), .debug_sel(sw_sync[5:0]), .busy(busy), .done(done),
    .outputs_bus(outputs_bus), .fu_debug(fu_debug), .reg_debug(reg_debug), .phase(phase));
wire [15:0] arithmetic_view = sw_sync[6] ? reg_debug : fu_debug;
wire [13:0] phase_view = phase;
wire [15:0] status_view = {{busy, done, phase_view}};
wire [15:0] display_value = sw_sync[7] ? status_view : arithmetic_view;
assign led = display_value[7:0];
assign dp = ~done;
hex_display display(.clk(clk), .rst(rst), .value(display_value), .seg(seg), .an(an));
endmodule

module nexys_a7_top(input clk, input [7:0] sw, input btnC, input btnL, input btnR, input btnU,
    output [7:0] led, output [6:0] seg, output [7:0] an, output dp);
wire [3:0] an_low;
assign an = {{4'b1111, an_low}};
board_runtime runtime(clk, sw, btnC, btnL, btnR, btnU, led, seg, an_low, dp);
endmodule
''']
    (out/'board_top.v').write_text('\n'.join(board))
    write_tb(p,times,length,binding,units,width,phase_width,ni,no,out,seed,vectors,initial)
    sources = ['functional_units.v','hls_control.v','hls_datapath.v','hls_core.v','board_support.v','board_top.v']
    (out/'sources.f').write_text('\n'.join(sources)+'\n')
    (out/'board_map.md').write_text('# Generated board map\n\n'+
        '\n'.join(f'- Input `{name}`: '+(f'SW[{selected.index(name)*4+3}:{selected.index(name)*4}] sampled on START' if name in selected else f'hardcoded {initial[name]}') for name in p.input_names)+
        '\n\nAfter START, switches select observations: SW7=1 status; SW7=0, SW6=0 functional unit; SW7=0, SW6=1 SSA register. SW[5:0] is the selector.\n\n'+
        '| Selector | Functional unit |\n|---|---|\n'+''.join(f'| {i} | {k}{u} |\n' for i,(k,u) in enumerate(units))+
        '\n| Selector | SSA register |\n|---|---|\n'+''.join(f'| {i} | {n.dst} |\n' for i,n in enumerate(p.nodes))+
        '\nAll displayed numbers are hexadecimal; display shows low 16 bits. Status bit15=busy, bit14=done, low bits=next scheduled cycle; after completion phase=L+1. Decimal point lights on done.\n')
    return manifest


def write_tb(p,times,length,binding,units,w,pw,ni,no,out,seed,vectors,initial):
    rng = random.Random(seed)
    cases = [{name:0 for name in p.input_names}, {name:(1<<w)-1 for name in p.input_names}, initial]
    cases += [{name:rng.randrange(1<<w) for name in p.input_names} for _ in range(vectors)]
    tb = [f'''`timescale 1ns/1ps
module testbench;
reg clk=0; always #5 clk=~clk;
reg rst=1, start=0, en=0;
reg [{ni*w-1}:0] inputs_bus=0;
reg [5:0] debug_sel=0;
wire busy, done;
wire [{pw-1}:0] phase;
wire [{no*w-1}:0] outputs_bus;
wire [{w-1}:0] fu_debug, reg_debug;
integer errors=0;
hls_core dut(clk,rst,start,en,inputs_bus,debug_sel,busy,done,outputs_bus,fu_debug,reg_debug,phase);
task tick; begin @(posedge clk); #1; end endtask
task check; input condition; input [511:0] message;
begin if (condition !== 1'b1) begin $display("FAIL %0s at %0t",message,$time); errors=errors+1; end end endtask
initial begin
    $dumpfile("wave.vcd"); $dumpvars(0,testbench);
    tick; @(negedge clk); rst=0;
''']
    for ci,values in enumerate(cases):
        tb += [f'    // Transaction {ci}; expected values come from the Python sequential interpreter.',
               '    @(negedge clk); start=1; en=0; inputs_bus=0;']
        for i,name in enumerate(p.input_names):
            tb += [f'    inputs_bus[{i*w} +: {w}]={literal(w,values[name])};']
        tb += ['    tick; check(busy && !done && phase==1,"start handshake");',
               '    @(negedge clk); start=0; inputs_bus=~inputs_bus;',
               '    tick; check(phase==1,"stall before first cycle");']
        env = evaluate(p,values,w)
        regs = {n.dst:0 for n in p.nodes}
        held = {unit:0 for unit in units}
        for c in range(1,length+1):
            tb += ['    @(negedge clk); en=1;'+(' start=1; // busy start must be ignored' if c==1 else ''), '    tick;']
            for n in p.nodes:
                if times[n.id]==c:
                    regs[n.dst] = env[n.dst]
                    held[binding[n.id]] = env[n.dst]
            tb += [f'    check(phase=={c+1},"phase advancement");',
                   f'    check(busy=={int(c<length)} && done=={int(c==length)},"completion timing");',
                   '    @(negedge clk); en=0; start=0;']
            for i,n in enumerate(p.nodes):
                tb += [f'    debug_sel={i}; #1; check(reg_debug=={literal(w,regs[n.dst])},"register {n.dst}");']
            for i,unit in enumerate(units):
                tb += [f'    debug_sel={i}; #1; check(fu_debug=={literal(w,held[unit])},"FU {unit[0]}{unit[1]}");']
            # All observations run at negedge+#1; for large programs they can cross
            # multiple clocks, but en=0 keeps the complete design stationary.
            tb += [f'    tick; check(phase=={c+1},"paused phase");']
        packed = sum(env[s] << (i*w) for i,s in enumerate(p.outputs.values()))
        tb += [f'    check(outputs_bus=={literal(no*w,packed)},"all final outputs transaction {ci}");',
               '    debug_sel=63; #1; check(fu_debug==0 && reg_debug==0,"invalid observation selector");']
    tb += ['''    // Reset aborts a running transaction and clears visible state.
    @(negedge clk); start=1; en=0; tick;
    @(negedge clk); start=0; en=1; tick;
    @(negedge clk); rst=1; tick;
    check(!busy && !done && phase==0 && outputs_bus==0,"reset clears transaction");
    @(negedge clk); rst=0; en=1; tick;
    check(phase==0,"idle ignores enable");
    if (errors) $fatal(1,"%0d failures",errors);
    $display("PASS: all transactions, cycle registers, shared FUs, stalls, reset and restart");
    $finish;
end
initial begin #100000000; $fatal(1,"timeout"); end
endmodule
''']
    (out/'testbench.v').write_text('\n'.join(tb))


def simulate(out):
    out = Path(out).resolve()
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        raise HLSError('install Icarus Verilog (iverilog and vvp) to use --simulate')
    sources = (out/'sources.f').read_text().splitlines()
    subprocess.run(['iverilog','-g2005','-Wall','-s','testbench','-o','sim.vvp',*sources,'testbench.v'],cwd=out,check=True)
    subprocess.run(['vvp','sim.vvp'],cwd=out,check=True)


MAX_EQUATIONS = 20


def read_dynamic_input(given=None):
    """Get the equations for --dynamic-input. Equations are separated by ';' or a
    new line, and at most 20 are used. Returns them as text, one per line, ready
    for parse().
    given = the text typed after --dynamic-input on the command line, e.g.
            --dynamic-input "X = A + B; Y = X * 2". The shell removes the quotes;
            any quotes still present are stripped.
    given = None: prompt for the equations. The list must start with a double
            quote (") and end with a closing double quote; reading also stops on
            its own once 20 equations have been entered."""
    if given is not None:
        text = given.strip()
        if text.startswith('"'):
            text = text[1:]
        if text.endswith('"'):
            text = text[:-1]
        if text.strip() and '=' not in text:
            raise HLSError(f'--dynamic-input expects equations such as "X = A + B; Y = X * 2", got {given!r}; '
                           'to read a file, give its name without --dynamic-input')
        eqs = [e.strip() for e in re.split(r'[;\n]', text) if e.strip()]
        if len(eqs) > MAX_EQUATIONS:
            print(f'(only the first {MAX_EQUATIONS} equations are used; {len(eqs) - MAX_EQUATIONS} ignored)')
        return '\n'.join(eqs[:MAX_EQUATIONS]) + '\n'
    print(f'Enter up to {MAX_EQUATIONS} equations, separated by ; or new lines.')
    print('Start the list with " and end it with " , e.g.  "X = A + B; Y = X * 2"')
    text = ''
    while True:
        try:
            line = input('> ' if not text else '... ')
        except EOFError:                                  # Ctrl-D / end of piped input
            print('\n(end of input reached without a closing ")')
            break
        if not text:                                      # first line must open with "
            if not line.strip():
                continue
            if not line.lstrip().startswith('"'):
                print('The list must start with " - please try again.')
                continue
            line = line.lstrip()[1:]
        text += line + '\n'
        body = text.split('"')[0]
        count = len([e for e in re.split(r'[;\n]', body) if e.strip()])
        if '"' in text:
            if text.split('"', 1)[1].strip():
                print('(text after the closing " was ignored)')
            break
        if count >= MAX_EQUATIONS:
            print(f'({MAX_EQUATIONS} equations entered - continuing without the closing ")')
            break
    eqs = [e.strip() for e in re.split(r'[;\n]', text.split('"')[0]) if e.strip()]
    if len(eqs) > MAX_EQUATIONS:
        print(f'(only the first {MAX_EQUATIONS} equations are used; {len(eqs) - MAX_EQUATIONS} ignored)')
    return '\n'.join(eqs[:MAX_EQUATIONS]) + '\n'


def step_through(enabled, title, lines):
    """--step: print one stage of the flow under a heading, then wait for Enter
    before the next stage. Does nothing when --step is not given."""
    if not enabled:
        return
    print(f'\n=== {title} ===')
    print('\n'.join(lines))
    try:
        input(f'\n[step] {title} done. Press Enter to continue...')
    except EOFError:                                      # no more input: keep going
        print()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path, nargs='?', help='equations file (omit when using --dynamic-input)')
    ap.add_argument('-dynamic-input', '--dynamic-input', dest='dynamic_input', nargs='?', const=True,
                    metavar='"EQUATIONS"',
                    help='give the equations on the command line instead of a file, e.g. '
                         '--dynamic-input "X = A + B; Y = X * 2"; with no equations after it, '
                         'prompt for them')
    ap.add_argument('--step', action='store_true',
                    help='walk through the flow: show input, SSA, DAG and schedule, pausing for Enter after each')
    ap.add_argument('--out',type=Path,default=Path('build/demo'))
    ap.add_argument('--mode',choices=MODES,default='constrained-asap')
    ap.add_argument('--adders',type=int,default=1)
    ap.add_argument('--subtractors',type=int,default=1)
    ap.add_argument('--multipliers',type=int,default=1)
    ap.add_argument('--latency',type=int,help='maximum cycles; ALAP aligns to this final cycle')
    ap.add_argument('--width',type=int,default=16)
    ap.add_argument('--export-ssa',nargs='?',const='-',metavar='FILE',help='also export SSA to FILE, or print if no FILE')
    ap.add_argument('--const',action='append',default=[],metavar='NAME=VALUE',help='hardcode a board input, repeatable')
    ap.add_argument('--switch-inputs',help='zero, one, or two comma-separated external names; default first two nonconstants')
    ap.add_argument('--vectors',type=int,default=24,help='random test vectors in addition to three directed vectors')
    ap.add_argument('--seed',type=int,default=551)
    ap.add_argument('--simulate',action='store_true')
    args = ap.parse_args(argv)
    if (args.dynamic_input is not None) == (args.input is not None):
        ap.error('give an equations file or --dynamic-input, but not both')
    try:
        if args.dynamic_input is None:
            text = args.input.read_text()
        else:
            text = read_dynamic_input(None if args.dynamic_input is True else args.dynamic_input)
        p = parse(text)
        step_through(args.step, 'Original input',
                     [l for l in (r.split('#', 1)[0].split('//', 1)[0].strip() for r in text.splitlines()) if l])
        step_through(args.step, 'SSA', p.ssa().splitlines() +
                     [f'(inputs: {", ".join(p.inputs) or "none"})'])
        step_through(args.step, 'DAG', ['(node: operation   <- nodes it depends on)'] +
                     [f'n{n.id}: {n.dst} = {n.a} {n.op} {n.b}   <- {", ".join(f"n{d}" for d in n.deps) or "inputs only"}'
                      for n in p.nodes])
        constants = {}
        for entry in args.const:
            name,value = entry.split('=',1)
            if name in constants:
                raise HLSError(f'duplicate constant {name}')
            constants[name] = int(value,16 if value.lower().startswith('0x') else 10)
        selected = None if args.switch_inputs is None else [s.strip() for s in args.switch_inputs.split(',') if s.strip()]
        caps = dict(add=args.adders,sub=args.subtractors,mul=args.multipliers)
        if any(v < 0 for v in caps.values()):
            raise HLSError('resource limits cannot be negative')
        if args.mode in ('asap','alap') and caps != dict(add=1,sub=1,mul=1):
            print('Note: unconstrained mode ignores resource flags.',file=sys.stderr)
        times,length,caps = schedule(p,args.mode,caps,args.latency)
        if args.step:
            binding, peaks = bind(p, times)
            rows = []
            for c in range(1, length+1):
                ops = [f'{n.dst} = {n.a} {n.op} {n.b} [{binding[n.id][0]}{binding[n.id][1]}]'
                       for n in p.nodes if times[n.id] == c]
                rows.append(f'cycle {c}: ' + (' | '.join(ops) or '(idle)'))
            rows.append(f'latency {length} cycles; functional units instantiated: {peaks}')
            step_through(True, f'Schedule ({args.mode})', rows)
        manifest = emit(p,times,length,caps,args.mode,args.width,args.out,constants,selected,args.seed,args.vectors)
        if args.export_ssa == '-':
            print(p.ssa(),end='')
        elif args.export_ssa:
            Path(args.export_ssa).write_text(p.ssa())
        print(f'{len(p.nodes)} operations; {length} cycles; FUs={manifest["resources_instantiated"]}; output={args.out}')
        if args.simulate:
            simulate(args.out)
        return 0
    except (HLSError,OSError,ValueError,subprocess.CalledProcessError) as exc:
        print(f'error: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())
