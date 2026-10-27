// Standalone conservative agreement checker. Scores arrive in class order 0..9.
// It certifies a CLASS decision; it does not claim an exact INT8 score.
module flexmac_agreement (
    input wire clk, rst,
    input wire start_valid,
    output wire start_ready,
    input wire [3:0] winner,
    input wire signed [31:0] winner_score,
    input wire score_valid,
    output wire score_ready,
    input wire signed [31:0] score,
    output wire result_valid,
    input wire result_ready,
    output wire result_certified
);
    localparam IDLE = 2'd0, CHECK = 2'd1, RESULT = 2'd2;
    reg [1:0] state;
    reg [3:0] captured_winner, index;
    reg signed [31:0] captured_score;
    reg certified;
    wire signed [31:0] threshold;
    digits_agreement_bounds bounds_rom(captured_winner, index, threshold);
    // A difference of two signed 32-bit scores requires 33 bits.
    wire signed [32:0] difference = {captured_score[31], captured_score} - {score[31], score};
    wire signed [32:0] extended_threshold = {threshold[31], threshold};
    wire passes = index == captured_winner ? score == captured_score : difference >= extended_threshold;
    assign start_ready = !rst && state == IDLE;
    assign score_ready = !rst && state == CHECK;
    assign result_valid = !rst && state == RESULT;
    assign result_certified = result_valid && certified;
    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE; captured_winner <= 0; captured_score <= 0; index <= 0; certified <= 0;
        end else case (state)
            IDLE: if (start_valid) begin
                captured_winner <= winner; captured_score <= winner_score;
                index <= 0; certified <= winner < 10; state <= CHECK;
            end
            CHECK: if (score_valid) begin
                certified <= certified && passes;
                if (index == 9) state <= RESULT;
                else index <= index + 1'b1;
            end
            RESULT: if (result_ready) state <= IDLE;
            default: state <= IDLE;
        endcase
    end
endmodule
