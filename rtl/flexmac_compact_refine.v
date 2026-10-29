// Compact pairwise certification plus selective exact INT8 class refinement.
// Four INT4 products or two INT8 products per cycle; two shared product cores.
// Bounds are valid only for the frozen model and supported raw pixels [0,16].
module flexmac_compact_refine (
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
    localparam IDLE=0, LOAD=1, LOW=2, LOW_COMPARE=3, CHECK=4,
               SELECT=5, EXACT=6, EXACT_COMPARE=7, RESULT=8;
    reg [3:0] state;
    reg [4:0] pixels [0:63];
    // Domain-wide frozen-model INT4 range is [-568,600], including its bias.
    reg signed [10:0] low_scores [0:9];
    reg [5:0] index;
    reg [3:0] class_index, best_class, candidate, check_index;
    reg signed [31:0] accumulator, pending_score, best_score;
    reg signed [10:0] candidate_score;
    reg [9:0] active;
    reg uncertain, have_exact, fallback, input_error;
    wire mode4 = !fallback;
    wire [5:0] base = mode4 ? {index[3:0],2'b00} : {index[4:0],1'b0};
    wire [5:0] p1=base+6'd1, p2=base+6'd2, p3=base+6'd3;
    wire [7:0] q80,q81,q82,q83;
    wire [3:0] q40,q41,q42,q43;
    digits_pixel_quantizer q0(pixels[base],q80,q40);
    digits_pixel_quantizer q1(pixels[p1],q81,q41);
    digits_pixel_quantizer q2(pixels[p2],q82,q42);
    digits_pixel_quantizer q3(pixels[p3],q83,q43);
    // class_index always names the active class; biases are loaded explicitly.
    wire [7:0] w0,w1;
    wire signed [31:0] bias,unused_bias;
    wire [9:0] a0=mode4 ? {1'b0,class_index,index[3:0],1'b0} : {class_index,base};
    wire [9:0] a1=mode4 ? {1'b0,class_index,index[3:0],1'b1} : {class_index,p1};
    digits_model_rom r0(mode4,a0,class_index,w0,bias);
    digits_model_rom r1(mode4,a1,4'd0,w1,unused_bias);
    wire signed [15:0] product0,product1;
    flexmac_product m0(mode4 ? {q41,q40} : q80,w0,mode4,product0);
    flexmac_product m1(mode4 ? {q43,q42} : q81,w1,mode4,product1);
    wire signed [16:0] beat_product={product0[15],product0}+{product1[15],product1};
    wire signed [31:0] completed_score=accumulator+{{15{beat_product[16]}},beat_product};
    wire signed [31:0] threshold;
    digits_agreement_bounds bounds(candidate,check_index,threshold);
    wire signed [11:0] difference={candidate_score[10],candidate_score}-
        {low_scores[check_index][10],low_scores[check_index]};
    wire signed [32:0] extended_threshold={threshold[31],threshold};
    wire safe_rival=difference >= extended_threshold;
    wire score_commit=!rst && ((state==LOW && index==15) || (state==EXACT && index==31));
    assign start_ready=!rst && state==IDLE;
    assign pixel_ready=!rst && state==LOAD;
    assign result_valid=!rst && state==RESULT;
    assign result_class=result_valid && !input_error ? best_class : 4'd0;
    assign result_fallback=result_valid && !input_error && fallback;
    assign result_error=result_valid && input_error;
    always @(posedge clk) begin
        if(rst) begin
            state<=IDLE; index<=0; class_index<=0; best_class<=0; candidate<=0;
            check_index<=0; accumulator<=0; pending_score<=0; best_score<=0;
            candidate_score<=0; active<=0; uncertain<=0; have_exact<=0;
            fallback<=0; input_error<=0;
        end else case(state)
            IDLE: if(start_valid) begin
                state<=LOAD; index<=0; class_index<=0; best_class<=0;
                input_error<=0; fallback<=0; active<=0; have_exact<=0;
            end
            LOAD: if(pixel_valid) begin
                pixels[index]<=pixel;
                if(pixel>16) input_error<=1;
                if(index==63) begin
                    index<=0; accumulator<=bias;
                    state<=(input_error || pixel>16) ? RESULT : LOW;
                end else index<=index+1'b1;
            end
            LOW: if(index==15) begin
                pending_score<=completed_score; state<=LOW_COMPARE;
            end else begin accumulator<=completed_score; index<=index+1'b1; end
            LOW_COMPARE: begin
                low_scores[class_index]<=pending_score;
                if(class_index==0 || pending_score>best_score) begin
                    best_score<=pending_score; best_class<=class_index;
                end
                if(class_index==9) begin
                    candidate<=pending_score>best_score ? class_index : best_class;
                    candidate_score<=pending_score>best_score ? pending_score : best_score;
                    state<=CHECK; check_index<=0; uncertain<=0;
                end else begin
                    class_index<=class_index+1'b1; index<=0; state<=SELECT;
                end
            end
            CHECK: begin
                active[check_index]<=check_index==candidate || !safe_rival;
                if(check_index!=candidate && !safe_rival) uncertain<=1;
                if(check_index==9) begin
                    if(uncertain || (check_index!=candidate && !safe_rival)) begin
                        fallback<=1; have_exact<=0; class_index<=0; state<=SELECT;
                    end else state<=RESULT;
                end else check_index<=check_index+1'b1;
            end
            SELECT: begin
                index<=0; accumulator<=bias;
                if(!fallback) state<=LOW;
                else if(active[class_index]) state<=EXACT;
                else if(class_index==9) state<=RESULT;
                else class_index<=class_index+1'b1;
            end
            EXACT: if(index==31) begin
                pending_score<=completed_score; state<=EXACT_COMPARE;
            end else begin accumulator<=completed_score; index<=index+1'b1; end
            EXACT_COMPARE: begin
                // Active classes are visited in ascending order; strict > keeps ties.
                if(!have_exact || pending_score>best_score) begin
                    best_score<=pending_score; best_class<=class_index;
                end
                have_exact<=1;
                if(class_index==9) state<=RESULT;
                else begin class_index<=class_index+1'b1; state<=SELECT; end
            end
            RESULT: if(result_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
