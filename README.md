# EC551 Programming Assignment 2 — Hardware Synthesis

**Authors:** Tanner Armstard and Francis Liri  
**FPGA used:** Digilent Nexys A7-100T, Artix-7 `xc7a100tcsg324-1` (CSG324)  
**FPGA toolchain:** Vivado 2026.1 on Windows

A Python HLS compiler for Rev 2.0: sequential equations → SSA → DAG → resource-constrained scheduling and binding → generated Verilog datapath and sequencer → switch/button FPGA runtime.

**Status:** synthesis, implementation, bitstream generation, and programming have been demonstrated on a **Nexys A7-100T CSG324** using **Vivado 2026.1 on Windows**. Physical testing confirmed correct results for `assignment.eqn` and `reassignment.eqn`, including manual stepping and observation controls. See [hardware results](docs/BOARD_RESULTS.md) for the evidence and remaining measurements, and [validation](docs/VALIDATION.md) for software/RTL checks. The live presentation and public repository submission remain separate course tasks.

## Quick start

Requirements: Python 3.10+; no pip packages. Install Icarus Verilog (`iverilog` and `vvp`) for simulation. Yosys and Graphviz are optional. On Windows, use `py` instead of `python3` if appropriate and install Icarus with its executables on PATH; the compiler itself works without WSL. FPGA builds use AMD/Xilinx Vivado for the Nexys A7-100T.

Run from the repository root:

```sh
python3 hls.py examples/assignment.eqn --out build/demo --export-ssa --simulate
python3 scripts/reference.py examples/assignment.eqn --value A=5 --value B=3
python3 scripts/verify.py --require-rtl
```

Expected values: `X=8, Y=13, Z=5, Q=15`. `--simulate` prints `PASS` or returns a nonzero exit code. Without Icarus, omit `--simulate`; compilation still generates every artifact. Verification without `--require-rtl` clearly reports skipped RTL checks.

For hardware, start with `build/demo`. It is already generated. The tested target is the **Nexys A7-100T**; use `nexys_a7_top`, part `xc7a100tcsg324-1`, and `constraints/nexys_a7.xdc`.

Windows quick start for the tested setup:

```bat
python hls.py examples/assignment.eqn --out build/demo --mode constrained-asap --export-ssa
python scripts/reference.py examples/assignment.eqn --manifest build/demo/manifest.json --value A=5 --value B=3
```

If Icarus is unavailable, use Vivado **Run Simulation → Run Behavioral Simulation** with the generated `testbench.v` as a simulation-only source and `testbench` as the simulation top. A Vivado simulation PASS was reported for this project. The compiler works without Icarus; `

## SYNOPSIS

```
python3 hls.py FILE [OPTIONS]
python3 hls.py --dynamic-input ["EQUATIONS"] [OPTIONS]

OPTIONS:
  [--step]
  [--mode asap|constrained-asap|alap|constrained-alap|custom]
  [--adders N] [--subtractors N] [--multipliers N] [--latency N]
  [--width N] [--export-ssa [FILE]]
  [--const NAME=VALUE]... [--switch-inputs NAME[,NAME]]
  [--vectors N] [--seed N] [--simulate] [--out DIR]
