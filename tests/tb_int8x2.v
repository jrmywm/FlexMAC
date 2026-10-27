`timescale 1ns/1ps
module tb_int8x2;
    reg [7:0] a0,b0,a1,b1;
    wire signed [16:0] product;
    flexmac_product_int8x2 dut(a0,b0,a1,b1,product);
    reg [7:0] boundary [0:7];
    integer i,j,k,l,expected,count=0;
    function integer signed8(input [7:0] value);
        begin signed8=value; if(value[7]) signed8=signed8-256; end
    endfunction
    initial begin
        boundary[0]=0;boundary[1]=1;boundary[2]=127;boundary[3]=128;
        boundary[4]=255;boundary[5]=64;boundary[6]=192;boundary[7]=85;
        for(i=0;i<8;i=i+1) for(j=0;j<8;j=j+1)
            for(k=0;k<8;k=k+1) for(l=0;l<8;l=l+1) begin
                a0=boundary[i];b0=boundary[j];a1=boundary[k];b1=boundary[l];
                #1;
                expected=signed8(a0)*signed8(b0)+signed8(a1)*signed8(b1);
                if($signed(product)!==expected) $fatal(1,"two-lane product mismatch got=%0d expected=%0d",product,expected);
                count=count+1;
            end
        $display("PASS INT8x2: %0d signed-boundary combinations, including +32768",count);
        $finish;
    end
endmodule
