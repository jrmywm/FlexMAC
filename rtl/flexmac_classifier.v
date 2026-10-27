// Fixed 64-feature, ten-class linear classifier. No host-side scoring/argmax.
module flexmac_classifier #(
    parameter PRODUCT_IMPL = 0,
    // -1: runtime configurable; 0: fixed INT8; 1: fixed two-lane INT4.
    parameter FIXED_MODE = -1
) (
    input wire clk,
    input wire rst,
    input wire start_valid,
    output wire start_ready,
    input wire mode4,
    input wire feature_valid,
    output wire feature_ready,
    input wire [7:0] feature_data,
    output wire result_valid,
    input wire result_ready,
    output wire [3:0] result_class,
    output wire signed [31:0] result_score
);
    localparam IDLE = 2'd0, LOAD = 2'd1, EVALUATE = 2'd2, RESULT = 2'd3;
    reg [1:0] state;
    reg precision4;
    wire use_int4 = FIXED_MODE < 0 ? precision4 : FIXED_MODE == 1;
    reg [5:0] index;
    reg [3:0] class_index;
    // Reset does not clear this bank. A complete new input is mandatory before
    // evaluation, including after reset, so stale entries are never consumed.
    localparam FEATURE_BYTES = FIXED_MODE == 1 ? 32 : 64;
    reg [7:0] features [0:FEATURE_BYTES-1];
    reg signed [31:0] accumulator;
    reg signed [31:0] best_score;
    reg [3:0] best_class;
    wire last_index = use_int4 ? index == 6'd31 : index == 6'd63;
    wire [9:0] weight_address = use_int4 ? {1'b0, class_index, index[4:0]} : {class_index, index};
    wire [3:0] bias_class = state == LOAD ? 4'd0 : class_index + 4'd1;
    wire [7:0] weight;
    wire signed [31:0] bias;
    digits_model_rom model_rom(use_int4, weight_address, bias_class, weight, bias);
    wire signed [15:0] product;
    generate
        if (FIXED_MODE == 0) begin : fixed_int8
            flexmac_product_int8 core(features[index], weight, product);
        end else if (FIXED_MODE == 1) begin : fixed_int4
            flexmac_product_int4x2 core(features[index], weight, product);
        end else if (PRODUCT_IMPL == 0) begin : shared_core
            flexmac_product core(features[index], weight, use_int4, product);
        end else begin : mux_core
            flexmac_product_mux core(features[index], weight, use_int4, product);
        end
    endgenerate
    // Exposed hierarchically to the testbench: no debug output registers.
    wire signed [31:0] completed_score = accumulator + {{16{product[15]}}, product};
    wire score_commit = !rst && state == EVALUATE && last_index;
    wire better = class_index == 0 || completed_score > best_score;
    assign start_ready = !rst && state == IDLE;
    assign feature_ready = !rst && state == LOAD;
    assign result_valid = !rst && state == RESULT;
    assign result_class = result_valid ? best_class : 4'd0;
    assign result_score = result_valid ? best_score : 32'sd0;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            precision4 <= 0;
            index <= 0;
            class_index <= 0;
            accumulator <= 0;
            best_score <= 0;
            best_class <= 0;
        end else begin
            case (state)
                IDLE: if (start_valid) begin
                    precision4 <= mode4;
                    index <= 0;
                    class_index <= 0;
                    best_class <= 0;
                    best_score <= 0;
                    state <= LOAD;
                end
                LOAD: if (feature_valid) begin
                    features[index] <= feature_data;
                    if (last_index) begin
                        index <= 0;
                        accumulator <= bias;
                        state <= EVALUATE;
                    end else index <= index + 1'b1;
                end
                EVALUATE: begin
                    if (last_index) begin
                        // Strict signed comparison keeps the lowest class on ties.
                        if (better) begin
                            best_score <= completed_score;
                            best_class <= class_index;
                        end
                        if (class_index == 4'd9) state <= RESULT;
                        else begin
                            class_index <= class_index + 1'b1;
                            index <= 0;
                            accumulator <= bias;
                        end
                    end else begin
                        accumulator <= completed_score;
                        index <= index + 1'b1;
                    end
                end
                RESULT: if (result_ready) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
