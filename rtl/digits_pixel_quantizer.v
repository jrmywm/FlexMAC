// Exact frozen preprocessing for a raw 5-bit pixel. Values 17..31 are invalid.
module digits_pixel_quantizer(input wire [4:0] pixel,
    output reg [7:0] int8_value, output reg [3:0] int4_value);
    always @* begin
        int8_value = 0; int4_value = 0;
        case (pixel)
            0: begin int8_value = -8'sd127; int4_value = -4'sd7; end
            1: begin int8_value = -8'sd111; int4_value = -4'sd6; end
            2: begin int8_value = -8'sd95; int4_value = -4'sd5; end
            3: begin int8_value = -8'sd79; int4_value = -4'sd4; end
            4: begin int8_value = -8'sd64; int4_value = -4'sd4; end
            5: begin int8_value = -8'sd48; int4_value = -4'sd3; end
            6: begin int8_value = -8'sd32; int4_value = -4'sd2; end
            7: begin int8_value = -8'sd16; int4_value = -4'sd1; end
            8: begin int8_value = 0; int4_value = 0; end
            9: begin int8_value = 8'sd16; int4_value = 4'sd1; end
            10: begin int8_value = 8'sd32; int4_value = 4'sd2; end
            11: begin int8_value = 8'sd48; int4_value = 4'sd3; end
            12: begin int8_value = 8'sd64; int4_value = 4'sd4; end
            13: begin int8_value = 8'sd79; int4_value = 4'sd4; end
            14: begin int8_value = 8'sd95; int4_value = 4'sd5; end
            15: begin int8_value = 8'sd111; int4_value = 4'sd6; end
            16: begin int8_value = 8'sd127; int4_value = 4'sd7; end
            default: begin int8_value = 0; int4_value = 0; end
        endcase
    end
endmodule
