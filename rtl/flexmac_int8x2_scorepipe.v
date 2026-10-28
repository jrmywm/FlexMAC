// Always-INT8 paired MAC with a separate registered class-score comparison.
// The accumulator feedback stays unpipelined; only the terminal score is staged.
module flexmac_int8x2_scorepipe (
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
    localparam IDLE=3'd0, LOAD=3'd1, EVAL8=3'd4, RESULT=3'd5, COMPARE=3'd6;
    reg [2:0] state;
    reg [4:0] pixels [0:63];
    reg [5:0] index;
    reg [3:0] class_index, best_class, pending_class;
    reg signed [31:0] accumulator, best_score, pending_score;
    reg pending_last, input_error;
    wire [5:0] low_index={index[4:0],1'b0};
    wire [5:0] high_index={index[4:0],1'b1};
    wire [7:0] quant8_low, quant8_high, weight, weight_high;
    wire [3:0] unused_quant4_low, unused_quant4_high;
    wire [3:0] bias_class=state==LOAD ? 4'd0 : class_index+1'b1;
    wire signed [31:0] bias, unused_bias;
    wire signed [16:0] beat_product;
    digits_pixel_quantizer qlow(pixels[low_index],quant8_low,unused_quant4_low);
    digits_pixel_quantizer qhigh(pixels[high_index],quant8_high,unused_quant4_high);
    digits_model_rom weights(1'b0,{class_index,low_index},bias_class,weight,bias);
    digits_model_rom high_weights(1'b0,{class_index,high_index},4'd0,weight_high,unused_bias);
    flexmac_product_int8x2 core(quant8_low,weight,quant8_high,weight_high,beat_product);
    // Explicit 32-bit addition preserves the frozen modulo-2^32 score contract.
    wire signed [31:0] completed_score=accumulator+{{15{beat_product[16]}},beat_product};
    wire score_commit=!rst && state==EVAL8 && index==31;
    wire compare_commit=!rst && state==COMPARE;
    assign start_ready=!rst && state==IDLE;
    assign pixel_ready=!rst && state==LOAD;
    assign result_valid=!rst && state==RESULT;
    assign result_class=result_valid && !input_error ? best_class : 4'd0;
    assign result_fallback=1'b0;
    assign result_error=result_valid && input_error;
    always @(posedge clk) begin
        if(rst) begin
            state<=IDLE; index<=0; class_index<=0; best_class<=0;
            accumulator<=0; best_score<=0; pending_score<=0;
            pending_class<=0; pending_last<=0; input_error<=0;
        end else case(state)
            IDLE: if(start_valid) begin
                state<=LOAD; index<=0; class_index<=0; best_class<=0;
                input_error<=0;
            end
            LOAD: if(pixel_valid) begin
                pixels[index]<=pixel;
                if(pixel>16) input_error<=1;
                if(index==63) begin
                    index<=0; accumulator<=bias;
                    if(input_error || pixel>16) state<=RESULT;
                    else state<=EVAL8;
                end else index<=index+1'b1;
            end
            EVAL8: begin
                if(index==31) begin
                    pending_score<=completed_score;
                    pending_class<=class_index;
                    pending_last<=class_index==9;
                    state<=COMPARE;
                end else begin
                    accumulator<=completed_score; index<=index+1'b1;
                end
            end
            COMPARE: begin
                // Classes arrive in increasing order; strict > preserves ties.
                if(pending_class==0 || pending_score>best_score) begin
                    best_score<=pending_score; best_class<=pending_class;
                end
                if(pending_last) state<=RESULT;
                else begin
                    class_index<=class_index+1'b1; index<=0;
                    accumulator<=bias; state<=EVAL8;
                end
            end
            RESULT: if(result_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
