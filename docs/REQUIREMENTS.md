# Assignment Rev 2.0 requirement mapping

| Assignment item | Implementation | Evidence / remaining action |
|---|---|---|
| 1. Read up to 20 binary arithmetic equations | `hls.py: parse`; addition, subtraction, multiplication, identifiers and constants | Grammar/error/max-length tests; example files |
| 2. Dynamic SSA renaming, requested export | `parse`, `Program.ssa`, `--export-ssa [FILE]` | Reassignment/self-read tests, generated `ssa.txt` |
| 3. Operator-node dependency DAG | `graph`; SSA producers and dependencies; generated `dag.dot` | Dependency tests and randomized schedule validation |
| ASAP | `schedule(..., 'asap')` | Exact schedule test; generated parallel example; RTL tests |
| Constrained ASAP | Forward resource-constrained list scheduling | Per-cycle capacity and binding checks; RTL tests |
| ALAP | Reverse scheduling, optional explicit latency bound | Exact bound test; padded schedule RTL test |
| Constrained ALAP | Reverse list scheduling with resource capacities | Random DAG and RTL tests; capacity checks |
| Custom schedule | Longest-remaining-path and fanout priority list scheduling | Demonstrated 4-to-3-cycle improvement in unit test |
| 4. Mux/register datapath and sequencer | Emitted `hls_datapath.v`, `hls_control.v` | Cycle-by-cycle register/FU observations; generic synthesis |
| 5. Modular Verilog units | `rtl/functional_units.v` | Three independent parameterized modules; operator/width RTL coverage |
| 5. Chosen practical width and physical inputs | Default 16-bit arithmetic; two 4-bit switch inputs; remaining input constants | Generated board map; board integration simulation |
| 6. Composite system and precise unit counts | `bind` peak counts; `hls_core`; per-cycle operand muxes and writes | Manifest, source inspection, binding tests, synthesis |
| 6. Comprehensive `testbench.v` | Generated golden sequential values, stalls, snapshots, busy start, reset, restart, selectors | 66 generated RTL simulations in default verifier |
| Rev 2: external button stepping | Synchronized/debounced STEP emits one clock enable | Bounce and held-button board simulation; physical manual stepping exercised |
| Rev 2: selectable unit observability | All physical FUs have an observation register; switch-indexed output mux | Checks of every unit in simulation; physical assignment FU selection exercised |
| 7. FPGA output mechanism | LEDs, multiplexed 4-digit hex display, done point, status view | Board RTL simulation plus user-confirmed Nexys A7 physical outputs; see `BOARD_RESULTS.md` |
| 7. Synthesis/place/route/flash | Target constraints, ISE build script, Vivado build/program scripts, GUI instructions | Vivado GUI implementation/bitstream generation and Nexys A7 programming confirmed; full reports and batch-script validation remain |
| 8. Comprehensive README, architecture/build/run | `README.md` | Included |
| 8. Strict 30-minute plan and three custom live runs | README timeline totals 30 minutes with three six-minute custom compile/build/run slots | Rehearse on actual machine; meet measured build-time precondition |
| Public GitHub submission | Ready-to-upload repository contents and Git commands | User must publish repository and submit public URL |
| Presentation slot | README pre-demo procedure | User must register |

Physical Nexys A7 deployment and the confirmed arithmetic checks are recorded in `BOARD_RESULTS.md`. Archive the remaining reports and evidence, rehearse the professor-directed runs, and complete public submission and the live presentation separately.
