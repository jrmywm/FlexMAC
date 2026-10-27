// Two independent signed INT8 products summed into one dot-product term.
module flexmac_product_int8x2 (
    input wire [7:0] a0, b0, a1, b1,
    output wire signed [16:0] product
);
    wire signed [15:0] p0, p1;
    flexmac_product_int8 lane0(a0, b0, p0);
    flexmac_product_int8 lane1(a1, b1, p1);
    // (-128)*(-128) twice is +32768, which requires signed 17 bits.
    assign product = {p0[15], p0} + {p1[15], p1};
endmodule
