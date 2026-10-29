`timescale 1ns/1ps
module tb_synthetic;
 parameter FEATURES=64,CLASSES=10,SCHEDULE=0;
 reg clk=0,rst=1,start_valid=0,result_ready=0,feature_valid=0;
 reg signed [7:0] feature=0;
 reg check_scores=1;
 always #5 clk=~clk;
 wire start_ready,result_valid,feature_ready;
 wire [$clog2(CLASSES)-1:0] result_class;
 flexmac_synthetic #(.FEATURES(FEATURES),.CLASSES(CLASSES),.SCHEDULE(SCHEDULE)) dut
 (clk,rst,start_valid,result_ready,feature_valid,feature,feature_ready,start_ready,result_valid,result_class);
 integer expected[0:CLASSES-1];integer frame[0:FEATURES-1];
 integer i,j,t,w,winning,cycle=0,seen,begin_cycle,elapsed,gap_count,report;
 reg [2047:0] report_path;
 always @(posedge clk) begin
   cycle<=cycle+1;
   if(!rst && check_scores && dut.score_valid) begin
     if(dut.cls!==seen || dut.score!==expected[seen])
       $fatal(1,"score mismatch class=%0d got=%0d expected=%0d",seen,dut.score,expected[seen]);
     seen=seen+1;
   end
 end
 task reset_engine;
   begin
     rst=1;start_valid=0;feature_valid=0;result_ready=0;seen=0;
     #1;if(start_ready || feature_ready || result_valid || result_class) $fatal(1,"reset mask");
     repeat(2) @(negedge clk);rst=0;#1;
     if(!start_ready || result_valid) $fatal(1,"reset cancellation");
   end
 endtask
 task command;
   begin
     if(!start_ready) $fatal(1,"not ready");
     start_valid=1;@(negedge clk);start_valid=0;
   end
 endtask
 initial begin
   if(!$value$plusargs("report=%s",report_path)) report_path="build/synthetic/default.csv";
   report=$fopen(report_path,"w");if(!report) $fatal(1,"report open");
   $fdisplay(report,"frame,features,classes,schedule,cycles,input_gaps,prediction");
   reset_engine;
   command;feature_valid=1;feature=-128;repeat(3) @(negedge clk);reset_engine;
   for(t=0;t<24;t=t+1) begin
     for(i=0;i<FEATURES;i=i+1) begin
       case(t)
         0: frame[i]=0;
         1: frame[i]=-128;
         2: frame[i]=127;
         3: frame[i]=i%2 ? 127 : -128;
         default: frame[i]=((i*37+t*53+13)%256)-128;
       endcase
     end
     // Independent signed-integer behavioral scoreboard.
     for(j=0;j<CLASSES;j=j+1) begin
       expected[j]=j*271-1000;
       for(i=0;i<FEATURES;i=i+1) begin
         w=((i*17+j*29+7)%256)-128;
         expected[j]=expected[j]+frame[i]*w;
       end
     end
     winning=0;for(j=1;j<CLASSES;j=j+1) if(expected[j]>expected[winning]) winning=j;
     seen=0;command;begin_cycle=cycle;gap_count=0;
     for(i=0;i<FEATURES;i=i+1) begin
       if(t%2 && i%7==0) begin feature_valid=0;feature=127;gap_count=gap_count+1;@(negedge clk);end
       if(!feature_ready || start_ready || result_valid) $fatal(1,"load handshake");
       feature_valid=1;feature=frame[i];@(negedge clk);
     end
     feature_valid=0;start_valid=1;
     while(!result_valid) begin
       if(start_ready || feature_ready || result_class) $fatal(1,"busy interface");
       @(negedge clk);
     end
     start_valid=0;elapsed=cycle-begin_cycle;
     if(elapsed!=FEATURES+FEATURES/2*CLASSES+(SCHEDULE==1 ? CLASSES : SCHEDULE==2 ? 1 : 0)+gap_count)
       $fatal(1,"cycle mismatch %0d",elapsed);
     if(seen!=CLASSES || result_class!==winning) $fatal(1,"wrong winner/missing score");
     $fdisplay(report,"%0d,%0d,%0d,%0d,%0d,%0d,%0d",t,FEATURES,CLASSES,SCHEDULE,elapsed,gap_count,winning);
     repeat(3) begin @(negedge clk);if(!result_valid || result_class!==winning || start_ready || feature_ready) $fatal(1,"stalled result");end
     result_ready=1;@(negedge clk);result_ready=0;
     if(!start_ready || result_valid || result_class) $fatal(1,"result consume");
   end
   check_scores=0;
   // Register-level tie check supplements real-interface operand tests.
   @(negedge clk);dut.best=-1;dut.best_cls=0;
   if(SCHEDULE==0) begin
     dut.state=1;dut.cls=CLASSES-1;dut.beat=FEATURES/2-1;force dut.score=-1;
   end else begin
     dut.state=2;dut.pending_valid=1;dut.pending_cls=CLASSES-1;dut.pending=-1;
   end
   @(negedge clk);if(SCHEDULE==0) release dut.score;
   if(!result_valid || result_class!==0) $fatal(1,"signed tie/final drain");
   reset_engine;
   dut.best=-1;dut.best_cls=0;
   if(SCHEDULE==0) begin
     dut.state=1;dut.cls=CLASSES-1;dut.beat=FEATURES/2-1;force dut.score=0;
   end else begin
     dut.state=2;dut.pending_valid=1;dut.pending_cls=CLASSES-1;dut.pending=0;
   end
   @(negedge clk);if(SCHEDULE==0) release dut.score;
   if(!result_valid || result_class!==(CLASSES-1)) $fatal(1,"signed final winner");
   reset_engine;
   command;feature_valid=1;feature=0;repeat(FEATURES) @(negedge clk);feature_valid=0;
   repeat(FEATURES/2+1) @(negedge clk);reset_engine;
   repeat(FEATURES*CLASSES) begin @(negedge clk);if(result_valid) $fatal(1,"stale result after reset");end
   $fclose(report);
   $display("PASS synthetic features=%0d classes=%0d schedule=%0d: 24 runtime-input frames, all scores, cycles, gaps, stalls, extremes, tie and reset",FEATURES,CLASSES,SCHEDULE);
   $finish;
 end
 initial begin #10000000;$fatal(1,"watchdog");end
endmodule
