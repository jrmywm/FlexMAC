`timescale 1ns/1ps
module tb_stream;
    parameter integer PRODUCT_IMPL = 0;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst = 1, start_valid = 0, mode4 = 0, term_valid = 0, term_last = 0, result_ready = 0;
    reg [7:0] a = 0, b = 0;
    wire start_ready, term_ready, result_valid;
    wire signed [31:0] result;
    flexmac_stream #(.PRODUCT_IMPL(PRODUCT_IMPL)) dut (.*);
    reg [4095:0] path, output_path, vcd_path;
    integer fd, out_fd, rc, m, length, stalls, frame = 0, i, j;
    integer accepted_at, produced_at, consumed_at;
    reg [31:0] expected;
    reg [7:0] av, bv;

    task start_frame;
        input integer selected_mode;
        begin
            @(negedge clk); start_valid = 1; mode4 = selected_mode;
            term_valid = 0; term_last = 0; result_ready = 0;
            #1; if (start_ready !== 1 || term_ready !== 0 || result_valid !== 0)
                $fatal(1,"Cannot accept a frame command");
            @(posedge clk); accepted_at = $time; #1;
            if (start_ready !== 0 || term_ready !== 1) $fatal(1,"Command handshake failed");
            @(negedge clk); start_valid = 0; mode4 = !selected_mode;
        end
    endtask

    task reset_engine;
        begin
            @(negedge clk); rst = 1; start_valid = 0; term_valid = 0; result_ready = 0;
            @(posedge clk); #1;
            if (start_ready !== 0 || term_ready !== 0 || result_valid !== 0 || result !== 0)
                $fatal(1,"Active interface during reset");
            @(negedge clk); rst = 0;
            @(posedge clk); #1;
            if (start_ready !== 1 || result_valid !== 0) $fatal(1,"Reset recovery failed");
        end
    endtask

    initial begin
        if (!$value$plusargs("frames=%s",path)) $fatal(1,"Missing frames");
        if (!$value$plusargs("results=%s",output_path)) $fatal(1,"Missing results");
        if ($value$plusargs("vcd=%s",vcd_path)) begin
            $dumpfile(vcd_path); $dumpvars(0,tb_stream);
        end
        fd = $fopen(path,"r"); out_fd = $fopen(output_path,"w");
        if (!fd || !out_fd) $fatal(1,"Cannot open stream files");
        $fdisplay(out_fd,"frame,mode4,beats,result_hex,command_to_production_cycles,held_cycles");
        reset_engine;
        // Cancel a partially accumulated frame.
        start_frame(0);
        a = 8'd2; b = 8'd3; term_valid = 1; term_last = 0;
        @(posedge clk); #1;
        if (result_valid !== 0) $fatal(1,"Premature partial result");
        reset_engine;
        // Cancel a completed but stalled output.
        start_frame(1);
        a = 8'h22; b = 8'h33; term_valid = 1; term_last = 1;
        @(posedge clk); #1;
        if (result_valid !== 1 || result !== 32'd12) $fatal(1,"Reset canary result wrong");
        reset_engine;
        while (!$feof(fd)) begin
            rc = $fscanf(fd,"%d %d %d %h\n",m,length,stalls,expected);
            if (rc == 4) begin
                if (length < 1) $fatal(1,"Empty frame is not supported");
                start_frame(m);
                for (i=0;i<length;i=i+1) begin
                    rc = $fscanf(fd,"%h %h\n",av,bv);
                    if (rc != 2) $fatal(1,"Truncated frame");
                    // Invalid beats (including last=1) must not affect the sum.
                    if (length < 1000 && i%7 == 0) begin
                        term_valid = 0; term_last = 1; a = 8'hff; b = 8'hff;
                        @(posedge clk); #1;
                        if (result_valid !== 0 || result !== 0 || term_ready !== 1)
                            $fatal(1,"Invalid input affected frame");
                        @(negedge clk);
                    end
                    a = av; b = bv; term_valid = 1; term_last = (i == length-1);
                    #1; if (term_ready !== 1 || start_ready !== 0) $fatal(1,"Term handshake failed");
                    @(posedge clk); produced_at = $time; #1;
                    if (i != length-1 && (result_valid !== 0 || result !== 0))
                        $fatal(1,"Premature result");
                    if (i == length-1 && (result_valid !== 1 || result !== expected))
                        $fatal(1,"stream result mismatch frame=%0d actual=%h expected=%h",frame,result,expected);
                    if (i != length-1) @(negedge clk);
                end
                for (j=0;j<stalls;j=j+1) begin
                    @(negedge clk); term_valid = 0; a = 0; b = 0; term_last = 0; mode4 = !mode4;
                    @(posedge clk); #1;
                    if (result_valid !== 1 || result !== expected || term_ready !== 0 || start_ready !== 0)
                        $fatal(1,"Stalled output changed");
                end
                @(negedge clk); term_valid = 0; result_ready = 1;
                @(posedge clk); consumed_at = $time;
                if (result_valid !== 1 || result !== expected) $fatal(1,"Result disappeared before consumption");
                $fdisplay(out_fd,"%0d,%0d,%0d,%08h,%0d,%0d",frame,m,length,result,
                    (produced_at-accepted_at)/10,(consumed_at-produced_at)/10);
                #1; if (result_valid !== 0 || result !== 0 || start_ready !== 1 || term_ready !== 0)
                    $fatal(1,"Result not retired");
                frame = frame+1;
            end else if (!$feof(fd)) $fatal(1,"Malformed frame header");
        end
        $fclose(fd); $fclose(out_fd);
        if (frame < 100) $fatal(1,"Insufficient frame coverage");
        $display("PASS stream impl=%0d frames=%0d reset_cancellations=2",PRODUCT_IMPL,frame);
        $finish;
    end
    initial begin
        #100000000;
        $fatal(1,"Stream test timeout");
    end
endmodule