```
### DESCRIPTION

**hls.py** reads up to 20 sequential equations and runs this flow:

1. **Parse** the equations, from *FILE* or from **--dynamic-input** (on the command line or typed at the prompt).
2. **Convert to SSA.** Every assignment creates a new version of the variable (`X_1`, `X_2`, …). An input that is read before it is assigned becomes version `_0` (`A_0`).
3. **Build the DAG.** There is one node per operation, and the edges are data dependencies.
4. **Schedule** each operation into a cycle, using one of five modes (see **SCHEDULING MODES**).
5. **Bind** operations to functional units. The *k*-th operation of a type in a cycle runs on unit *k*, so the design instantiates the largest number of units of each type used in any one cycle.
6. **Emit Verilog-2001.** The output is:
   - a sequencer FSM (`hls_control`);
   - a datapath with operand muxes and one register per SSA value (`hls_datapath`);
   - a core wrapper (`hls_core`);
   - a Nexys A7 board runtime with START, STEP and RUN buttons (`board_top.v`);
   - a self-checking testbench.

Each operation takes one *enabled* cycle. The design advances only when STEP or RUN is pressed, so data can be stepped through the datapath one cycle at a time.


### OPTIONS

#### Input

**FILE**
: Text file of equations. Required unless **--dynamic-input** is given; giving both is an error.

**-dynamic-input** ["*EQUATIONS*"], **--dynamic-input** ["*EQUATIONS*"]
: Take the equations from the command line instead of a file, for example `--dynamic-input "X = A + B; Y = X * 2"`. With no equations after it, prompt for them. See **DYNAMIC INPUT**.

**--step**
: Walk through the flow one stage at a time. See **STEP MODE**.

#### Scheduling

**--mode** *MODE*
: One of `asap`, `constrained-asap`, `alap`, `constrained-alap`, `custom`. Default: `constrained-asap`.

**--adders** *N*, **--subtractors** *N*, **--multipliers** *N*
: Maximum units of each type per cycle in the constrained modes and `custom`. Default 1 each. A limit of 0 is an error if the program needs that unit type. The unconstrained modes ignore these flags and print a note to stderr.

**--latency** *N*
: Latency bound in cycles (1–4095). It must be at least the critical-path length.
  - Forward modes treat *N* as a maximum. If the schedule needs more cycles, the tool stops with an error.
  - ALAP modes place the last operation in cycle *N*, so earlier cycles may be idle.

#### Hardware

**--width** *N*
: Datapath width in bits, 4–64. Default 16. Arithmetic is unsigned modulo 2^*N*.

**--const** *NAME*=*VALUE*
: Hardcode the external input *NAME* on the board. *VALUE* may be decimal or `0x` hex and must fit in **--width** bits. Repeat the option for several inputs.

**--switch-inputs** *NAME*[,*NAME*]
: Choose zero, one or two external inputs to read from the switches. The first is read from `SW[3:0]`, the second from `SW[7:4]`. Default: the first two inputs that are not given with **--const**. Any other input is hardcoded to 1.

#### Output and verification

**--export-ssa** [*FILE*]
: Also write the SSA form to *FILE*. With no *FILE*, print it to standard output. `ssa.txt` is always written to **--out** as well.

**--out** *DIR*
: Output directory. Default `build/demo`.

**--vectors** *N*
: Number of random test vectors in the testbench, 1–1000. Default 24. Three fixed vectors are always added (see **VERIFICATION**).

**--seed** *N*
: Random seed for the test vectors. Default 551.

**--simulate**
: After generating, compile and run the testbench with Icarus Verilog (`iverilog -g2005`, `vvp`) in *DIR*.

### INPUT FORMAT

```
DEST = ARG OP ARG [;]
```

| Element | Rule |
|---|---|
| *DEST* | identifier: `[A-Za-z_][A-Za-z_0-9]*` |
| *ARG* | identifier, decimal constant (`12`) or hex constant (`0x1F`) |
| *OP* | `+`, `-` or `*` (one operator per equation) |
| Comments | `#` or `//` to end of line |
| Blank lines | ignored |
| Limit | 20 equations |

Both operands are read before *DEST* is updated, so `X = X + 1` uses the old `X`.

Example:

```
X = A + B
Y = X + A
Z = X - B
Q = B * Z
X = Q + Y      # reassignment -> X_2
R = X * 2
```

### DYNAMIC INPUT

**--dynamic-input** takes the equations instead of a file, in one of two ways.

#### On the command line

Put the equations in double quotes straight after the option:

```
$ python3 hls.py --out build/sharing --const C=2 --const D=1 --switch-inputs A,B \
      -dynamic-input "P=A+B; R=C+D ; S=P+R; T=C+D; U=P*T;V=S+U;Q=V-T"
7 operations; 7 cycles; FUs={'add': 1, 'sub': 1, 'mul': 1}; output=build/sharing
```

- The quotes are needed so the shell passes the equations as one argument. The shell removes them before `hls.py` sees the text; quotes that are still present (escaped as `\"...\"`) are stripped.
- Equations are separated by `;` or new lines inside the quotes.
- If more than 20 are given, the first 20 are used and the tool says how many were ignored.
- The equations must come straight after the option. A file name in that position is reported as an error, because the tool can't take a file and **--dynamic-input** together.

#### At the prompt

With nothing after **--dynamic-input** (it is the last argument, or the next argument is another option), the tool prompts for the equations:

