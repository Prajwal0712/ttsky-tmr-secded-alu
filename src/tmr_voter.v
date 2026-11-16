/*
 * Copyright (c) 2024 Tiny Tapeout
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tmr_voter (
    input  wire [7:0] alu0_result,
    input  wire       alu0_carry,
    input  wire       alu0_zero,

    input  wire [7:0] alu1_result,
    input  wire       alu1_carry,
    input  wire       alu1_zero,

    input  wire [7:0] alu2_result,
    input  wire       alu2_carry,
    input  wire       alu2_zero,

    output wire [7:0] voted_result,
    output wire       voted_carry,
    output wire       voted_zero,
    output wire       tmr_disagreement
);

    // Bitwise majority voting across 3 lanes
    assign voted_result = (alu0_result & alu1_result) |
                          (alu1_result & alu2_result) |
                          (alu0_result & alu2_result);

    assign voted_carry  = (alu0_carry & alu1_carry) |
                          (alu1_carry & alu2_carry) |
                          (alu0_carry & alu2_carry);

    assign voted_zero   = (alu0_zero & alu1_zero) |
                          (alu1_zero & alu2_zero) |
                          (alu0_zero & alu2_zero);

    // Check for disagreement on any bit in any lane
    wire res_diff   = (alu0_result != voted_result) |
                      (alu1_result != voted_result) |
                      (alu2_result != voted_result);

    wire carry_diff = (alu0_carry != voted_carry) |
                      (alu1_carry != voted_carry) |
                      (alu2_carry != voted_carry);

    wire zero_diff  = (alu0_zero != voted_zero) |
                      (alu1_zero != voted_zero) |
                      (alu2_zero != voted_zero);

    assign tmr_disagreement = res_diff | carry_diff | zero_diff;

endmodule
