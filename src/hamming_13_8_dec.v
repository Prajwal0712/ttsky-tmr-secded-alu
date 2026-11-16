/*
 * Copyright (c) 2024 Tiny Tapeout
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module hamming_13_8_dec (
    input  wire [12:0] codeword_in,
    output wire [7:0]  data_out,
    output wire        sec_flag,
    output wire        ded_flag
);

    wire p;
    wire [3:0] s;

    // Overall parity over all 13 bits
    assign p = ^codeword_in;

    // 4-bit syndrome S[3:0] covering parity bits at positions 1, 2, 4, 8
    assign s[0] = codeword_in[1] ^ codeword_in[3] ^ codeword_in[5] ^
                  codeword_in[7] ^ codeword_in[9] ^ codeword_in[11];

    assign s[1] = codeword_in[2] ^ codeword_in[3] ^ codeword_in[6] ^
                  codeword_in[7] ^ codeword_in[10] ^ codeword_in[11];

    assign s[2] = codeword_in[4] ^ codeword_in[5] ^ codeword_in[6] ^
                  codeword_in[7] ^ codeword_in[12];

    assign s[3] = codeword_in[8] ^ codeword_in[9] ^ codeword_in[10] ^
                  codeword_in[11] ^ codeword_in[12];

    // Single-Error Correction (SEC): P == 1 (odd parity indicates single-bit error)
    // Double-Error Detection (DED): S != 0 and P == 0 (even parity with non-zero syndrome)
    assign sec_flag = p;
    assign ded_flag = (s != 4'b0000) && (!p);

    // Correct codeword by flipping bit position S when single error occurs in 1..12
    wire [12:0] corr_codeword;
    assign corr_codeword[0]  = codeword_in[0] ^ (p && (s == 4'd0));
    assign corr_codeword[1]  = codeword_in[1] ^ (p && (s == 4'd1));
    assign corr_codeword[2]  = codeword_in[2] ^ (p && (s == 4'd2));
    assign corr_codeword[3]  = codeword_in[3] ^ (p && (s == 4'd3));
    assign corr_codeword[4]  = codeword_in[4] ^ (p && (s == 4'd4));
    assign corr_codeword[5]  = codeword_in[5] ^ (p && (s == 4'd5));
    assign corr_codeword[6]  = codeword_in[6] ^ (p && (s == 4'd6));
    assign corr_codeword[7]  = codeword_in[7] ^ (p && (s == 4'd7));
    assign corr_codeword[8]  = codeword_in[8] ^ (p && (s == 4'd8));
    assign corr_codeword[9]  = codeword_in[9] ^ (p && (s == 4'd9));
    assign corr_codeword[10] = codeword_in[10] ^ (p && (s == 4'd10));
    assign corr_codeword[11] = codeword_in[11] ^ (p && (s == 4'd11));
    assign corr_codeword[12] = codeword_in[12] ^ (p && (s == 4'd12));

    // Extract 8 data bits from corrected codeword
    assign data_out = {
        corr_codeword[12],
        corr_codeword[11],
        corr_codeword[10],
        corr_codeword[9],
        corr_codeword[7],
        corr_codeword[6],
        corr_codeword[5],
        corr_codeword[3]
    };

endmodule