```
$ python3 hls.py --dynamic-input --mode custom
Enter up to 20 equations, separated by ; or new lines.
Start the list with " and end it with " , e.g.  "X = A + B; Y = X * 2"
> "X = A + B; Y = X + A
... Z = X - B
... Q = B * Z; X = Q + Y; R = X * 2"
6 operations; 5 cycles; FUs={'add': 1, 'sub': 1, 'mul': 1}; output=build/demo
```
How input is read:

- **Opening quote:** the list must start with `"`. If the first line doesn't, the tool asks again.
- **Separators:** equations are separated by `;` or new lines, in any mix, across any number of lines.
- **Closing quote:** the list ends at the closing `"`. Any text after it is ignored, and the tool says so.
- **20-equation limit:** once 20 equations have been entered, the tool continues without waiting for the closing `"`. If more than 20 are typed on one line, the first 20 are used.
- **End of input:** if input ends (Ctrl-D, or end of piped input) before the closing `"`, the equations entered so far are used.

The equations are then processed exactly like a file: the same parser and the same 20-equation limit.

### STEP MODE

With **--step**, the tool prints each stage of the flow and waits for **Enter** before the next one:

1. **Original input:** the equations, with comments and blank lines removed.
2. **SSA:** the renamed statements and the SSA input names.
3. **DAG:** each node, its operation, and the nodes it depends on.
4. **Schedule:** each cycle's operations with their functional unit (`[add0]`), idle cycles, the latency, and the units instantiated.

After the last pause, the files are written. **--step** can be combined with any other option, including **--dynamic-input** and **--simulate**.

```
=== DAG ===
(node: operation   <- nodes it depends on)
n0: X_1 = A_0 + B_0   <- inputs only
n1: Y_1 = X_1 + A_0   <- n0
...
[step] DAG done. Press En

## Organization

```text
ec551_hls/
  hls.py                    parser, SSA IR, DAG, schedulers, binding, RTL/TB generation
  rtl/functional_units.v    parameterized add/subtract/multiply modules
  rtl/board_support.v       synchronization, debounce, hex display scan
  examples/                 source equations, including three demo programs
  build/demo/               complete generated assignment example
  build/reassignment/       SSA reassignment example
  build/sharing/            time-shared units with static C=2, D=1
  build/schedules/           parallel example under all five modes
  constraints/nexys_a7.xdc   Nexys A7-100T pin and clock constraints
  scripts/                  example generation, reference evaluation, verification, FPGA builds
  tests/                    Python invariants and board integration testbench
  docs/                     requirement mapping and validation record
```

Each generated directory contains `ssa.txt`, `dag.dot`, `schedule.csv`, `manifest.json`, `board_map.md`, `functional_units.v`, `hls_control.v`, `hls_datapath.v`, `hls_core.v`, `board_support.v`, `board_top.v`, `sources.f`, and `testbench.v`. Simulation additionally produces `sim.vvp` and `wave.vcd` (not committed). `manifest.json` defines every bus lane, resource instance, selector, and schedule cycle.

Regenerate committed artifacts with:

```sh
python3 scripts/generate_examples.py
```

Optional DAG image and waveform inspection:

```sh
dot -Tsvg build/demo/dag.dot -o build/demo/dag.svg
gtkwave build/demo/wave.vcd
```

## Input language and SSA

An equation has exactly two operands and one `+`, `-`, or `*`. Operands are case-sensitive identifiers, unsigned decimal literals, or hexadecimal literals. Blank lines, `#`/`//` comments, whitespace, and optional trailing semicolons are supported. At most 20 equations are accepted. Parentheses, division, unary minus, and multi-operator expressions are rejected with line numbers. Split complex expressions into equations.

```text
X = A + B
X = X * B
Y = X - A
```

becomes:

```text
X_1 = A_0 + B_0
X_2 = X_1 * B_0
Y_1 = X_2 - A_0
```

A name read before its first assignment is an external input at version `_0`. An assignment always reads the old operands before publishing the new destination version. Thus `X=X+1` uses external `X_0`; a later assignment to `X` does not create a backward edge. The source is sequential code, not a simultaneous system of algebraic equations. Constants have no producer nodes. Internally, compiler-owned `r0`, `r1`, … register names avoid conflicts with Verilog keywords or user names.

