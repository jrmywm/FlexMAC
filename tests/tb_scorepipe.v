`timescale 1ns/1ps
module tb_scorepipe;
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
    flexmac_int8x2_scorepipe dut(
`endif
        clk,rst,start_valid,start_ready,pixel_valid,pixel_ready,pixel,
        result_valid,result_ready,result_class,result_fallback,result_error);
    reg [7:0] raw [0:ALL*64-1], predictions8 [0:ALL-1];
    reg [31:0] scores8 [0:ALL*10-1];
    reg [31:0] selected_indices [0:N-1];
    integer cycle=0,sample=FIRST,checked8=0,compared8=0;
    integer i,k,f,run_index,replay_count=N,use_selection=0;
    reg check_scores=0,await_compare=0;
    reg signed [31:0] expected_score, captured_score;
    reg [3:0] captured_class;
    integer capture_cycle;
    always @(posedge clk) begin
        cycle<=cycle+1;
`ifndef GATE_LEVEL
        if(rst) await_compare=0;
        else if(check_scores) begin
            if(await_compare && !dut.compare_commit) $fatal(1,"missing immediate score comparison");
            if(dut.score_commit) begin
                if(await_compare || dut.compare_commit) $fatal(1,"overlapping score boundaries");
                expected_score=scores8[sample*10+dut.class_index];
                if(dut.completed_score!==expected_score)
                    $fatal(1,"scorepipe score mismatch sample=%0d class=%0d got=%0d expected=%0d",sample,dut.class_index,dut.completed_score,expected_score);
                if(dut.class_index!==checked8 || dut.index!==6'd31 || result_valid)
                    $fatal(1,"terminal MAC class/index or early result");
                if(checked8>0 && cycle-capture_cycle!=33) $fatal(1,"class boundary spacing");
                capture_cycle=cycle; captured_score=dut.completed_score; captured_class=dut.class_index;
                checked8=checked8+1; await_compare=1;
            end else if(dut.compare_commit) begin
                if(!await_compare || cycle-capture_cycle!=1 || result_valid)
                    $fatal(1,"COMPARE must follow terminal MAC by one cycle");
                if(dut.pending_score!==captured_score || dut.pending_class!==captured_class ||
                    dut.pending_class!==compared8 || dut.pending_last!==(captured_class==9) ||
                    dut.class_index!==captured_class)
                    $fatal(1,"pending score/class/last tag mismatch");
                compared8=compared8+1; await_compare=0;
            end
        end
`endif
    end
    task reset_engine(input integer compare_class);
        begin
            @(negedge clk);
`ifndef GATE_LEVEL
            if(compare_class>=0 && (dut.state!==3'd6 || dut.pending_class!==compare_class ||
                dut.pending_last!==(compare_class==9))) $fatal(1,"reset did not target COMPARE");
`endif
            rst=1; start_valid=0; pixel_valid=0; result_ready=0; check_scores=0;
            #1;
            if(start_ready || pixel_ready || result_valid || result_class || result_fallback || result_error)
                $fatal(1,"scorepipe reset mask");
            repeat(2) @(negedge clk);
            rst=0;
            #1;
            if(!start_ready || result_valid) $fatal(1,"scorepipe reset cancellation");
            if($test$plusargs("progress")) begin $display("GATE_PROGRESS reset_complete compare_class=%0d time=%0t",compare_class,$time);$fflush();end
        end
    endtask
    task command;
        begin
            @(negedge clk);
            if(!start_ready) $fatal(1,"scorepipe not ready");
            start_valid=1;
            @(negedge clk); start_valid=0;
        end
    endtask
    task load_zero;
        begin
            command; pixel_valid=1;pixel=8;
            repeat(64) @(negedge clk);
            pixel_valid=0;
        end
    endtask
    task infer(input integer image,gaps,bad_index);
        integer t,begin_cycle,end_cycle,expected_cycles;
        reg [3:0] held_class;
        begin
            sample=image; checked8=0; compared8=0; await_compare=0;
            command; begin_cycle=cycle; check_scores=bad_index<0;
            for(t=0;t<64;t=t+1) begin
                if(gaps && t%7==0) begin pixel_valid=0;pixel=31;@(negedge clk);end
                if(!pixel_ready) $fatal(1,"scorepipe input handshake");
                pixel_valid=1; pixel=t==bad_index ? 5'd31 : raw[image*64+t][4:0];
                @(negedge clk);
            end
            pixel_valid=0; pixel=31; start_valid=1;
            while(!result_valid) begin
                if(start_ready || pixel_ready || result_class || result_fallback || result_error)
                    $fatal(1,"scorepipe evaluation interface");
                @(negedge clk);
            end
            start_valid=0; end_cycle=cycle;
            expected_cycles=bad_index>=0 ? 64 : 394;
            if(gaps) expected_cycles=expected_cycles+10;
            if(end_cycle-begin_cycle!=expected_cycles)
                $fatal(1,"scorepipe cycle mismatch got=%0d expected=%0d",end_cycle-begin_cycle,expected_cycles);
            if(bad_index>=0) begin
                if(!result_error || result_class || result_fallback) $fatal(1,"invalid raw input was accepted");
            end else begin
                if(result_error || result_fallback || result_class!==predictions8[image][3:0])
                    $fatal(1,"scorepipe decision mismatch sample=%0d",image);
