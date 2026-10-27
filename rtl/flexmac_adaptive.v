// Input-conditioned agreement certificate, followed by INT8 when needed.
// FORCE_INT8 is a fair baseline with the same raw-pixel interface and checks.
module flexmac_adaptive #(
    parameter PRODUCT_IMPL = 0,
    parameter FORCE_INT8 = 0,
    // Two lanes apply only to the always-INT8 baseline; adaptive reruns stay serial.
    parameter INT8_LANES = 1
) (
    input wire clk, rst,
    input wire start_valid,
    output wire start_ready,
    input wire pixel_valid,
    output wire pixel_ready,
    input wire [4:0] pixel,
    output wire result_valid,
    input wire result_ready,
    output wire [3:0] result_class,
    output wire result_fallback,
    output wire result_error
);
    localparam IDLE=3'd0, LOAD=3'd1, EVAL4=3'd2, CHECK=3'd3, EVAL8=3'd4, RESULT=3'd5;
    reg [2:0] state;
    reg [4:0] pixels [0:63];
    reg [5:0] index;
    reg [3:0] class_index, best_class, check_index;
    reg signed [31:0] accumulator, best_score, residual_lower, residual_upper;
    reg signed [31:0] lower_scores [0:9], upper_scores [0:9];
    reg certified, fallback, input_error;
    wire mode4 = !FORCE_INT8 && state != EVAL8 && state != CHECK;
    wire paired = mode4 || (FORCE_INT8 && INT8_LANES == 2);
    wire [5:0] low_index = paired ? {index[4:0],1'b0} : index;
    wire [5:0] high_index = {index[4:0],1'b1};
    wire [7:0] quant8_low, quant8_high;
    wire [3:0] quant4_low, quant4_high;
    digits_pixel_quantizer qlow(pixels[low_index], quant8_low, quant4_low);
    digits_pixel_quantizer qhigh(pixels[high_index], quant8_high, quant4_high);
    wire [7:0] operand = mode4 ? {quant4_high, quant4_low} : quant8_low;
    wire [9:0] weight_address = mode4 ? {1'b0,class_index,index[4:0]} : {class_index,low_index};
    wire [3:0] bias_class = state == LOAD || state == CHECK ? 4'd0 : class_index+1'b1;
    wire [7:0] weight;
    wire signed [31:0] bias;
    digits_model_rom weights(mode4, weight_address, bias_class, weight, bias);
    wire signed [15:0] product;
    wire signed [16:0] beat_product;
    wire signed [12:0] lo0, hi0, lo1, hi1;
    wire signed [31:0] residual_bias;
    generate
        if (FORCE_INT8 && INT8_LANES == 2) begin : fixed_pair
            wire [7:0] weight_high;
            wire signed [31:0] unused_bias;
            digits_model_rom high_weights(1'b0, {class_index,high_index}, 4'd0, weight_high, unused_bias);
            flexmac_product_int8x2 core(quant8_low, weight, quant8_high, weight_high, beat_product);
            assign product=0;
            assign lo0=0; assign hi0=0; assign lo1=0; assign hi1=0;
            assign residual_bias=0;
        end else if (FORCE_INT8) begin : fixed_core
            flexmac_product_int8 core(operand, weight, product);
            assign beat_product={product[15],product};
            assign lo0=0; assign hi0=0; assign lo1=0; assign hi1=0;
            assign residual_bias=0;
        end else begin : configurable_core
            assign beat_product={product[15],product};
            if (PRODUCT_IMPL == 0) begin : shared_core
                flexmac_product core(operand, weight, mode4, product);
            end else begin : mux_core
                flexmac_product_mux core(operand, weight, mode4, product);
            end
            digits_residual_rom bounds_low(class_index,low_index,quant4_low,lo0,hi0);
            digits_residual_rom bounds_high(class_index,high_index,quant4_high,lo1,hi1);
            digits_residual_bias offsets(bias_class,residual_bias);
        end
    endgenerate
    wire signed [31:0] completed_score = accumulator + {{15{beat_product[16]}},beat_product};
    wire signed [31:0] scaled_score = completed_score * 32'sd366;
    wire signed [31:0] lower_complete = scaled_score + residual_lower + {{19{lo0[12]}},lo0} + {{19{lo1[12]}},lo1};
    wire signed [31:0] upper_complete = scaled_score + residual_upper + {{19{hi0[12]}},hi0} + {{19{hi1[12]}},hi1};
    wire last_index = paired ? index == 31 : index == 63;
    wire score_commit = !rst && (state == EVAL4 || state == EVAL8) && last_index;
    wire check_pass = check_index == best_class || lower_scores[best_class] > upper_scores[check_index];
    assign start_ready = !rst && state == IDLE;
    assign pixel_ready = !rst && state == LOAD;
    assign result_valid = !rst && state == RESULT;
    assign result_class = result_valid && !input_error ? best_class : 4'd0;
    assign result_fallback = result_valid && !input_error && fallback;
    assign result_error = result_valid && input_error;
    always @(posedge clk) begin
        if (rst) begin
            state<=IDLE; index<=0; class_index<=0; best_class<=0; check_index<=0;
            accumulator<=0; best_score<=0; residual_lower<=0; residual_upper<=0;
            certified<=0; fallback<=0; input_error<=0;
        end else case (state)
            IDLE: if (start_valid) begin
                state<=LOAD; index<=0; class_index<=0; best_class<=0;
                input_error<=0; fallback<=0;
            end
            LOAD: if (pixel_valid) begin
                pixels[index]<=pixel;
                if (pixel > 16) input_error<=1;
                if (index == 63) begin
                    index<=0; accumulator<=bias;
                    residual_lower<=residual_bias; residual_upper<=residual_bias;
                    if (input_error || pixel > 16) state<=RESULT;
                    else if (FORCE_INT8) state<=EVAL8;
                    else state<=EVAL4;
                end else index<=index+1'b1;
            end
            EVAL4: if (!FORCE_INT8) begin
                if (last_index) begin
                    lower_scores[class_index]<=lower_complete;
                    upper_scores[class_index]<=upper_complete;
                    if (class_index == 0 || completed_score > best_score) begin
                        best_score<=completed_score; best_class<=class_index;
                    end
                    if (class_index == 9) begin
                        state<=CHECK; check_index<=0; certified<=1;
                    end else begin
                        class_index<=class_index+1'b1; index<=0;
                        accumulator<=bias; residual_lower<=residual_bias; residual_upper<=residual_bias;
                    end
                end else begin
                    accumulator<=completed_score; index<=index+1'b1;
                    residual_lower<=residual_lower+{{19{lo0[12]}},lo0}+{{19{lo1[12]}},lo1};
                    residual_upper<=residual_upper+{{19{hi0[12]}},hi0}+{{19{hi1[12]}},hi1};
                end
            end
            CHECK: if (!FORCE_INT8) begin
                certified<=certified && check_pass;
                if (check_index == 9) begin
                    if (certified && check_pass) state<=RESULT;
                    else begin
                        state<=EVAL8; fallback<=1; class_index<=0; index<=0; accumulator<=bias;
                    end
                end else check_index<=check_index+1'b1;
            end
            EVAL8: begin
                if (last_index) begin
                    if (class_index == 0 || completed_score > best_score) begin
                        best_score<=completed_score; best_class<=class_index;
                    end
                    if (class_index == 9) state<=RESULT;
                    else begin class_index<=class_index+1'b1; index<=0; accumulator<=bias; end
                end else begin accumulator<=completed_score; index<=index+1'b1; end
            end
            RESULT: if (result_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
