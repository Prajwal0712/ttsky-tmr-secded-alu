/*
 * Copyright (c) 2024 Tiny Tapeout
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_tmr_secded_alu (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    // List unused inputs to avoid linter warnings
    wire _unused = &{ena, uio_in, 1'b0};

    // -------------------------------------------------------------
    // 1. Two-stage Input Synchronizer & Rising-Edge Detector
    // -------------------------------------------------------------
    reg [7:0] ui_sync1, ui_sync2;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ui_sync1 <= 8'h00;
            ui_sync2 <= 8'h00;
        end else begin
            ui_sync1 <= ui_in;
            ui_sync2 <= ui_sync1;
        end
    end

    wire [3:0] sync_nibble   = ui_sync2[3:0];
    wire [1:0] sync_mode     = ui_sync2[5:4];
    wire       sync_strobe   = ui_sync2[6];
    wire       sync_fault_en = ui_sync2[7];

    reg sync_strobe_d;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync_strobe_d <= 1'b0;
        end else begin
            sync_strobe_d <= sync_strobe;
        end
    end
    wire strobe_rising = sync_strobe && (!sync_strobe_d);

    // -------------------------------------------------------------
    // 2. Registers & State Elements
    // -------------------------------------------------------------
    reg [15:0] instr_reg;
    reg [23:0] fault_mask_reg;
    reg [7:0]  result_reg;
    reg        alu_carry_reg;
    reg        alu_zero_reg;
    reg        tmr_disagreement_reg;
    reg        hamming_sec_reg;
    reg        hamming_ded_reg;
    reg [2:0]  healed_err_cnt;

    // -------------------------------------------------------------
    // 3. Instruction Decoding
    // -------------------------------------------------------------
    wire       use_imm = instr_reg[15];
    wire [2:0] opcode  = instr_reg[14:12];
    wire [2:0] rd      = instr_reg[11:9];
    wire [2:0] rs1     = instr_reg[8:6];
    wire [2:0] rs2     = instr_reg[5:3];
    wire [7:0] imm8    = {5'b00000, instr_reg[2:0]};

    // -------------------------------------------------------------
    // 4. SECDED Register File (8 x 13-bit)
    // -------------------------------------------------------------
    wire [7:0]  rf_rdata1;
    wire [7:0]  rf_rdata2;
    wire        rf_sec_flag;
    wire        rf_ded_flag;
    wire [12:0] active_rf_fault_mask = sync_fault_en ? fault_mask_reg[12:0] : 13'h0000;
    wire [7:0]  voted_result;

    regfile_secded u_regfile (
        .clk           (clk),
        .rst_n         (rst_n),
        .rs1           (rs1),
        .rs2           (rs2),
        .rd            (rd),
        .we            (strobe_rising && (sync_mode == 2'b01)),
        .wdata         (voted_result),
        .rf_fault_mask (active_rf_fault_mask),
        .rdata1        (rf_rdata1),
        .rdata2        (rf_rdata2),
        .sec_flag      (rf_sec_flag),
        .ded_flag      (rf_ded_flag)
    );

    // -------------------------------------------------------------
    // 5. ALU Operands
    // -------------------------------------------------------------
    wire [7:0] alu_op_a = rf_rdata1;
    wire [7:0] alu_op_b = (use_imm) ? imm8 : rf_rdata2;

    // -------------------------------------------------------------
    // 6. Triple Modular Redundant (TMR) ALUs
    //    (* keep = "true" *) and (* dont_touch = "true" *)
    //    prevent Yosys from deduplicating redundant hardware.
    // -------------------------------------------------------------
    (* keep = "true", dont_touch = "true" *) wire [7:0] alu0_result_raw;
    (* keep = "true", dont_touch = "true" *) wire       alu0_carry_raw;
    (* keep = "true", dont_touch = "true" *) wire       alu0_zero_raw;

    (* keep = "true", dont_touch = "true" *) wire [7:0] alu1_result;
    (* keep = "true", dont_touch = "true" *) wire       alu1_carry;
    (* keep = "true", dont_touch = "true" *) wire       alu1_zero;

    (* keep = "true", dont_touch = "true" *) wire [7:0] alu2_result;
    (* keep = "true", dont_touch = "true" *) wire       alu2_carry;
    (* keep = "true", dont_touch = "true" *) wire       alu2_zero;

    (* keep = "true", dont_touch = "true" *) alu_8bit u_alu_lane0 (
        .a        (alu_op_a),
        .b        (alu_op_b),
        .op       (opcode),
        .result   (alu0_result_raw),
        .carry_out(alu0_carry_raw),
        .zero_flag(alu0_zero_raw)
    );

    (* keep = "true", dont_touch = "true" *) alu_8bit u_alu_lane1 (
        .a        (alu_op_a),
        .b        (alu_op_b),
        .op       (opcode),
        .result   (alu1_result),
        .carry_out(alu1_carry),
        .zero_flag(alu1_zero)
    );

    (* keep = "true", dont_touch = "true" *) alu_8bit u_alu_lane2 (
        .a        (alu_op_a),
        .b        (alu_op_b),
        .op       (opcode),
        .result   (alu2_result),
        .carry_out(alu2_carry),
        .zero_flag(alu2_zero)
    );

    // Fault injection onto Lane 0 outputs when fault_inject_en == 1
    (* keep = "true", dont_touch = "true" *) wire [7:0] alu0_result = sync_fault_en ? (alu0_result_raw ^ fault_mask_reg[20:13]) : alu0_result_raw;
    (* keep = "true", dont_touch = "true" *) wire       alu0_carry  = sync_fault_en ? (alu0_carry_raw  ^ fault_mask_reg[22])    : alu0_carry_raw;
    (* keep = "true", dont_touch = "true" *) wire       alu0_zero   = sync_fault_en ? (alu0_zero_raw   ^ fault_mask_reg[21])    : alu0_zero_raw;

    // -------------------------------------------------------------
    // 7. TMR Majority Voter
    // -------------------------------------------------------------
    wire voted_carry;
    wire voted_zero;
    wire tmr_disagreement;

    tmr_voter u_tmr_voter (
        .alu0_result      (alu0_result),
        .alu0_carry       (alu0_carry),
        .alu0_zero        (alu0_zero),
        .alu1_result      (alu1_result),
        .alu1_carry       (alu1_carry),
        .alu1_zero        (alu1_zero),
        .alu2_result      (alu2_result),
        .alu2_carry       (alu2_carry),
        .alu2_zero        (alu2_zero),
        .voted_result     (voted_result),
        .voted_carry      (voted_carry),
        .voted_zero       (voted_zero),
        .tmr_disagreement (tmr_disagreement)
    );

    // -------------------------------------------------------------
    // 8. Control & Status Sequential Logic
    // -------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            instr_reg            <= 16'h0000;
            fault_mask_reg       <= 24'h000000;
            result_reg           <= 8'h00;
            alu_carry_reg        <= 1'b0;
            alu_zero_reg         <= 1'b0;
            tmr_disagreement_reg <= 1'b0;
            hamming_sec_reg      <= 1'b0;
            hamming_ded_reg      <= 1'b0;
            healed_err_cnt       <= 3'b000;
        end else begin
            // Reset healed_err_cnt when fault_mask_reg[23] is pulsed with fault_inject_en
            if (sync_fault_en && fault_mask_reg[23]) begin
                healed_err_cnt <= 3'b000;
            end

            if (strobe_rising) begin
                case (sync_mode)
                    2'b00: begin // Load Instruction
                        instr_reg <= {instr_reg[11:0], sync_nibble};
                    end
                    2'b01: begin // Execute Instruction
                        result_reg           <= voted_result;
                        alu_carry_reg        <= voted_carry;
                        alu_zero_reg         <= voted_zero;
                        tmr_disagreement_reg <= tmr_disagreement;
                        hamming_sec_reg      <= rf_sec_flag;
                        hamming_ded_reg      <= rf_ded_flag;

                        // Increment saturating 3-bit healed error counter
                        if ((tmr_disagreement || rf_sec_flag) && !(sync_fault_en && fault_mask_reg[23])) begin
                            if (healed_err_cnt != 3'b111) begin
                                healed_err_cnt <= healed_err_cnt + 3'b001;
                            end
                        end
                    end
                    2'b10: begin // Load Fault Mask
                        fault_mask_reg <= {fault_mask_reg[19:0], sync_nibble};
                    end
                    default: begin
                        // 2'b11: Debug Readout Select (no register state change)
                    end
                endcase
            end
        end
    end

    // -------------------------------------------------------------
    // 9. Output Muxing & Dedicated Telemetry
    // -------------------------------------------------------------
    reg [7:0] debug_byte;
    always @(*) begin
        case (sync_nibble[2:0])
            3'd0: debug_byte = result_reg;
            3'd1: debug_byte = instr_reg[7:0];
            3'd2: debug_byte = instr_reg[15:8];
            3'd3: debug_byte = {healed_err_cnt, alu_carry_reg, alu_zero_reg, hamming_ded_reg, hamming_sec_reg, tmr_disagreement_reg};
            3'd4: debug_byte = fault_mask_reg[7:0];
            3'd5: debug_byte = fault_mask_reg[15:8];
            3'd6: debug_byte = fault_mask_reg[23:16];
            3'd7: debug_byte = 8'hA5;
            default: debug_byte = 8'h00;
        endcase
    end

    // uo_out: result_reg whenever mode != 2'b11, or debug byte when mode == 2'b11
    assign uo_out = (sync_mode == 2'b11) ? debug_byte : result_reg;

    // Dedicated status outputs on bidirectional pins
    assign uio_oe = 8'hFF;
    assign uio_out = {healed_err_cnt, alu_carry_reg, alu_zero_reg, hamming_ded_reg, hamming_sec_reg, tmr_disagreement_reg};

endmodule
