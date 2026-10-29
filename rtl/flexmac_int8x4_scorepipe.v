// Four-lane INT8 control: prevents attributing extra arithmetic parallelism to certification.
module flexmac_int8x4_scorepipe (
    input wire clk,rst,start_valid, output wire start_ready,
    input wire pixel_valid,output wire pixel_ready,input wire [4:0] pixel,
    output wire result_valid,input wire result_ready,output wire [3:0] result_class,
    output wire result_fallback,result_error
);
    localparam IDLE=0,LOAD=1,EVAL=2,COMPARE=3,RESULT=4;
    reg [2:0] state;
    reg [4:0] pixels[0:63];
    reg [5:0] index;
    reg [3:0] class_index,best_class;
    reg signed [31:0] accumulator,best_score,pending_score;
    reg input_error;
    wire [3:0] bias_class=state==LOAD ? 4'd0 : class_index+1'b1;
    wire signed [31:0] biases[0:3];
    wire signed [15:0] products[0:3];
    genvar lane;
    generate for(lane=0;lane<4;lane=lane+1) begin: lanes
        wire [5:0] address={index[3:0],2'b00}+lane;
        wire [7:0] q8,weight;
        wire [3:0] q4;
        digits_pixel_quantizer quant(pixels[address],q8,q4);
        digits_model_rom rom(1'b0,{class_index,address},bias_class,weight,biases[lane]);
        flexmac_product_int8 mult(q8,weight,products[lane]);
    end endgenerate
    wire signed [16:0] pair0={products[0][15],products[0]}+{products[1][15],products[1]};
    wire signed [16:0] pair1={products[2][15],products[2]}+{products[3][15],products[3]};
    wire signed [17:0] beat={pair0[16],pair0}+{pair1[16],pair1};
    wire signed [31:0] completed_score=accumulator+{{14{beat[17]}},beat};
    wire score_commit=!rst && state==EVAL && index==15;
    assign start_ready=!rst && state==IDLE;
    assign pixel_ready=!rst && state==LOAD;
    assign result_valid=!rst && state==RESULT;
    assign result_class=result_valid && !input_error ? best_class : 4'd0;
    assign result_fallback=0;
    assign result_error=result_valid && input_error;
    always @(posedge clk) begin
        if(rst) begin
            state<=IDLE;index<=0;class_index<=0;best_class<=0;
            accumulator<=0;best_score<=0;pending_score<=0;input_error<=0;
        end else case(state)
            IDLE: if(start_valid) begin state<=LOAD;index<=0;class_index<=0;best_class<=0;input_error<=0;end
            LOAD: if(pixel_valid) begin
                pixels[index]<=pixel;
                if(pixel>16) input_error<=1;
                if(index==63) begin
                    index<=0;accumulator<=biases[0];
                    state<=(input_error || pixel>16) ? RESULT : EVAL;
                end else index<=index+1'b1;
            end
            EVAL: if(index==15) begin pending_score<=completed_score;state<=COMPARE;end
                  else begin accumulator<=completed_score;index<=index+1'b1;end
            COMPARE: begin
                if(class_index==0 || pending_score>best_score) begin best_score<=pending_score;best_class<=class_index;end
                if(class_index==9) state<=RESULT;
                else begin class_index<=class_index+1'b1;index<=0;accumulator<=biases[0];state<=EVAL;end
            end
            RESULT: if(result_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
