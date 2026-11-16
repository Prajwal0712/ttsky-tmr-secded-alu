/*
 * Copyright (c) 2024 Tiny Tapeout
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module regfile_secded (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [2:0]  rs1,
    input  wire [2:0]  rs2,
    input  wire [2:0]  rd,
    input  wire        we,
    input  wire [7:0]  wdata,
    input  wire [12:0] rf_fault_mask,
    output wire [7:0]  rdata1,
    output wire [7:0]  rdata2,
    output wire        sec_flag,
    output wire        ded_flag
);

    // 8 registers storing 13-bit SECDED codewords
    reg [12:0] rf [0:7];

    // Encoder for write data
    wire [12:0] enc_wdata;
    hamming_13_8_enc u_enc (
        .data_in (wdata),
        .codeword(enc_wdata)
    );

    // Synchronous write and reset
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 8; i = i + 1) begin
                rf[i] <= 13'h0000;
            end
        end else if (we) begin
            rf[rd] <= enc_wdata;
        end
    end

    // Read Port 1 (rs1) with fault-injection mask applied before SECDED decoding
    wire [12:0] raw_rdata1    = rf[rs1];
    wire [12:0] masked_rdata1 = raw_rdata1 ^ rf_fault_mask;

    hamming_13_8_dec u_dec_port1 (
        .codeword_in (masked_rdata1),
        .data_out    (rdata1),
        .sec_flag    (sec_flag),
        .ded_flag    (ded_flag)
    );

    // Read Port 2 (rs2)
    wire [12:0] raw_rdata2 = rf[rs2];
    hamming_13_8_dec u_dec_port2 (
        .codeword_in (raw_rdata2),
        .data_out    (rdata2),
        .sec_flag    (),
        .ded_flag    ()
    );

endmodule
