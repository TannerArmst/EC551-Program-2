`timescale 1ns/1ps
// W-bit unsigned arithmetic. Carry/high product bits are discarded explicitly
// by assignment to W-bit y. The scheduled destination register supplies latency.
module hls_add #(parameter W=16)(input [W-1:0] a,b, output [W-1:0] y);
assign y = a + b;
endmodule
module hls_sub #(parameter W=16)(input [W-1:0] a,b, output [W-1:0] y);
assign y = a - b;
endmodule
module hls_mul #(parameter W=16)(input [W-1:0] a,b, output [W-1:0] y);
assign y = a * b;
endmodule
