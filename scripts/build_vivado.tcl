# Usage: vivado -mode batch -source scripts/build_vivado.tcl -tclargs build/demo [xc7a100tcsg324-1]
# Nexys A7 only. Nexys 3 requires ISE, see build_ise.py.
if {$argc < 1} { error "Specify generated directory" }
set generated [file normalize [lindex $argv 0]]
set part xc7a100tcsg324-1
if {$argc > 1} {set part [lindex $argv 1]}
set repo [file normalize [file join [file dirname [info script]] ..]]
set dest [file join $generated fpga_build vivado]
create_project -force hls_demo $dest -part $part
set f [open [file join $generated sources.f] r]
foreach source [split [read $f] "\n"] {
    if {$source ne ""} { add_files [file join $generated $source] }
}
close $f
add_files -fileset constrs_1 [file join $repo constraints nexys_a7.xdc]
set_property top nexys_a7_top [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
open_run impl_1
report_utilization -file [file join $generated utilization.rpt]
report_timing_summary -file [file join $generated timing.rpt]
report_drc -file [file join $generated drc.rpt]
if {[get_property SLACK [get_timing_paths -max_paths 1]] < 0} {error "Timing failed; do not use this bitstream"}
puts "Bitstream: [file join $dest hls_demo.runs impl_1 nexys_a7_top.bit]"
