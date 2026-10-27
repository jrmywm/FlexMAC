`timescale 1ns/1ps
module tb_adaptive;
    parameter PRODUCT_IMPL=0, FORCE_INT8=0, INT8_LANES=1;
    localparam ALL=1437, FIRST=1078, N=359;
    reg clk=0;
    always #5 clk=!clk;
    reg rst=1, start_valid=0, pixel_valid=0, result_ready=0;
    reg [4:0] pixel=0;
    wire start_ready,pixel_ready,result_valid,result_fallback,result_error;
    wire [3:0] result_class;
`ifdef GATE_LEVEL
    flexmac_mapped dut(
`else
    flexmac_adaptive #(.PRODUCT_IMPL(PRODUCT_IMPL),.FORCE_INT8(FORCE_INT8),.INT8_LANES(INT8_LANES)) dut(
`endif
        clk,rst,start_valid,start_ready,pixel_valid,pixel_ready,pixel,
        result_valid,result_ready,result_class,result_fallback,result_error);
    reg [7:0] raw [0:ALL*64-1], predictions8 [0:ALL-1], expected_accept [0:ALL-1];
    reg [31:0] scores8 [0:ALL*10-1],scores4 [0:ALL*10-1];
    integer cycle=0, sample=FIRST, checked4=0,checked8=0,accepted=0,fallbacks=0,i,k,f;
    reg check_scores=0;
    reg signed [31:0] expected_score;
    always @(posedge clk) begin
        cycle<=cycle+1;
`ifndef GATE_LEVEL
        if (check_scores && dut.score_commit) begin
            expected_score=dut.mode4 ? scores4[sample*10+dut.class_index] : scores8[sample*10+dut.class_index];
            if (dut.completed_score !== expected_score) $fatal(1,"adaptive score mismatch sample=%0d class=%0d mode4=%0d",sample,dut.class_index,dut.mode4);
            if (dut.mode4) begin
                checked4=checked4+1;
                if (dut.class_index !== checked4-1) $fatal(1,"INT4 class progression");
                if (dut.lower_complete > $signed(scores8[sample*10+dut.class_index]) ||
                    dut.upper_complete < $signed(scores8[sample*10+dut.class_index])) $fatal(1,"unsound RTL interval");
            end else begin
                checked8=checked8+1;
                if (dut.class_index !== checked8-1) $fatal(1,"INT8 class progression");
            end
        end
`endif
    end
    task reset_engine;
        begin
            @(negedge clk); rst=1; start_valid=0; pixel_valid=0; result_ready=0; check_scores=0;
            #1;
            if (start_ready || pixel_ready || result_valid || result_class || result_fallback || result_error) $fatal(1,"adaptive reset mask");
            repeat(2) @(negedge clk);
            rst=0;
            #1;
            if (!start_ready || result_valid) $fatal(1,"adaptive reset cancellation");
        end
    endtask
    task command;
        begin
            @(negedge clk);
            if (!start_ready) $fatal(1,"adaptive not ready");
            start_valid=1;
            @(negedge clk); start_valid=0;
        end
    endtask
    task infer(input integer image, gaps, bad_index);
        integer t,begin_cycle,end_cycle,expected_cycles;
        reg fallback_expected;
        reg [3:0] held_class;
        begin
            sample=image; checked4=0; checked8=0;
            command;
            begin_cycle=cycle;
            check_scores=bad_index < 0;
            for(t=0;t<64;t=t+1) begin
                if(gaps && t%7==0) begin pixel_valid=0;pixel=31;@(negedge clk);end
                if(!pixel_ready) $fatal(1,"adaptive input handshake");
                pixel_valid=1;
                pixel=t==bad_index ? 5'd31 : raw[image*64+t][4:0];
                @(negedge clk);
            end
            pixel_valid=0; pixel=31; start_valid=1;
            while(!result_valid) begin
                if(start_ready || pixel_ready || result_class || result_fallback || result_error) $fatal(1,"adaptive evaluation interface");
                @(negedge clk);
            end
            start_valid=0; end_cycle=cycle;
            fallback_expected=!FORCE_INT8 && !expected_accept[image][0];
            expected_cycles=bad_index>=0 ? 64 : FORCE_INT8 ? (INT8_LANES == 2 ? 384 : 704) : fallback_expected ? 1034 : 394;
            if(gaps) expected_cycles=expected_cycles+10;
            if(end_cycle-begin_cycle!=expected_cycles) $fatal(1,"adaptive cycle mismatch got=%0d expected=%0d",end_cycle-begin_cycle,expected_cycles);
            if(bad_index>=0) begin
                if(!result_error || result_class || result_fallback) $fatal(1,"invalid raw input was accepted");
            end else begin
                if(result_error || result_class!==predictions8[image][3:0] || result_fallback!==fallback_expected)
                    $fatal(1,"adaptive decision mismatch sample=%0d",image);
