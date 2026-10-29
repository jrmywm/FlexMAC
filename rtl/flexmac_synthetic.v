// Runtime-feature synthetic two-lane study. SCHEDULE: 0 terminal, 1 separate, 2 overlap.
module flexmac_synthetic #(parameter FEATURES=64, CLASSES=10, SCHEDULE=0)(
 input wire clk,rst,start_valid, result_ready,
 input wire feature_valid, input wire signed [7:0] feature,
 output wire feature_ready,
 output wire start_ready,result_valid,
 output wire [$clog2(CLASSES)-1:0] result_class
);
 localparam CW=$clog2(CLASSES), BW=$clog2(FEATURES/2), FW=$clog2(FEATURES);
 localparam IDLE=0, MAC=1, CMP=2, RESULT=3, LOAD=4;
 reg [2:0] state;
 reg [FW-1:0] load_index;
 reg [BW-1:0] beat;
 reg [CW-1:0] cls,best_cls,pending_cls;
 reg signed [31:0] acc,best,pending;
 reg pending_valid;
 reg signed [7:0] features [0:FEATURES-1];
 reg signed [7:0] weights [0:FEATURES*CLASSES-1];
 reg signed [31:0] biases [0:CLASSES-1];
 integer i,j;
 initial begin
   for(j=0;j<CLASSES;j=j+1) begin
     biases[j]=j*271-1000;
     for(i=0;i<FEATURES;i=i+1) weights[j*FEATURES+i]=((i*17+j*29+7)%256)-128;
   end
 end
 wire signed [15:0] p0=features[beat*2]*weights[cls*FEATURES+beat*2];
 wire signed [15:0] p1=features[beat*2+1]*weights[cls*FEATURES+beat*2+1];
 wire signed [31:0] score=acc+{{16{p0[15]}},p0}+{{16{p1[15]}},p1};
 assign start_ready=!rst && state==IDLE;
 assign result_valid=!rst && state==RESULT;
 assign result_class=result_valid ? best_cls : 0;
 assign feature_ready=!rst && state==LOAD;
 wire score_valid=!rst && state==MAC && beat==FEATURES/2-1;
 always @(posedge clk) begin
   if(rst) begin state<=IDLE;load_index<=0;beat<=0;cls<=0;best_cls<=0;acc<=0;best<=0;pending<=0;pending_cls<=0;pending_valid<=0;end
   else case(state)
    IDLE: if(start_valid) begin state<=LOAD;load_index<=0;beat<=0;cls<=0;best_cls<=0;acc<=biases[0];pending_valid<=0;end
    LOAD: if(feature_valid) begin
      features[load_index]<=feature;
      if(load_index==FEATURES-1) begin load_index<=0;state<=MAC;end
      else load_index<=load_index+1'b1;
    end
    MAC: begin
      if(SCHEDULE==2 && pending_valid) begin
        if(pending_cls==0 || pending>best) begin best<=pending;best_cls<=pending_cls;end
        pending_valid<=0;
      end
      if(beat==FEATURES/2-1) begin
        beat<=0;
        if(SCHEDULE==0) begin
          if(cls==0 || score>best) begin best<=score;best_cls<=cls;end
          if(cls==CLASSES-1) state<=RESULT;
          else begin cls<=cls+1'b1;acc<=biases[cls+1'b1];end
        end else begin
          pending<=score;pending_cls<=cls;pending_valid<=1;
          if(SCHEDULE==1 || cls==CLASSES-1) state<=CMP;
          else begin cls<=cls+1'b1;acc<=biases[cls+1'b1];end
        end
      end else begin acc<=score;beat<=beat+1'b1;end
    end
    CMP: if(pending_valid) begin
      if(pending_cls==0 || pending>best) begin best<=pending;best_cls<=pending_cls;end
      pending_valid<=0;
      if(pending_cls==CLASSES-1) state<=RESULT;
      else begin cls<=cls+1'b1;acc<=biases[cls+1'b1];state<=MAC;end
    end
    RESULT: if(result_ready) state<=IDLE;
    default: state<=IDLE;
   endcase
 end
endmodule
