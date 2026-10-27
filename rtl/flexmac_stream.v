// One framed dot product at a time. mode4 is captured on command acceptance.
// PRODUCT_IMPL=0: shared decomposition; 1: separate units selected by a mux.
module flexmac_stream #(
    parameter integer PRODUCT_IMPL = 0
) (
    input wire clk,
    input wire rst,
    input wire start_valid,
    output wire start_ready,
    input wire mode4,
    input wire term_valid,
    output wire term_ready,
    input wire [7:0] a,
    input wire [7:0] b,
    input wire term_last,
    output wire result_valid,
    input wire result_ready,
    output wire signed [31:0] result
);
    localparam [1:0] IDLE=0, RUN=1, OUTPUT_RESULT=2;
    reg [1:0] state;
    reg captured_mode4;
    reg signed [31:0] accumulator;
    wire signed [15:0] term_product;
    wire signed [31:0] extended_product = {{16{term_product[15]}}, term_product};
    wire signed [31:0] sum_next = accumulator + extended_product;
    generate if (PRODUCT_IMPL == 0) begin: shared
        flexmac_product unit (.a(a), .b(b), .mode4(captured_mode4), .product(term_product));
    end else begin: separate
        flexmac_product_mux unit (.a(a), .b(b), .mode4(captured_mode4), .product(term_product));
    end endgenerate
    assign start_ready = !rst && (state == IDLE);
    assign term_ready = !rst && (state == RUN);
    assign result_valid = !rst && (state == OUTPUT_RESULT);
    assign result = result_valid ? accumulator : 32'sd0;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            accumulator <= 0;
            captured_mode4 <= 0;
        end else case (state)
            IDLE: if (start_valid && start_ready) begin
                captured_mode4 <= mode4;
                accumulator <= 0;
                state <= RUN;
            end
            RUN: if (term_valid && term_ready) begin
                accumulator <= sum_next;
                if (term_last) state <= OUTPUT_RESULT;
            end
            OUTPUT_RESULT: if (result_ready) state <= IDLE;
            default: begin
                state <= IDLE;
                accumulator <= 0;
            end
        endcase
    end
endmodule