`ssa.txt` is always generated; `--export-ssa` additionally prints it and `--export-ssa PATH` writes the requested file.

## Scheduling and binding

All arithmetic operators are modeled as combinational functional units whose result is captured in one destination register at the next **enabled** edge. Every dependency therefore requires a strictly later scheduled cycle. The physical multiplier has the same one-enabled-cycle model as the adder/subtractor; there is no hidden multi-cycle IP.

| Mode | Strategy | Resource flags |
|---|---|---|
| `asap` | Forward earliest-ready placement | Ignored; provision peak parallelism |
| `constrained-asap` | Forward list scheduling, source-order priority | Enforced |
| `alap` | Backward placement from final-cycle bound | Ignored; provision peak parallelism |
| `constrained-alap` | Reverse list scheduling with per-type capacities | Enforced |
| `custom` | Forward list scheduling, longest remaining path first, then fanout and source order | Enforced |

The constrained modes default to one adder, one subtractor, and one multiplier. Supply any nonnegative limits; zero is allowed only for a resource type not used in the program. Unconstrained scheduling does not mean missing registers: it means no cap on simultaneous operations. The unconstrained ASAP/ALAP latency is the unit-delay critical path when no bound is supplied.

For ALAP, `--latency N` puts the final operations at cycle N, leaving leading empty cycles when appropriate. Without that flag, reverse scheduling derives a feasible compact bound. For forward modes the flag is a maximum, not a request for padding. Bounds 1..4095 are supported. Impossible critical-path bounds, missing resources, and bounds exceeded by the chosen schedule are reported. Constrained list scheduling is heuristic: rejecting a tight bound does not prove that every possible ordering is infeasible. There is no optimal-latency claim.

```sh
python3 hls.py examples/parallel.eqn --mode asap --out build/unconstrained
python3 hls.py examples/parallel.eqn --mode constrained-asap --adders 1 --multipliers 1 --out build/limited
python3 hls.py examples/parallel.eqn --mode alap --latency 7 --out build/alap7
python3 hls.py examples/parallel.eqn --mode constrained-alap --adders 1 --multipliers 1 --latency 8 --out build/reverse
python3 hls.py examples/parallel.eqn --mode custom --adders 1 --subtractors 0 --multipliers 1 --out build/custom
```

Binding uses exactly the peak number of simultaneous operations of each type in that schedule. E.g., three additions at different cycles share one `hls_add`; three in the same cycle require three `hls_add` instances. The muxes choose that unit's operands from the appropriate input/intermediate registers for the current FSM phase. The generated register-write case only enables destinations scheduled in that phase. Every assigned SSA result has its own register for observability; register lifetime allocation is not attempted. Xilinx may optimize or map those logical units into LUTs/DSPs; logical instance counts are not a promise of a particular mapped cell count.

## Datapath, FSM, and interface

`hls_control` is the sequencer; `hls_datapath` contains operand muxes, instantiated units, input snapshots, destination registers, and observation muxes; `hls_core` connects both. `board_runtime` connects the core to filtered controls and display logic. All emitted hardware is Verilog-2001.

At a clock edge, priority is reset → accepted start → enabled operation cycle. Start is accepted only while idle/done. An accepted start snapshots all external inputs, clears previous intermediates and FU observation registers, sets `busy=1`, clears `done`, and selects cycle 1. It does **not** execute cycle 1 at that edge. While busy, each `en=1` edge commits the current cycle and advances the phase. `en=0` holds every computation register and the FSM. `start` while busy is ignored. After the last commit, `done=1`, `busy=0`, and `phase=L+1` persist until reset or another accepted start. Reset is synchronous and aborts a computation.

| Core port | Meaning |
|---|---|
| `clk`, `rst` | Clock and synchronous active-high reset |
| `start`, `en` | Capture/start request and scheduled-cycle enable |
| `inputs_bus` | W-bit lanes in `manifest.input_names` order; lane 0 is least significant |
| `outputs_bus` | W-bit lanes in manifest `outputs` insertion order; latest version of **each** assigned source variable |
| `busy`, `done`, `phase` | Execution status and next cycle number |
| `debug_sel[5:0]` | Selector used for both observation buses |
| `fu_debug` | Selected unit's last committed result |
| `reg_debug` | Selected assigned SSA register |

