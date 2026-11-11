# Validation record

The original software/RTL checks below were executed in a Linux environment with Python 3.12.14, Icarus Verilog 12.0, and Yosys 0.33. They are a historical validation record, separate from the subsequent Windows/Vivado and physical tests. Use `python3 --version` locally; Python 3.10 or newer is supported.

## Checks actually executed

| Check | Result |
|---|---|
| Nine Python unittest methods | PASS |
| 120 random source programs × five scheduling modes, independently evaluated and schedule/binding checked | PASS (600 schedules) |
| Five supplied programs × five modes | PASS (25 RTL simulations) |
| Eight random 20-equation programs × five modes | PASS (40 RTL simulations) |
| Padded constrained ALAP bound | PASS (one RTL simulation) |
| RTL widths covered | 4, 8, 16, 32, 64 |
| Generated RTL total | 66 simulations, each with directed and seeded random transactions |
| All eight committed example builds, full default 27-vector testbenches | PASS |
| Board runtime with short debounce for simulation | PASS: startup, bounce, held buttons, input capture, manual step, run, observation selectors, reset, restart |
| Nexys 3 and Nexys A7 top-level elaboration | PASS |
| Generic Yosys synthesis: `hls_core` | PASS, zero structural check failures |
| Generic Yosys synthesis: `nexys3_top` | PASS, zero structural check failures |
| Generic Yosys synthesis: `nexys_a7_top` | PASS, zero structural check failures |

Each RTL simulation checks every SSA result and each shared FU's last committed output after each scheduled cycle, as well as final output lanes, stalls, input snapshot, ignored start while busy, completion, reset and restart. Random arithmetic may wrap intentionally under the documented unsigned W-bit semantics.

Commands:

```sh
python3 scripts/verify.py --require-rtl
python3 scripts/check_synthesis.py build/demo
python3 scripts/check_synthesis.py build/demo --top nexys3_top
python3 scripts/check_synthesis.py build/demo --top nexys_a7_top
```

The verifier's terminal summary:

```text
PASS: Python tests, 66 generated RTL simulations, board integration, both board wrappers
```

The committed example generator was also run, and the sharing example's reference values were checked with A=5, B=3, C=2, D=1.

## Subsequent Windows/Vivado and physical checks

The user subsequently used Vivado 2026.1 on Windows with a Nexys A7-100T (`xc7a100tcsg324-1`). A Vivado simulation reported:

```text
PASS: all transactions, cycle registers, shared FUs, stalls, reset and restart
```

Screenshots showed successful bitstream generation and a programmed device. The implemented-design timing screenshot showed positive setup, hold, and pulse-width slack with zero failing endpoints. The user confirmed physical arithmetic results for the assignment and reassignment examples and exercised stepping and observation controls. See [BOARD_RESULTS.md](BOARD_RESULTS.md) for exact values, evidence limits, and outstanding measurements.

During the current ZIP review, all nine Python test methods passed again. `scripts/verify.py` explicitly skipped RTL because Icarus was unavailable in the review environment; the historical 66-simulation result was not rerun during that review. No vendor build script was rerun here. The user used a Vivado GUI project; successful GUI implementation does not independently validate the supplied batch scripts.

## Checks still to record

Full device timing/DRC/utilization report files, unconstrained-path review, exact source/bitstream identity, measured build time, and physical results for every scheduling mode have not been archived. The three professor-directed live runs, presentation, and public repository submission are not established by the tests above. Nexys 3/ISE deployment has not been physically confirmed.

Pins were checked against the manufacturer references linked in README; the actual tested target is the Nexys A7-100T.
