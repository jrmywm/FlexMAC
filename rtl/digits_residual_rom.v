// Generated exact conditioned residual ranges. No empirical extrema.
module digits_residual_rom(input wire [3:0] class_index, input wire [5:0] feature_index,
    input wire [3:0] quantized_pixel, output wire signed [12:0] lower, upper);
    reg [25:0] ranges [0:16383];
    initial $readmemh("model/agreement/residual_ranges.hex", ranges);
    wire [25:0] range_bits = ranges[{class_index, feature_index, quantized_pixel}];
    assign lower = range_bits[25:13];
    assign upper = range_bits[12:0];
endmodule
module digits_residual_bias(input wire [3:0] class_index, output reg signed [31:0] bias);
    always @* begin
        bias = 0;
        case (class_index)
            4'd0: bias = 32'h0000001c;
            4'd1: bias = 32'h00000018;
            4'd2: bias = 32'hffffffa4;
            4'd3: bias = 32'h000000b7;
            4'd4: bias = 32'h00000006;
            4'd5: bias = 32'h00000066;
            4'd6: bias = 32'h00000007;
            4'd7: bias = 32'h0000003c;
            4'd8: bias = 32'hffffff6a;
            4'd9: bias = 32'hffffff58;
            default: bias = 0;
        endcase
    end
endmodule