Programs with no external inputs still have one unused W-bit input bus lane tied to zero by the board wrapper. Unused selector values return zero. FU observation is a registered copy of the **actual unit output** when used; it remains visible after the next phase changes its operand muxes. This lets the professor inspect shared-unit activity after each step. `reg_debug` exposes all assigned SSA versions, even intermediate versions later overwritten in source code.

## Bit width and numerical behavior

Default W=16, configurable `--width 4..64`. Inputs and results are unsigned W-bit values. Each arithmetic result is reduced modulo `2**W`; addition carry and high product bits are discarded. Subtraction underflow wraps by the same rule. Literals are also reduced to W bits. Choose demo inputs with nonnegative subtraction and no overflow to show ordinary unsigned integer arithmetic, as assumed by the assignment. `scripts/reference.py` flags wrap cases so they are not mistaken for arithmetic errors.

The two switch-controlled variables receive zero-extended **4-bit values 0..15**. The core has the full W-bit interface for simulation and integration. The board display shows the low 16 bits in hexadecimal and LEDs show the low 8 bits. A wider configured core does not expand the display. With W=16, this is the full result.

## Physical I/O and button stepping

The Nexys A7-100T implementation uses eight switches and four action buttons. It disables the upper four seven-segment digits and uses the lower four. Use `constraints/nexys_a7.xdc` for the pin assignments.

| Control | Action |
|---|---|
| BTN C (center) | Reset; hold/release for at least 20 ms |
| BTN L (left) | START: snapshot switch inputs and initialize a new transaction |
| BTN R (right) | STEP: execute exactly one scheduled cycle per press |
| BTN U (up) | RUN: finish an already-started transaction automatically |
| SW[3:0] at START | First selected external variable, unsigned 0..15 |
| SW[7:4] at START | Second selected external variable, unsigned 0..15 |
| SW7=1 after START | Status: bit15 busy, bit14 done, low14 next phase |
| SW7=0, SW6=0 | FU observation, index SW[5:0] |
| SW7=0, SW6=1 | SSA register observation, index SW[5:0] |
| Decimal point | Illuminated while done |

**Switches have two roles.** Set input values first, wait at least 20 ms, and press START. After that, freely change switches to select observations; captured inputs remain unchanged. For the assignment example A=5, B=3, set switches to binary `00110101` (hex 35), START, then choose selectors. Return switches to the desired input values before starting again. Keep switches still while pressing START; synchronization alone does not make a changing multi-bit switch value atomic.

In the default example the FU selectors are 0=adder, 1=subtractor, 2=multiplier. SSA selectors are 0=X_1, 1=Y_1, 2=Z_1, 3=Q_1. SW=0x43 therefore shows Q, and SW=0x80 shows status. Read each generated `board_map.md` because this mapping changes with equations and resources.

The 100 MHz oscillator runs continuously for safe FPGA clock distribution, input synchronization, debounce, and display scanning. The external STEP button **clocks the computation logically via a one-cycle clock enable**; a raw mechanical button is not routed as a clock. Holding it does not advance multiple times. All datapath registers and the sequencer use the same enable. One hardware clock cycle is 10 ns; one manual scheduled cycle takes one button press. RUN is optional convenience after START; STEP is the required demo behavior.

Two-stage synchronizers handle buttons and switches. Buttons must remain stable for 2,000,000 clock cycles (20 ms) to change their debounced state. A rising debounced edge emits a single pulse. Release a button for at least 20 ms before pressing it again. A short power-on reset counter initializes the runtime after FPGA configuration.

## Static inputs and professor-selected variables

By default, the first two external variables in first-read order use the switches; other external inputs are hardcoded to 1. Set all additional values deliberately for each demo:

```sh
python3 hls.py examples/sharing.eqn --out build/sharing --const C=2 --const D=1 --switch-inputs A,B --simulate
python3 scripts/reference.py examples/sharing.eqn --manifest build/sharing/manifest.json --value A=5 --value B=3
```

Use `--switch-inputs NAME1,NAME2` to select different variables, one name for one input, or `--switch-inputs ""` for none. `--const NAME=VALUE` is repeatable. Conflicting selections, unknown names, out-of-range constants, or more than two switch inputs are rejected. Static board values are compile-time constants; changing them regenerates/rebuilds the bitstream. Core testbenches can still vary every external core input independently, including board-hardcoded ones.

