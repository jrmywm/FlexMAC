`timescale 1ns/1ps
module tb_agreement;
    localparam N = 1437;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst = 1, start_valid = 0, score_valid = 0, result_ready = 0;
    reg [3:0] winner = 0;
    reg signed [31:0] winner_score = 0, score = 0;
    wire start_ready, score_ready, result_valid, result_certified;
    flexmac_agreement dut(clk, rst, start_valid, start_ready, winner, winner_score,
        score_valid, score_ready, score, result_valid, result_ready, result_certified);
    reg [31:0] scores [0:N*10-1], thresholds [0:99];
    reg [7:0] winners [0:N-1], reference [0:N-1], expected [0:N-1];
    integer i, c, j, accepted = 0, frames = 0;
    task reset_engine;
        begin
            @(negedge clk); rst = 1; start_valid = 0; score_valid = 0; result_ready = 0;
            #1;
            if (start_ready || score_ready || result_valid || result_certified) $fatal(1, "reset masking");
            repeat (2) @(negedge clk);
            rst = 0;
            #1;
            if (!start_ready || result_valid) $fatal(1, "reset cancellation");
        end
    endtask
    task command(input integer candidate, input signed [31:0] value);
        begin
            @(negedge clk);
            if (!start_ready) $fatal(1, "checker not ready");
            winner = candidate; winner_score = value; start_valid = 1;
            @(negedge clk); start_valid = 0;
            winner = 15; winner_score = 32'sh80000000;
        end
    endtask
    task frame(input integer sample, candidate, competitor, adjustment, input bit expected_result);
        integer k, hold;
        reg signed [31:0] candidate_score;
        begin
            candidate_score = sample >= 0 ? scores[sample*10+candidate] : 0;
            command(candidate, candidate_score);
            for (k = 0; k < 10; k = k + 1) begin
                if (k % 3 == 0) begin
                    score_valid = 0; score = 32'sh80000000;
                    @(negedge clk);
                end
                if (!score_ready || result_valid) $fatal(1, "unexpected checker handshake");
                score_valid = 1;
                if (sample >= 0) score = scores[sample*10+k];
                else if (k == candidate) score = adjustment == 2 ? 1 : 0;
                else if (k == competitor) score = -$signed(thresholds[candidate*10+competitor]) + adjustment;
                else score = -1000000;
                @(negedge clk);
            end
            score_valid = 0;
            if (!result_valid || result_certified !== expected_result)
                $fatal(1, "certificate mismatch sample=%0d candidate=%0d competitor=%0d adjustment=%0d", sample, candidate, competitor, adjustment);
            if (sample >= 0 && result_certified && candidate != reference[sample])
                $fatal(1, "unsafe certification");
            for (hold = 0; hold < 3; hold = hold + 1) begin
                @(negedge clk);
                if (!result_valid || result_certified !== expected_result || start_ready || score_ready)
                    $fatal(1, "certificate stall stability");
            end
            result_ready = 1;
            @(negedge clk); result_ready = 0;
            if (result_valid || result_certified || !start_ready) $fatal(1, "invalid certificate masking");
            frames = frames + 1;
        end
    endtask
    task extreme(input bit positive);
        reg signed [31:0] candidate_score;
        integer k;
        begin
            candidate_score = positive ? 32'sh7fffffff : 32'sh80000000;
            command(0, candidate_score);
            score_valid = 1;
            for (k = 0; k < 10; k = k + 1) begin
                score = k == 0 ? candidate_score : ~candidate_score;
                @(negedge clk);
            end
            score_valid = 0;
            if (!result_valid || result_certified !== positive) $fatal(1, "33-bit score difference failed");
            result_ready = 1;
            @(negedge clk); result_ready = 0;
            frames = frames + 1;
        end
    endtask
    initial begin
        $readmemh("model/agreement/scores_int4.hex", scores);
        $readmemh("model/agreement/thresholds.hex", thresholds);
        $readmemh("model/agreement/winner_int4.hex", winners);
        $readmemh("model/agreement/reference_int8.hex", reference);
        $readmemh("model/agreement/expected_pairwise.hex", expected);
        reset_engine;
        command(0, 0);
        score_valid = 1; score = 0;
        repeat (4) @(negedge clk);
        reset_engine;
        command(0, 0);
        score_valid = 1; score = 0;
        repeat (10) @(negedge clk);
        score_valid = 0;
        if (!result_valid) $fatal(1, "missing pending certificate");
        reset_engine;
        for (i = 0; i < N; i = i + 1) begin
            frame(i, winners[i], 0, 0, expected[i][0]);
            accepted = accepted + expected[i];
        end
        for (c = 0; c < 10; c = c + 1)
            for (j = 0; j < 10; j = j + 1) if (c != j) begin
                frame(-1, c, j, 0, 1); // Exact minimum accepting integer margin.
                frame(-1, c, j, 1, 0); // One less than the required margin.
            end
        frame(-1, 15, -1, 0, 0); // Invalid class must never certify.
        frame(-1, 0, -1, 2, 0); // Candidate score must match its streamed score.
        extreme(1);
        extreme(0);
        $display("PASS agreement: %0d training/calibration fixtures, %0d accepted, zero unsafe accepts, 180 threshold boundaries, invalid/mismatched candidates, 33-bit score differences, stalls and two reset cancellations; %0d frames", N, accepted, frames);
        $finish;
    end
    initial begin #1000000; $fatal(1, "agreement watchdog"); end
endmodule
