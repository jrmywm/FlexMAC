`timescale 1ns/1ps
// Compiled WITHOUT the trained ROM: the controlled model below tests negative
// score ordering and ties, which a particular dataset cannot guarantee.
module digits_model_rom(input mode4, input [9:0] weight_address,
    input [3:0] bias_class, output [7:0] weight, output signed [31:0] bias);
    assign weight = 0;
    assign bias = mode4 && bias_class == 9 ? 32'sd1 : -32'sd5;
endmodule
module tb_classifier_directed;
    parameter PRODUCT_IMPL = 0;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst = 1, start_valid = 0, mode4 = 0, feature_valid = 0, result_ready = 0;
    wire start_ready, feature_ready, result_valid;
    wire [3:0] result_class;
    wire signed [31:0] result_score;
    flexmac_classifier #(.PRODUCT_IMPL(PRODUCT_IMPL)) dut(clk, rst, start_valid, start_ready,
        mode4, feature_valid, feature_ready, 8'hff, result_valid, result_ready, result_class, result_score);
    integer m;
    initial begin
        repeat (2) @(negedge clk);
        rst = 0;
        for (m = 0; m < 2; m = m + 1) begin
            mode4 = m; start_valid = 1;
            @(negedge clk); start_valid = 0; feature_valid = 1;
            repeat (m ? 32 : 64) @(negedge clk);
            feature_valid = 0;
            while (!result_valid) @(negedge clk);
            if (result_class !== (m ? 4'd9 : 4'd0) || result_score !== (m ? 32'sd1 : -32'sd5))
                $fatal(1, "negative-score/tie selection failed");
            result_ready = 1;
            @(negedge clk); result_ready = 0;
        end
        $display("PASS directed classifier impl=%0d: all-negative ties, signed mixed-score ordering, class-nine winner", PRODUCT_IMPL);
        $finish;
    end
    initial begin #100000; $fatal(1, "directed watchdog"); end
endmodule
