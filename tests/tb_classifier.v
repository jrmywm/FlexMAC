`timescale 1ns/1ps
module tb_classifier;
    parameter PRODUCT_IMPL = 0;
    parameter FIXED_MODE = -1;
    localparam N = 360;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst = 1, start_valid = 0, mode4 = 0, feature_valid = 0, result_ready = 0;
    reg [7:0] feature_data = 0;
    wire start_ready, feature_ready, result_valid;
    wire [3:0] result_class;
    wire signed [31:0] result_score;
    flexmac_classifier #(.PRODUCT_IMPL(PRODUCT_IMPL), .FIXED_MODE(FIXED_MODE)) dut(
        clk, rst, start_valid, start_ready, mode4, feature_valid,
        feature_ready, feature_data, result_valid, result_ready, result_class, result_score);
    reg [7:0] features8 [0:N*64-1], features4 [0:N*32-1];
    reg [31:0] scores8 [0:N*10-1], scores4 [0:N*10-1];
    reg [7:0] predictions8 [0:N-1], predictions4 [0:N-1], labels [0:N-1], floating [0:N-1];
    integer cycle = 0, image = 0, active_mode = 0, score_count = 0;
    integer correct8 = 0, correct4 = 0, correct_float = 0, i, m, file_out;
    reg check_scores = 0;
    reg signed [31:0] expected_score;
    always @(posedge clk) begin
        cycle <= cycle + 1;
        if (check_scores && dut.score_commit) begin
            expected_score = active_mode ? scores4[image*10 + score_count] : scores8[image*10 + score_count];
            if (dut.class_index !== score_count || dut.completed_score !== expected_score)
                $fatal(1, "class score mismatch impl=%0d image=%0d mode=%0d class=%0d got=%0d expected=%0d",
                    PRODUCT_IMPL, image, active_mode, score_count, dut.completed_score, expected_score);
            score_count = score_count + 1;
        end
    end
    task reset_engine;
        begin
            @(negedge clk); rst = 1; start_valid = 0; feature_valid = 0; result_ready = 0;
            #1;
            if (start_ready || feature_ready || result_valid || result_class || result_score)
                $fatal(1, "reset did not mask interface");
            repeat (2) @(negedge clk);
            rst = 0;
            #1;
            if (!start_ready || result_valid) $fatal(1, "reset did not cancel transaction");
        end
    endtask
    task begin_command(input integer precision);
        begin
            @(negedge clk);
            if (!start_ready) $fatal(1, "not ready for command");
            mode4 = precision; start_valid = 1;
            @(posedge clk); #1;
            @(negedge clk); start_valid = 0; mode4 = !precision;
        end
    endtask
    task infer(input integer sample, input integer precision, input integer gaps);
        integer k, count, start_cycle, load_done_cycle, finish_cycle, hold;
        reg [3:0] held_class;
        reg signed [31:0] held_score;
        begin
            image = sample; active_mode = precision; score_count = 0; check_scores = 1;
            count = precision ? 32 : 64;
            begin_command(precision);
            start_cycle = cycle;
            for (k = 0; k < count; k = k + 1) begin
                if (gaps && k % 7 == 0) begin
                    feature_valid = 0; feature_data = 8'hff;
                    @(negedge clk);
                end
                if (!feature_ready) $fatal(1, "feature not ready");
                feature_valid = 1;
                feature_data = precision ? features4[sample*32+k] : features8[sample*64+k];
                @(negedge clk);
            end
            feature_valid = 0;
            load_done_cycle = cycle;
            // Host noise after loading must have no effect on evaluation.
            feature_data = 8'had; start_valid = 1;
            while (!result_valid) begin
                if (feature_ready || start_ready) $fatal(1, "accepted work during evaluation");
                if (result_class !== 0 || result_score !== 0) $fatal(1, "invalid payload not masked");
                @(negedge clk);
            end
            start_valid = 0;
            finish_cycle = cycle;
            if (score_count != 10) $fatal(1, "missing class scores");
            if (finish_cycle-load_done_cycle != count*10) $fatal(1, "wrong evaluation cycle count");
            if (!gaps && finish_cycle-start_cycle != count*11) $fatal(1, "wrong total cycle count");
            if (result_class !== (precision ? predictions4[sample][3:0] : predictions8[sample][3:0]))
                $fatal(1, "prediction mismatch");
            expected_score = precision ? scores4[sample*10+result_class] : scores8[sample*10+result_class];
            if (result_score !== expected_score) $fatal(1, "winning score mismatch");
            held_class = result_class; held_score = result_score;
            for (hold = 0; hold < 3; hold = hold + 1) begin
                @(negedge clk);
                if (!result_valid || result_class !== held_class || result_score !== held_score || start_ready || feature_ready)
                    $fatal(1, "stalled result changed");
            end
            if (held_class == labels[sample]) begin
                if (precision) correct4 = correct4 + 1; else correct8 = correct8 + 1;
            end
            $fdisplay(file_out, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d", PRODUCT_IMPL, precision ? 4 : 8,
                sample, labels[sample], held_class, held_score, finish_cycle-start_cycle, finish_cycle-load_done_cycle);
            result_ready = 1;
            @(negedge clk); result_ready = 0; check_scores = 0;
            if (!start_ready || result_valid) $fatal(1, "result not consumed");
        end
    endtask
    initial begin
        $readmemh("model/digits/features_int8.hex", features8);
        $readmemh("model/digits/features_int4.hex", features4);
        $readmemh("model/digits/scores_int8.hex", scores8);
        $readmemh("model/digits/scores_int4.hex", scores4);
        $readmemh("model/digits/predictions_int8.hex", predictions8);
        $readmemh("model/digits/predictions_int4.hex", predictions4);
        $readmemh("model/digits/labels.hex", labels);
        $readmemh("model/digits/float_predictions.hex", floating);
        // Keep strings separate: packed conditional strings of unequal length
        // are not portable across Icarus versions.
        if (FIXED_MODE == 0) file_out = $fopen("build/classifier_fixed_int8.csv", "w");
        else if (FIXED_MODE == 1) file_out = $fopen("build/classifier_fixed_int4.csv", "w");
        else if (PRODUCT_IMPL == 0) file_out = $fopen("build/classifier_shared.csv", "w");
        else file_out = $fopen("build/classifier_mux.csv", "w");
        if (!file_out) $fatal(1, "cannot open report");
        $fdisplay(file_out, "implementation,bits,sample,label,prediction,score,command_to_valid_cycles,evaluation_cycles");
        reset_engine;
        // Abort a partially loaded frame, a running evaluation and a pending output.
        for (m = 0; m < 2; m = m + 1) if (FIXED_MODE < 0 || FIXED_MODE == m) begin
            begin_command(m);
            feature_valid = 1; feature_data = 8'h88;
            repeat (5) @(negedge clk);
            reset_engine;
            begin_command(m);
            feature_valid = 1; feature_data = 8'h77;
            repeat (m ? 32 : 64) @(negedge clk);
            feature_valid = 0;
            repeat (17) @(negedge clk);
            reset_engine;
            begin_command(m);
            feature_valid = 1; feature_data = 8'h00;
            repeat (m ? 32 : 64) @(negedge clk);
            feature_valid = 0;
            while (!result_valid) @(negedge clk);
            reset_engine;
        end
        for (i = 0; i < N; i = i + 1) begin
            if (floating[i] == labels[i]) correct_float = correct_float + 1;
            if (FIXED_MODE != 1) infer(i, 0, i % 11 == 0);
            if (FIXED_MODE != 0) infer(i, 1, i % 11 == 0);
        end
        $fclose(file_out);
        $display("PASS classifier impl=%0d fixed_mode=%0d: %0d images/mode, %0d class scores, float=%0d INT8=%0d INT4=%0d correct; %0d reset cancellations",
            PRODUCT_IMPL, FIXED_MODE, N, N*(FIXED_MODE < 0 ? 20 : 10), correct_float, correct8, correct4,
            FIXED_MODE < 0 ? 6 : 3);
        $finish;
    end
    initial begin
        #20000000; $fatal(1, "classifier watchdog");
    end
endmodule
