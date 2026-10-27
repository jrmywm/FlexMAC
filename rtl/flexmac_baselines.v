// Fixed-precision and deliberately unshared references for a fair comparison.
module flexmac_product_int8 (
    input wire [7:0] a, b,
    output wire signed [15:0] product
);
    wire signed [7:0] sa = a, sb = b;
    assign product = sa * sb;
endmodule

module flexmac_product_int4x2 (
    input wire [7:0] a, b,
    output wire signed [15:0] product
);
    wire signed [3:0] al = a[3:0], ah = a[7:4];
    wire signed [3:0] bl = b[3:0], bh = b[7:4];
    wire signed [7:0] low_product = al * bl;
    wire signed [7:0] high_product = ah * bh;
    assign product = {{8{low_product[7]}}, low_product}
                   + {{8{high_product[7]}}, high_product};
endmodule

module flexmac_product_mux (
    input wire [7:0] a, b,
    input wire mode4,
    output wire signed [15:0] product
);
    wire signed [15:0] p8, p4;
    flexmac_product_int8 i8 (.a(a), .b(b), .product(p8));
    flexmac_product_int4x2 i4 (.a(a), .b(b), .product(p4));
    assign product = mode4 ? p4 : p8;
endmodule
