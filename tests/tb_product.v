`timescale 1ns/1ps
module tb_product;
    reg [7:0] a, b;
    reg mode4;
    wire signed [15:0] shared_product, mux_product, p8, p4;
    flexmac_product dut (.a(a),.b(b),.mode4(mode4),.product(shared_product));
    flexmac_product_mux reference_mux (.a(a),.b(b),.mode4(mode4),.product(mux_product));
    flexmac_product_int8 reference8 (.a(a),.b(b),.product(p8));
    flexmac_product_int4x2 reference4 (.a(a),.b(b),.product(p4));
    reg [4095:0] path;
    integer fd, rc, m, expected, count = 0;
    initial begin
        if (!$value$plusargs("vectors=%s",path)) $fatal(1,"Missing vectors");
        fd = $fopen(path,"r");
        if (!fd) $fatal(1,"Cannot open product vectors");
        while (!$feof(fd)) begin
            rc = $fscanf(fd,"%d %h %h %d\n",m,a,b,expected);
            if (rc == 4) begin
                mode4 = m; #1;
                if (shared_product !== expected[15:0])
                    $fatal(1,"shared product mismatch mode=%d a=%h b=%h actual=%d expected=%d",m,a,b,shared_product,expected);
                if (mux_product !== expected[15:0]) $fatal(1,"mux product mismatch");
                if (!mode4 && p8 !== expected[15:0]) $fatal(1,"INT8 baseline mismatch");
                if (mode4 && p4 !== expected[15:0]) $fatal(1,"INT4 baseline mismatch");
                count = count+1;
            end else if (!$feof(fd)) $fatal(1,"Malformed product vector");
        end
        $fclose(fd);
        if (count != 131072) $fatal(1,"Incomplete exhaustive test count=%d",count);
        $display("PASS exhaustive products: 65536 input pairs per mode, total=%0d",count);
        $finish;
    end
endmodule
