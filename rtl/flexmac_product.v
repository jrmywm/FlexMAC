// Genuine shared partial-product implementation. Mode 4 sums two independent
// signed nibble products; mode 8 reconstructs one signed byte product.
module flexmac_product (
    input wire [7:0] a,
    input wire [7:0] b,
    input wire mode4,
    output wire signed [15:0] product
);
    // A signed byte is 16*its signed high nibble + its UNSIGNED low nibble.
    // In INT4 mode the low nibble instead becomes an independent signed value.
    wire signed [4:0] a_low = {mode4 && a[3], a[3:0]};
    wire signed [4:0] b_low = {mode4 && b[3], b[3:0]};
    wire signed [4:0] a_high = {a[7], a[7:4]};
    wire signed [4:0] b_high = {b[7], b[7:4]};
    // Cross products are unnecessary in INT4 mode. This is functional operand
    // isolation, not evidence of a measured power benefit.
    wire signed [4:0] cross_a_low = mode4 ? 5'sd0 : a_low;
    wire signed [4:0] cross_a_high = mode4 ? 5'sd0 : a_high;
    wire signed [9:0] p_ll = a_low * b_low;
    wire signed [9:0] p_hh = a_high * b_high;
    wire signed [9:0] p_lh = cross_a_low * b_high;
    wire signed [9:0] p_hl = cross_a_high * b_low;
    // Extend BEFORE shifting: Verilog shifts retain the left operand's width.
    wire signed [15:0] ll = {{6{p_ll[9]}}, p_ll};
    wire signed [15:0] hh = {{6{p_hh[9]}}, p_hh};
    wire signed [15:0] lh = {{6{p_lh[9]}}, p_lh};
    wire signed [15:0] hl = {{6{p_hl[9]}}, p_hl};
    assign product = mode4 ? ll + hh : ll + (lh <<< 4) + (hl <<< 4) + (hh <<< 8);
endmodule