`ifndef GATE_LEVEL
                if(checked8!=10 || compared8!=10 || await_compare) $fatal(1,"scorepipe missing scores/comparisons");
`endif
                $fdisplay(f,"%0d,1,0,%0d,0,%0d",image,result_class,end_cycle-begin_cycle);
            end
            held_class=result_class;
            repeat(3) begin
                @(negedge clk);
                if(!result_valid || result_class!==held_class || result_error!==(bad_index>=0) ||
                    result_fallback || start_ready || pixel_ready) $fatal(1,"scorepipe stalled result");
            end
            result_ready=1;
            @(negedge clk); result_ready=0; check_scores=0;
            if(!start_ready || result_valid || result_class || result_error || result_fallback)
                $fatal(1,"scorepipe result consume");
        end
    endtask
`ifndef GATE_LEVEL
    // Directed register-level arithmetic/control checks supplement the frozen
    // model replay: the calibration scores do not reach wrap or signed limits.
    task directed_boundaries;
        begin
            @(negedge clk);
            dut.state=3'd4; dut.class_index=0; dut.index=31;
            dut.accumulator=32'sh7fffffff;
            force dut.beat_product=17'sd1;
            @(negedge clk);
            release dut.beat_product;
            if(dut.pending_score!==32'sh80000000 || dut.pending_class!==0 || dut.pending_last)
                $fatal(1,"signed32 terminal score wrap/tag");
            @(negedge clk);
            if(dut.best_score!==32'sh80000000 || dut.best_class!==0)
                $fatal(1,"first negative score must initialize winner");
            // Equal negative scores must retain the earlier class.
            dut.state=3'd6; dut.pending_class=1; dut.pending_last=0;
            dut.pending_score=32'sh80000000; dut.class_index=1;
            @(negedge clk);
            if(dut.best_class!==0) $fatal(1,"lower-index tie winner");
            // A positive final score must beat a negative score and be visible
            // on the same edge that publishes RESULT, without a stale winner.
            dut.state=3'd6; dut.pending_class=9; dut.pending_last=1;
            dut.pending_score=32'sh7fffffff; dut.class_index=9;
            @(negedge clk);
            if(!result_valid || result_class!==9 || dut.best_score!==32'sh7fffffff)
                $fatal(1,"signed final-class compare/result publication");
        end
    endtask
`endif
    reg [2047:0] report_path,indices_path;
    initial begin
        $readmemh("model/agreement/raw_pixels.hex",raw);
        $readmemh("model/agreement/scores_int8.hex",scores8);
        $readmemh("model/agreement/reference_int8.hex",predictions8);
        if($value$plusargs("indices=%s",indices_path)) begin
            use_selection=1;
            if(!$value$plusargs("count=%d",replay_count) || replay_count<1 || replay_count>N)
                $fatal(1,"invalid replay selection");
            $readmemh(indices_path,selected_indices,0,replay_count-1);
        end
        if($value$plusargs("report=%s",report_path)) f=$fopen(report_path,"w");
        else f=$fopen("build/scorepipe.csv","w");
        if(!f) $fatal(1,"scorepipe report open");
        $fdisplay(f,"sample,force_int8,product_impl,prediction,fallback,command_to_valid_cycles");$fflush(f);
        reset_engine(-1);
        command;pixel_valid=1;pixel=8;repeat(7) @(negedge clk);reset_engine(-1);
        load_zero;repeat(19) @(negedge clk);reset_engine(-1);
        // At 32 compute edges class 0 is staged; assert reset before its compare.
        load_zero;repeat(31) @(negedge clk);reset_engine(0);
        // Nine full 33-cycle classes plus 32 MAC beats stage the final class.
        load_zero;repeat(328) @(negedge clk);reset_engine(9);
        load_zero;while(!result_valid) @(negedge clk);reset_engine(-1);
`ifndef GATE_LEVEL
        directed_boundaries;reset_engine(-1);
`endif
        infer(FIRST,0,0);infer(FIRST,0,63);
        for(run_index=0;run_index<replay_count;run_index=run_index+1) begin
            i=use_selection ? selected_indices[run_index] : FIRST+run_index;
            if(i<FIRST || i>=FIRST+N) $fatal(1,"replay selection outside calibration split");
            if($test$plusargs("progress") && run_index%32==0) begin
                $display("GATE_PROGRESS frame=%0d sample=%0d time=%0t",run_index,i,$time);$fflush();
            end
            infer(i,i%11==0,-1);$fflush(f);
        end
        $fclose(f);
`ifdef GATE_LEVEL
        $display("PASS gate-level scorepipe black-box replay: %0d calibration images; predictions, flags, exact 394 cycles plus input gaps, invalid pixels, reset in both boundary COMPARE cycles, stalls",replay_count);
`else
        $display("PASS scorepipe: %0d calibration images; all INT8 class scores/predictions, score/class/last tags, exact 394 cycles plus input gaps, signed32 wrap, signed/tie/final comparison, invalid pixels, reset and stalls",replay_count);
`endif
        $finish;
    end
    initial begin #10000000;$fatal(1,"scorepipe watchdog");end
endmodule
