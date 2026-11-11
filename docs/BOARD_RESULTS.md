# Physical FPGA results

Updated from the user's Vivado screenshots and physical-test confirmations. These results describe the tested builds; they do not establish timing or behavior for every subsequently generated design.

## Hardware and implementation

| Item | Recorded result |
|---|---|
| Board | Digilent Nexys A7-100T; PCB revision not recorded |
| FPGA | `xc7a100tcsg324-1` (Artix-7, CSG324, speed -1) |
| Tools / OS | Vivado 2026.1 on Windows |
| Top / constraints | `nexys_a7_top` / `constraints/nexys_a7.xdc` |
| Arithmetic width / clock | Default 16-bit unsigned arithmetic; 100 MHz board oscillator |
| Synthesis / implementation / bitstream | Completed in the user's Vivado project |
| Programming | Hardware Manager showed `xc7a100t_0` as **Programmed**; startup status HIGH |
| GUI project used | `C:/Users/Owner/hls_demo/hls_demo.xpr` |
| GUI bitstream path | `C:/Users/Owner/hls_demo/hls_demo.runs/impl_1/nexys_a7_top.bit` |
| Source commit / bitstream hash | Not recorded; filenames alone do not identify a build uniquely |

The implemented-design screenshot showed the following timing summary:

| Metric | Displayed value |
|---|---:|
| Worst setup slack (WNS) | +2.618 ns |
| Total negative setup slack (TNS) | 0.000 ns |
| Worst hold slack (WHS) | +0.122 ns |
| Total hold slack (THS) | 0.000 ns |
| Worst pulse-width slack | +4.500 ns |
| Failing endpoints: setup / hold / pulse width | 0 / 0 / 0 |

The screenshot reported that all user-specified timing constraints were met. Full timing, unconstrained-path, DRC, and utilization reports have not been archived in this package. The screenshot was not tied to a source commit or bitstream hash, so these values must not be attributed to every example or schedule.

## Physical arithmetic checks

The user reported successful cycling through `assignment.eqn` and `reassignment.eqn`. Values below document the corresponding expected results that the user confirmed; they are not an automated capture of the display.

| Program | Inputs | SSA register results: decimal (four-digit hex) | Schedule |
|---|---|---|---|
| `assignment.eqn` | A=5, B=3 | X_1=8 (`0008`), Y_1=13 (`000D`), Z_1=5 (`0005`), Q_1=15 (`000F`) | Three cycles with default constrained ASAP |
| `assignment.eqn` | A=2, B=1 | X_1=3 (`0003`), Y_1=5 (`0005`), Z_1=2 (`0002`), Q_1=2 (`0002`) | Three cycles with default constrained ASAP |
| `reassignment.eqn` | A=5, B=3 | X_1=8 (`0008`), X_2=24 (`0018`), Y_1=19 (`0013`), Z_1=43 (`002B`) | Four cycles; constrained ASAP command shown by user |

Assignment inputs A=5, B=3 are captured with SW2, SW0, SW5, and SW4 on. Press BTN L to capture, then change switches for observation. BTN R advances one scheduled cycle; independent operations scheduled together commit on the same step.

| Control / observation | Recorded status |
|---|---|
| BTN C reset, BTN L capture/start, BTN R manual step | Exercised during the user's physical testing |
| SSA register selection with SW6=1, SW7=0 | User confirmed expected operation results |
| FU selection with SW6=0, SW7=0 | User exercised selected arithmetic-unit outputs; assignment multiplier showed `000F` after the final cycle |
| Status selection with SW7=1 | Assignment completion `4004` observed; busy/done bits encode status, low bits encode next phase |
| Every parallel unit under every schedule | Not individually recorded on physical hardware |
| BTN U automatic RUN / held-button behavior | Covered by the existing simulation record; separate physical confirmation not recorded here |

After START, switches select observations without changing the captured operands. Selector assignments depend on the generated design; use its `board_map.md`. For the assignment example, register selectors 0..3 are X, Y, Z, Q; FU selectors 0..2 are adder, subtractor, multiplier.

## Remaining evidence and rehearsal

- Archive Vivado timing, utilization, and DRC reports for the final demo build, plus a board photo or short recording.
- Record a source revision or bitstream hash and the selected equations, mode, resource limits, and width for that build.
- Measure generate → simulate → build → program time on the demo laptop.
- Rehearse three fresh professor-style equation runs, including parallelism and resource sharing. All five modes are covered by the software/RTL validation record; physical testing of every mode is not claimed here.
- Confirm the public repository URL and presentation registration separately.

A new equation file, schedule, resource configuration, or static-input value requires regeneration, bitstream rebuilding, and programming. The prior FPGA configuration continues running until a new bitstream is programmed.
