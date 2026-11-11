`timescale 1ns/1ps
// 100 MHz clock. COUNT=2,000,000 => 20 ms stable before changing level.
// A synchronized, debounced rising edge produces exactly one pulse per press.
module button_filter #(parameter COUNT=2000000)(input clk, input rst, input raw,
    output reg level, output reg pulse);
function integer clog2;
    input integer value;
    integer v;
    begin v=value-1; clog2=0; while(v>0) begin clog2=clog2+1; v=v>>1; end end
endfunction
localparam CW = (COUNT<2) ? 1 : clog2(COUNT);
(* ASYNC_REG = "TRUE" *) reg meta, sync;
reg [CW-1:0] count;
always @(posedge clk) begin
    if (rst) begin meta<=0; sync<=0; level<=0; pulse<=0; count<=0; end
    else begin
        meta<=raw; sync<=meta; pulse<=0;
        if (sync==level) count<=0;
        else if (count==COUNT-1) begin
            count<=0; level<=sync; pulse<=sync;
        end else count<=count+1'b1;
    end
end
endmodule

// Digilent common-anode display: seg[0]=a,...seg[6]=g. All active low.
module hex_display(input clk, input rst, input [15:0] value,
    output reg [6:0] seg, output reg [3:0] an);
reg [16:0] divider;
reg [3:0] digit;
always @(posedge clk) begin
    if (rst) divider<=0;
    else divider<=divider+1'b1;
end
always @* begin
    case (divider[16:15])
        0: begin an=4'b1110; digit=value[3:0]; end
        1: begin an=4'b1101; digit=value[7:4]; end
        2: begin an=4'b1011; digit=value[11:8]; end
        default: begin an=4'b0111; digit=value[15:12]; end
    endcase
    case (digit)
        4'h0: seg=7'b1000000; 4'h1: seg=7'b1111001;
        4'h2: seg=7'b0100100; 4'h3: seg=7'b0110000;
        4'h4: seg=7'b0011001; 4'h5: seg=7'b0010010;
        4'h6: seg=7'b0000010; 4'h7: seg=7'b1111000;
        4'h8: seg=7'b0000000; 4'h9: seg=7'b0010000;
        4'ha: seg=7'b0001000; 4'hb: seg=7'b0000011;
        4'hc: seg=7'b1000110; 4'hd: seg=7'b0100001;
        4'he: seg=7'b0000110; default: seg=7'b0001110;
    endcase
end
endmodule
