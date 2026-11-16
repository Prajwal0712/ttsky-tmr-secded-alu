/*
 * Copyright (c) 2024 Tiny Tapeout
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module hamming_13_8_enc (
    input  wire [7:0]  data_in,
    output wire [12:0] codeword
);

    wire p1, p2, p4, p8, p0;

    // Bit positions in 12-bit Hamming:
    // 1: p1, 2: p2, 3: d[0], 4: p4, 5: d[1], 6: d[2], 7: d[3],
    // 8: p8, 9: d[4], 10: d[5], 11: d[6], 12: d[7]
    assign p1 = data_in[0] ^ data_in[1] ^ data_in[3] ^ data_in[4] ^ data_in[6];
    assign p2 = data_in[0] ^ data_in[2] ^ data_in[3] ^ data_in[5] ^ data_in[6];
    assign p4 = data_in[1] ^ data_in[2] ^ data_in[3] ^ data_in[7];
    assign p8 = data_in[4] ^ data_in[5] ^ data_in[6] ^ data_in[7];

    // Overall even-parity bit p0 covering all 13 bits (c[0] ^ sum(c[1..12]) = 0)
    assign p0 = p1 ^ p2 ^ data_in[0] ^ p4 ^ data_in[1] ^ data_in[2] ^ data_in[3] ^
                p8 ^ data_in[4] ^ data_in[5] ^ data_in[6] ^ data_in[7];

    assign codeword[0]  = p0;
    assign codeword[1]  = p1;
    assign codeword[2]  = p2;
    assign codeword[3]  = data_in[0];
    assign codeword[4]  = p4;
    assign codeword[5]  = data_in[1];
    assign codeword[6]  = data_in[2];
    assign codeword[7]  = data_in[3];
    assign codeword[8]  = p8;
    assign codeword[9]  = data_in[4];
    assign codeword[10] = data_in[5];
    assign codeword[11] = data_in[6];
    assign codeword[12] = data_in[7];

endmodule
