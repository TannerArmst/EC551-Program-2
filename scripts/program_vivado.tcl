# Usage: vivado -mode batch -source scripts/program_vivado.tcl -tclargs PATH.bit
if {$argc != 1} {error "Specify one .bit file"}
open_hw_manager
connect_hw_server
open_hw_target
set devices [get_hw_devices -filter {PART =~ "xc7a*"}]
if {[llength $devices] != 1} {error "Expected exactly one attached Artix-7; select device manually"}
set device [lindex $devices 0]
current_hw_device $device
set_property PROGRAM.FILE [file normalize [lindex $argv 0]] $device
program_hw_devices $device
refresh_hw_device $device
close_hw_manager
