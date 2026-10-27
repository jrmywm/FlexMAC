// Complete fixed-precision baselines: no runtime precision port or second model.
module flexmac_classifier_int8 (
    input wire clk, rst, start_valid,
    output wire start_ready,
    input wire feature_valid,
    output wire feature_ready,
    input wire [7:0] feature_data,
    output wire result_valid,
    input wire result_ready,
    output wire [3:0] result_class,
    output wire signed [31:0] result_score
);
    flexmac_classifier #(.FIXED_MODE(0)) engine(clk, rst, start_valid, start_ready,
        1'b0, feature_valid, feature_ready, feature_data, result_valid, result_ready, result_class, result_score);
endmodule

module flexmac_classifier_int4 (
    input wire clk, rst, start_valid,
    output wire start_ready,
    input wire feature_valid,
    output wire feature_ready,
    input wire [7:0] feature_data,
    output wire result_valid,
    input wire result_ready,
    output wire [3:0] result_class,
    output wire signed [31:0] result_score
);
    flexmac_classifier #(.FIXED_MODE(1)) engine(clk, rst, start_valid, start_ready,
        1'b1, feature_valid, feature_ready, feature_data, result_valid, result_ready, result_class, result_score);
endmodule