`ifndef GATE_LEVEL
                if(checked4!=(FORCE_INT8 ? 0 : 10) || checked8!=((FORCE_INT8 || fallback_expected) ? 10 : 0)) $fatal(1,"adaptive missing scores");
`endif
                if(fallback_expected) fallbacks=fallbacks+1;else accepted=accepted+1;
                $fdisplay(f,"%0d,%0d,%0d,%0d,%0d,%0d",image,FORCE_INT8,PRODUCT_IMPL,result_class,result_fallback,end_cycle-begin_cycle);
            end
            held_class=result_class;
            repeat(3) begin
                @(negedge clk);
                if(!result_valid || result_class!==held_class || result_error!==(bad_index>=0) ||
                    result_fallback!==((bad_index>=0) ? 1'b0 : fallback_expected) || start_ready || pixel_ready) $fatal(1,"adaptive stalled result");
            end
            result_ready=1;
            @(negedge clk); result_ready=0; check_scores=0;
            if(!start_ready || result_valid || result_class || result_error || result_fallback) $fatal(1,"adaptive result consume");
        end
    endtask
    reg [2047:0] report_path;
    initial begin
        $readmemh("model/agreement/raw_pixels.hex",raw);
        $readmemh("model/agreement/scores_int8.hex",scores8);
        $readmemh("model/agreement/scores_int4.hex",scores4);
        $readmemh("model/agreement/reference_int8.hex",predictions8);
        $readmemh("model/agreement/expected_conditioned.hex",expected_accept);
        if($value$plusargs("report=%s",report_path)) f=$fopen(report_path,"w");
        else if(FORCE_INT8 && INT8_LANES == 2) f=$fopen("build/int8_two_lane.csv","w");
        else if(FORCE_INT8) f=$fopen("build/adaptive_always_int8.csv","w");
        else if(PRODUCT_IMPL==0) f=$fopen("build/adaptive_shared.csv","w");
        else f=$fopen("build/adaptive_mux.csv","w");
        if(!f) $fatal(1,"adaptive report open");
        $fdisplay(f,"sample,force_int8,product_impl,prediction,fallback,command_to_valid_cycles");
        reset_engine;
        command; pixel_valid=1;pixel=8;repeat(7) @(negedge clk);reset_engine;
        command; pixel_valid=1;pixel=8;repeat(64) @(negedge clk);pixel_valid=0;
        repeat(19) @(negedge clk);reset_engine;
        if(!FORCE_INT8) begin
            // Zero normalized input makes intervals exact; cancel during CHECK.
            command;pixel_valid=1;pixel=8;repeat(64) @(negedge clk);pixel_valid=0;
`ifdef GATE_LEVEL
            repeat(320) @(negedge clk);
`else
            while(dut.state!=3) @(negedge clk);
`endif
            reset_engine;
            // Find a known fallback using calibration metadata, then cancel INT8.
            i=FIRST;while(expected_accept[i]) i=i+1;
            command;pixel_valid=1;
            for(k=0;k<64;k=k+1) begin pixel=raw[i*64+k][4:0];@(negedge clk);end
            pixel_valid=0;
`ifdef GATE_LEVEL
            repeat(330) @(negedge clk);
`else
            while(dut.state!=4) @(negedge clk);
`endif
            repeat(13) @(negedge clk);reset_engine;
        end
        command;pixel_valid=1;pixel=8;repeat(64) @(negedge clk);pixel_valid=0;
        while(!result_valid) @(negedge clk);reset_engine;
        infer(FIRST,0,0);infer(FIRST,0,63);
        for(i=FIRST;i<FIRST+N;i=i+1) infer(i,i%11==0,-1);
        $fclose(f);
`ifdef GATE_LEVEL
        $display("PASS gate-level black-box replay impl=%0d force_int8=%0d int8_lanes=%0d: %0d calibration images, no_fallback=%0d fallback=%0d; decisions, flags, cycles, invalid pixels, reset and stalls",PRODUCT_IMPL,FORCE_INT8,INT8_LANES,N,accepted,fallbacks);
`else
        $display("PASS raw classifier impl=%0d force_int8=%0d int8_lanes=%0d: %0d calibration images, no_fallback=%0d fallback=%0d; exact INT8 decisions, class scores, applicable interval containment, cycle counts, invalid pixels, reset and stalls",PRODUCT_IMPL,FORCE_INT8,INT8_LANES,N,accepted,fallbacks);
`endif
        $finish;
    end
    initial begin #10000000;$fatal(1,"adaptive watchdog");end
endmodule
