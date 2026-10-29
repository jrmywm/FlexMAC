`timescale 1ns/1ps
module tb_compact_refine;
    parameter FIRST=1078, COUNT=359;
    reg clk=0;
    always #5 clk=!clk;
    reg rst=1,start_valid=0,pixel_valid=0,result_ready=0;
    reg [4:0] pixel=0;
    wire start_ready,pixel_ready,result_valid,result_fallback,result_error;
    wire [3:0] result_class;
`ifdef GATE_LEVEL
    flexmac_mapped dut(
`else
`ifdef BASELINE4
    flexmac_int8x4_scorepipe dut(
`else
    flexmac_compact_refine dut(
`endif
`endif
        clk,rst,start_valid,start_ready,pixel_valid,pixel_ready,pixel,
        result_valid,result_ready,result_class,result_fallback,result_error);
    reg [7:0] raw[0:1437*64-1],predictions[0:1436];
    reg [31:0] scores4[0:14369],scores8[0:14369];
    reg [9:0] masks[0:1436];
    integer cycle=0,sample=0,low_checked=0,exact_checked=0,f,i,k,run_index;
    integer replay_count=COUNT,use_selection=0;
    reg [31:0] indices[0:1436];
    reg checking=0;
    reg [9:0] seen;
    always @(posedge clk) begin
        cycle<=cycle+1;
`ifndef GATE_LEVEL
`ifdef BASELINE4
        if(checking && dut.score_commit) begin
            if(dut.class_index!=exact_checked || dut.completed_score!==scores8[sample*10+dut.class_index])
                $fatal(1,"four-lane baseline score mismatch");
            exact_checked=exact_checked+1;
        end
`else
        if(checking && dut.score_commit) begin
            if(dut.class_index>9) $fatal(1,"invalid score class");
            if(dut.mode4) begin
                if(dut.class_index!=low_checked || dut.completed_score!==scores4[sample*10+dut.class_index])
                    $fatal(1,"compact low score mismatch sample=%0d class=%0d",sample,dut.class_index);
                low_checked=low_checked+1;
            end else begin
                if(!masks[sample][dut.class_index] || seen[dut.class_index] ||
                   dut.completed_score!==scores8[sample*10+dut.class_index])
                    $fatal(1,"compact exact score or selection mismatch sample=%0d class=%0d",sample,dut.class_index);
                seen[dut.class_index]=1;
                exact_checked=exact_checked+1;
            end
        end
`endif
`endif
    end
    task reset_engine;
        begin
            @(negedge clk); rst=1; start_valid=0; pixel_valid=0; result_ready=0; checking=0;
            #1;
            if(start_ready || pixel_ready || result_valid || result_class || result_error || result_fallback)
                $fatal(1,"compact reset mask");
            repeat(2) @(negedge clk); rst=0; #1;
            if(!start_ready || result_valid) $fatal(1,"compact reset cancellation");
        end
    endtask
    task command;
        begin
            @(negedge clk); if(!start_ready) $fatal(1,"compact command not ready");
            start_valid=1; @(negedge clk); start_valid=0;
        end
    endtask
    task infer(input integer image,gaps,bad);
        integer begin_cycle,t,nexact,expected,gap_count;
        reg [3:0] held;
        begin
            sample=image; low_checked=0; exact_checked=0; seen=0;
            nexact=0; for(t=0;t<10;t=t+1) nexact=nexact+masks[image][t];
`ifdef BASELINE4
            nexact=0;
`endif
            command; begin_cycle=cycle; checking=bad<0; gap_count=0;
            for(t=0;t<64;t=t+1) begin
                if(gaps && t%7==0) begin
                    pixel_valid=0; pixel=31; @(negedge clk); gap_count=gap_count+1;
                end
                if(!pixel_ready) $fatal(1,"compact input not ready");
                pixel_valid=1;pixel=t==bad ? 31 : raw[image*64+t][4:0]; @(negedge clk);
            end
            pixel_valid=0;pixel=31;start_valid=1;
            while(!result_valid) begin
                if(start_ready || pixel_ready || result_class || result_error || result_fallback)
                    $fatal(1,"compact evaluation interface");
                @(negedge clk);
            end
            start_valid=0;checking=0;
            expected=bad>=0 ? 64 : 253+(nexact>0 ? 10+33*nexact : 0);
`ifdef BASELINE4
            expected=bad>=0 ? 64 : 234;
`endif
            if(cycle-begin_cycle!=expected+gap_count) $fatal(1,"compact cycles got=%0d expected=%0d",cycle-begin_cycle,expected+gap_count);
            if(bad>=0) begin
                if(!result_error || result_class || result_fallback) $fatal(1,"compact invalid input");
            end else begin
                if(result_error || result_class!==predictions[image][3:0] || result_fallback!==(nexact>0))
                    $fatal(1,"compact decision mismatch sample=%0d",image);
`ifndef GATE_LEVEL
`ifdef BASELINE4
                if(exact_checked!=10) $fatal(1,"four-lane baseline missing scores");
`else
                if(low_checked!=10 || exact_checked!=nexact || seen!==masks[image]) $fatal(1,"compact missing scores");
`endif
`endif
                $fdisplay(f,"%0d,%0d,%0d,%0d,%0d,%0d",image,result_class,result_fallback,nexact,cycle-begin_cycle,gap_count);
            end
            held=result_class;
            repeat(3) begin
                @(negedge clk);
                if(!result_valid || result_class!==held || result_error!==(bad>=0) ||
                   result_fallback!==((bad<0)&&(nexact>0)) || start_ready || pixel_ready)
                    $fatal(1,"compact stalled output");
            end
            result_ready=1; @(negedge clk); result_ready=0;
            if(!start_ready || result_valid || result_class || result_fallback || result_error)
                $fatal(1,"compact output consumption");
        end
    endtask
    reg [2047:0] report_path,indices_path;
    initial begin
        $readmemh("model/agreement/raw_pixels.hex",raw);
        $readmemh("model/agreement/scores_int4.hex",scores4);
        $readmemh("model/agreement/scores_int8.hex",scores8);
        $readmemh("model/agreement/reference_int8.hex",predictions);
        $readmemh("build/compact_refinement/active_masks.hex",masks);
        if($value$plusargs("indices=%s",indices_path)) begin
            use_selection=1;
            if(!$value$plusargs("count=%d",replay_count) || replay_count<1 || replay_count>1437)
                $fatal(1,"invalid replay selection");
            $readmemh(indices_path,indices,0,replay_count-1);
        end
        if(!$value$plusargs("report=%s",report_path)) report_path="build/compact_refinement/rtl.csv";
        f=$fopen(report_path,"w");if(!f) $fatal(1,"compact report open");
        $fdisplay(f,"sample,prediction,fallback,exact_classes,cycles,input_gaps");
        reset_engine;
        command;pixel_valid=1;pixel=8;repeat(7) @(negedge clk);reset_engine;
        // Cancel each phase by wall-clock position; these also run on mapped RTL.
        for(k=0;k<5;k=k+1) begin
            command;pixel_valid=1;
            for(i=0;i<64;i=i+1) begin pixel=raw[FIRST*64+i][4:0];@(negedge clk);end
            pixel_valid=0;
            repeat(k==0 ? 13 : k==1 ? 170 : k==2 ? 185 : k==3 ? 201 : 700) @(negedge clk);
            reset_engine;
        end
        infer(FIRST,0,0);infer(FIRST,0,63);
        for(run_index=0;run_index<replay_count;run_index=run_index+1) begin
            i=use_selection ? indices[run_index] : FIRST+run_index;
            if(i<0 || i>=1437) $fatal(1,"selection outside fixture domain");
            infer(i,i%11==0,-1);$fflush(f);
        end
        $fclose(f);
        $display("PASS compact refinement: %0d frames; decisions, flags, cycles, gaps, reset, stalls, invalid inputs; internal score/selection checks in RTL builds",replay_count);
        $finish;
    end
    initial begin #20000000;$fatal(1,"compact watchdog");end
endmodule
