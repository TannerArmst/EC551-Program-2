`timescale 1ns/1ps
// Integration test for build/demo (the assignment example), W=16.
// Short debounce interval makes bounce/hold tests fast; production default=20 ms.
module board_testbench;
reg clk=0; always #5 clk=~clk;
reg [7:0] sw=0;
reg reset=0, start=0, step=0, run=0;
wire [7:0] led;
wire [6:0] seg;
wire [3:0] an;
wire dp;
integer errors=0;
reg [5:0] before_phase;
board_runtime #(.DEBOUNCE(4)) dut(clk,sw,reset,start,step,run,led,seg,an,dp);
task clocks; input integer count; integer i; begin
    for(i=0;i<count;i=i+1) begin @(posedge clk); #1; end
end endtask
task check; input condition; input [511:0] message;
begin if(condition !== 1'b1) begin $display("FAIL board: %0s",message); errors=errors+1; end end endtask
initial begin
    clocks(280); check(dut.core.phase==0 && !dut.busy,"power-on reset");
    // Press/release shorter than debounce must not start a transaction.
    @(negedge clk); start=1; clocks(1);
    @(negedge clk); start=0; clocks(10);
    check(!dut.busy,"bounce rejected");
    // A=5 (low nibble), B=3 (high nibble).
    @(negedge clk); sw=8'h35; clocks(10);
    @(negedge clk); start=1; clocks(25);
    check(dut.busy && dut.phase==1,"start is one pulse despite hold");
    @(negedge clk); start=0; sw=0; clocks(12);
    // One long step press advances exactly one scheduled cycle.
    @(negedge clk); step=1; clocks(30);
    check(dut.phase==2,"held step advances once");
    check(dut.core.dp.r2==8,"inputs were captured on start: X=8");
    @(negedge clk); step=0; clocks(12);
    // Select adder 0, verify committed result remains visible while paused.
    check(led==8 && dut.fu_debug==8,"FU output selector");
    @(negedge clk); sw=8'h40; clocks(10);
    check(dut.reg_debug==8 && led==8,"register selector");
    @(negedge clk); sw=8'h80; clocks(10);
    check(dut.display_value==16'h8002,"busy/phase display");
    // Finish via manual single stepping, final Q=15.
    @(negedge clk); step=1; clocks(12);
    @(negedge clk); step=0; clocks(12);
    check(dut.phase==3,"second step");
    @(negedge clk); step=1; clocks(12);
    @(negedge clk); step=0; clocks(12);
    check(dut.done && !dut.busy && dut.phase==4,"manual completion");
    check(dut.outputs_bus==64'h000f0005000d0008,"all four board outputs");
    check(dp==0,"done decimal point");
    @(negedge clk); sw=8'h43; clocks(10);
    check(led==15,"Q register visible on LEDs");
    // Restart with A=2 B=1, then finish using RUN.
    @(negedge clk); sw=8'h12; clocks(10);
    @(negedge clk); start=1; clocks(12);
    @(negedge clk); start=0; clocks(12);
    @(negedge clk); run=1; clocks(20);
    check(dut.done && dut.outputs_bus==64'h0002000200050003,"run-to-completion and restart");
    @(negedge clk); run=0; reset=1; clocks(12);
    check(!dut.busy && !dut.done && dut.phase==0,"reset button");
    @(negedge clk); reset=0; clocks(12);
    // Invalid selector is deterministically zero.
    @(negedge clk); sw=8'h3f; clocks(10);
    check(led==0,"invalid FU selector");
    if(errors) $fatal(1,"%0d board errors",errors);
    $display("PASS: board startup, debounce, hold, input capture, step, run, selectors, reset");
    $finish;
end
initial begin #1000000; $fatal(1,"board timeout"); end
endmodule