## Simulation and verification

Every compilation emits a self-checking `testbench.v`. Run it with `--simulate`. It checks zero and max inputs, the static-input configuration, and `--vectors` seeded random input sets (default 24), including every intermediate register and each FU's committed result after every scheduled cycle. It also checks paused cycles, busy-start rejection, input snapshot stability, completion timing, invalid selectors, restart without reset, and reset/abort. The Python sequential interpreter computes expected values independently of the scheduling and binding implementation. Random underflow and overflow tests intentionally exercise the defined W-bit hardware semantics.

```sh
python3 scripts/verify.py --require-rtl
python3 scripts/verify.py --require-rtl --random-rtl 20
python3 scripts/check_synthesis.py build/demo
python3 scripts/check_synthesis.py build/demo --top nexys_a7_top
```

The default verifier runs nine Python test methods (including 120 random programs under all five modes), 66 generated RTL simulations across widths 4, 8, 16, 32, and 64, a padded ALAP schedule, a complete board-control simulation, and Nexys A7-100T wrapper elaboration. The physical FPGA used for this project is exclusively the Nexys A7-100T. Temporary random artifacts are removed automatically. It fails on any simulator failure. Generic Yosys synthesis checks synthesizability and structural consistency, **not** FPGA placement, pin correctness, timing closure, or physical behavior.

## FPGA build and programming

### Nexys A7-100T — Artix-7 (Vivado)

Use device `xc7a100tcsg324-1`, top `nexys_a7_top`, and `constraints/nexys_a7.xdc`. Run from a Vivado command shell:

```sh
vivado -mode batch -source scripts/build_vivado.tcl -tclargs build/demo
vivado -mode batch -source scripts/program_vivado.tcl -tclargs build/demo/fpga_build/vivado/hls_demo.runs/impl_1/nexys_a7_top.bit
```

The build exports utilization, timing, and DRC reports and stops if implementation fails or the reported worst setup slack is negative. Review complete setup/hold timing and DRC before programming. The programming script requires exactly one Artix-7 device, avoiding arbitrary device selection.

For an existing Vivado GUI project referencing the generated files in `build/demo`:

1. Regenerate `build/demo` for the desired equations and schedule.
2. Reset synthesis and regenerate the bitstream. In the Tcl Console:

```tcl
reset_run synth_1
launch_runs impl_1 -to_step write_bitstream -jobs 4
```

3. Wait for bitstream generation to complete and review timing. In **Hardware Manager**, connect to the powered board and select **Program Device** with the newly generated `nexys_a7_top.bit`.
4. Reset, capture inputs, and step through the new schedule. Check the regenerated `board_map.md` before choosing observations.

Equation files and schedules are compiled into hardware; the FPGA does not read `.eqn` files. Regenerating Python outputs alone does not update the running FPGA. If the output directory changes, update the Vivado source references as well. Batch-script builds and manually created GUI projects place bitstreams in different project directories; select the bitstream from the build just completed.

The hardware instructions and physical demonstration in this README apply only to the Nexys A7-100T.

### Manufacturer references

