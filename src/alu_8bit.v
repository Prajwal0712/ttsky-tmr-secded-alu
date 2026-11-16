/*
 * Copyright (c) 2024 Tiny Tapeout
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module alu_8bit (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire [2:0] op,
    output reg  [7:0] result,
    output reg        carry_out,
    output wire       zero_flag
);

    always @(*) begin
        case (op)
            3'b000: begin // ADD
                {carry_out, result} = {1'b0, a} + {1'b0, b};
            end
            3'b001: begin // SUB
                {carry_out, result} = {1'b0, a} - {1'b0, b};
            end
            3'b010: begin // AND
                result    = a & b;
                carry_out = 1'b0;
            end
            3'b011: begin // OR
                result    = a | b;
                carry_out = 1'b0;
            end
            3'b100: begin // XOR
                result    = a ^ b;
                carry_out = 1'b0;
            end
            3'b101: begin // SHL
                result    = a << b[2:0];
                carry_out = 1'b0;
            end
            3'b110: begin // SHR
                result    = a >> b[2:0];
                carry_out = 1'b0;
            end
            3'b111: begin // PASS_B
                result    = b;
                carry_out = 1'b0;
            end
            default: begin
                result    = 8'h00;
                carry_out = 1'b0;
            end
        endcase
    end

    assign zero_flag = (result == 8'h00);

endmodule