- [Digilent Nexys A7 master constraints](https://github.com/Digilent/digilent-xdc/blob/master/Nexys-A7-100T-Master.xdc): clock, switches, LEDs, buttons, display pins.

The Nexys A7-100T pin assignments are defined in `constraints/nexys_a7.xdc` using this project's top-level port names.

## Strict 30-minute live demo plan

**Before the slot (outside the 30 minutes):** install tools/cable drivers, sign up for the professor's presentation slot, rehearse all commands and board controls, and measure a full generate → simulate → synthesize → place/route → program iteration on the actual laptop and board. For the plan below, each live hardware build/program must take **at most four minutes**, leaving about two minutes per run for editing and inspection. Keep the part, tool version, project, constraints, and cables ready. Do not call a simulation a physical run. If measured builds exceed this budget, resolve this with the professor before the slot; the three-live-build requirement cannot honestly be guaranteed by a generic script.

| Time | Minutes | Demonstration |
|---|---:|---|
| 00:00–03:00 | 3 | Explain language, SSA, dependency DAG, unit-delay model, and datapath/controller split. Show source, SSA, DAG, and manifest. |
| 03:00–06:00 | 3 | Compare all five pre-generated schedules for `parallel.eqn`, caps and unit counts. Show a shared adder's operand mux and register write-enable. Explain custom critical-path priority and ALAP bound. |
| 06:00–08:00 | 2 | On the preloaded assignment example show START, one STEP per cycle, a held button, FU and SSA selectors, and done. Explain 16-bit arithmetic and input capture. |
| 08:00–14:00 | 6 | **Professor-directed live run 1:** professor writes custom equations and selects input values. Save to `live1.eqn`; generate, simulate, compute expected values, build/program, STEP and compare outputs. |
| 14:00–20:00 | 6 | **Professor-directed live run 2:** new equations, preferably including reassignment; professor chooses resources and values. Save to `live2.eqn`; repeat complete compile/build/program/physical verification. Show old/new SSA versions. |
| 20:00–26:00 | 6 | **Professor-directed live run 3:** new equations, preferably mixed parallel operators and time sharing; professor chooses mode/limits/values. Save to `live3.eqn`; repeat complete process and inspect selected units at cycle boundaries. |
| 26:00–29:00 | 3 | Show test summary and actual implementation/timing/utilization reports; demonstrate reset/restart and discuss resource/latency tradeoffs. |
| 29:00–30:00 | 1 | Answer final questions; show public repository URL and stop at 30:00. |

Use an explicit six-minute timer for each run. During synthesis/place/route, discuss that run's SSA/schedule/reference values; this does not substitute for programming and running its new bitstream. All three runs are professor-directed and may have completely new equations. This tool generates dedicated hardware, so arbitrary equation changes need a new bitstream; the initial FPGA does not secretly interpret equations.

Commands for one live run (replace input names and constants with the actual first-use names printed in the manifest):

```sh
python3 hls.py live1.eqn --out build/live1 --mode constrained-asap --adders 1 --subtractors 1 --multipliers 1 --switch-inputs A,B --export-ssa --simulate
python3 scripts/reference.py live1.eqn --manifest build/live1/manifest.json --value A=5 --value B=3
vivado -mode batch -source scripts/build_vivado.tcl -tclargs build/live1
vivado -mode batch -source scripts/program_vivado.tcl -tclargs build/live1/fpga_build/vivado/hls_demo.runs/impl_1/nexys_a7_top.bit
```

These commands target the tested Nexys A7-100T. On Windows, use `python` instead of `python3` where needed; if Icarus is unavailable, omit `--simulate` and run the generated testbench in Vivado before hardware testing. Check `board_map.md`, set input switches, START, inspect each scheduled cycle with STEP, and compare final registers to the reference. For extra external inputs add explicit `--const NAME=value` settings before generation. Never change equation files without regenerating/rebuilding the corresponding artifacts.

Prepared practice runs (the professor's choices replace these during the actual demo):

| Program | Inputs | Final results (decimal) | What it shows |
|---|---|---|---|
| `assignment.eqn` | A=5, B=3 | X=8, Y=13, Z=5, Q=15 | dependencies and all three operator types |
| `reassignment.eqn` | A=5, B=3 | X=24, Y=19, Z=43 | dynamic SSA renaming and preserved intermediates |
| `sharing.eqn` | A=5, B=3, C=2, D=1 | P=8, R=3, S=11, T=2, U=16, V=27, Q=25 | resource sharing and compile-time static inputs |

## Public repository submission and physical evidence

Unzip this project, create an empty **public** GitHub repository through your own account, and add this directory's contents. Commit source, README, tests, constraints, and generated textual artifacts in `build/`; exclude VCDs, simulator executables, and large tool project directories. Example, after creating the public repository:

```sh
git init
git add .
git commit -m "Implement EC551 HLS compiler and FPGA runtime"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/EC551-HLS.git
git push -u origin main
```

The confirmed board identity, tool version, displayed timing results, and confirmed physical tests are recorded in `docs/BOARD_RESULTS.md`. Before submission, attach the actual implementation reports and a photo or short recording, record measured build times, and complete the remaining live-run rehearsal. Verify the public URL while signed out. Submit that URL and sign up for a live presentation slot. GitHub publication, slot registration, physical programming, and a successful live demonstration are course actions that are not completed by downloading code.

## AI use

AI assistance was used to help debug code and refine code clarity and conciseness. AI assistance was also used to revise the project documentation.
