# Fault-Tolerant TMR + Hamming (13,8) SECDED 8-bit ALU & Register File

A radiation-hardened / high-reliability 8-bit processing unit designed for the SKY130 process in a standard 1x1 Tiny Tapeout tile (~160 x 100 um). It incorporates **Triple Modular Redundant (TMR)** ALUs with bitwise majority voting alongside a **Hamming (13,8) Single-Error Correction, Double-Error Detection (SECDED)** protected 8-register storage file. A built-in controllable fault injection subsystem allows live verification of fault masking and telemetry reporting on physical silicon.

---

## Architecture Overview

```
                      +-----------------------------------+
                      |   16-bit Instruction Register     |
                      |   {use_imm, op[2:0], rd, rs1, rs2, imm3}
                      +-----------------+-----------------+
                                        |
     +----------------------------------+---------------------------------+
     |                                                                    |
+----+--------------------+                                  +------------+------------+
|  8x13-bit SECDED        |                                  |   Immediate Generator   |
|  Register File          |                                  |   {5'b0, imm3}          |
|  (R0-R7)                |                                  +------------+------------+
+----+---------------+----+                                               |
     | RS1           | RS2                                                |
     v               v                                                    v
[XOR Mask]           |                                                    |
[SECDED Dec]         |                                                    |
     |               +-----------------------\ /--------------------------+
     | rdata1 (8b)                            |  rdata2 / imm (8b)
     +---------------------+------------------+
                           |
       +-------------------+-------------------+
       |                   |                   |
       v                   v                   v
+--------------+    +--------------+    +--------------+
| ALU Lane 0   |    | ALU Lane 1   |    | ALU Lane 2   |
| (keep/touch) |    | (keep/touch) |    | (keep/touch) |
+------+-------+    +------+-------+    +------+-------+
       |                   |                   |
  [XOR Fault]              |                   |
       |                   |                   |
       +-------------------+-------------------+
                           |
                           v
              +-------------------------+
              |    TMR Majority Voter   |
              |  (Result, Carry, Zero)  |
              +------------+------------+
                           |
         +-----------------+-----------------+
         |                                   |
         v                                   v
+------------------+                +------------------+
| Writeback to RD  |                | Status Telemetry |
| in Register File |                | & Disagreement   |
| (SECDED Enc)     |                | Counter (UIO)    |
+------------------+                +------------------+
```

### Key Modules:
1. **ALU 8-bit (`src/alu_8bit.v`)**: Compact combinational ALU supporting 8 opcodes:
   - `3'b000`: `ADD` (`a + b`)
   - `3'b001`: `SUB` (`a - b`)
   - `3'b010`: `AND` (`a & b`)
   - `3'b011`: `OR` (`a | b`)
   - `3'b100`: `XOR` (`a ^ b`)
   - `3'b101`: `SHL` (`a << b[2:0]`)
   - `3'b110`: `SHR` (`a >> b[2:0]`)
   - `3'b111`: `PASS_B` (`b`)
2. **TMR Majority Voter (`src/tmr_voter.v`)**: Bitwise majority voter `(a & b) | (b & c) | (a & c)` across results, carry, and zero flags. Real-time comparator asserts `tmr_disagreement` whenever any lane differs from majority consensus.
3. **Hamming (13,8) SECDED Codec (`src/hamming_13_8_enc.v`, `src/hamming_13_8_dec.v`)**:
   - Codeword layout: Bit 0 = Overall Parity `P0`; Bits 1, 2, 4, 8 = Hamming Parities `P1`, `P2`, `P4`, `P8`; Bits 3, 5, 6, 7, 9, 10, 11, 12 = Data bits `d[0]`..`d[7]`.
   - Single-bit flips (in data or parity) are corrected transparently with `sec_flag = 1`.
   - Double-bit flips are identified as uncorrectable errors with `ded_flag = 1`.
4. **Fault-Tolerant Register File (`src/regfile_secded.v`)**:
   - 8 general-purpose registers (`R0`–`R7`) storing 13-bit SECDED codewords.
   - Read Port A passes through an XOR fault-injection gate into SECDED decoder.

---

## Control Protocol & Operational Modes

Input pins `ui_in[5:4]` configure the active operational mode:

| Mode `ui_in[5:4]` | Name | Operation on `step_strobe` (`ui_in[6]`) Rising Edge |
|:---:|:---|:---|
| `2'b00` | **Load Instruction** | Shifts 4-bit `nibble_in[3:0]` into `instr_reg[15:0]` (`instr_reg <= {instr_reg[11:0], nibble_in}`) |
| `2'b01` | **Execute** | Executes current `instr_reg`, stores voted result into `rd`, latches flags, increments saturating healed error counter |
| `2'b10` | **Load Fault Mask** | Shifts 4-bit `nibble_in[3:0]` into `fault_mask_reg[23:0]` (`fault_mask_reg <= {fault_mask_reg[19:0], nibble_in}`) |
| `2'b11` | **Debug Readout** | Selects internal telemetry register onto `uo_out[7:0]` based on `nibble_in[2:0]` |

### Instruction Format (`instr_reg[15:0]`):
- `[15]`: `use_imm` (`0` = use `rs2`, `1` = use `imm3` zero-extended to 8-bit)
- `[14:12]`: `opcode[2:0]` (`ADD`, `SUB`, `AND`, `OR`, `XOR`, `SHL`, `SHR`, `PASS_B`)
- `[11:9]`: `rd[2:0]` (Destination register in regfile)
- `[8:6]`: `rs1[2:0]` (Source register 1)
- `[5:3]`: `rs2[2:0]` (Source register 2)
- `[2:0]`: `imm3[2:0]` (Immediate operand when `use_imm == 1`)

### Fault Mask Register (`fault_mask_reg[23:0]`):
Active when `fault_inject_en == 1` (`ui_in[7] = 1`):
- `[12:0]`: Injected into 13-bit codeword on `rs1` read port of `regfile_secded`
- `[20:13]`: Injected into 8-bit output bus of `alu_lane0`
- `[21]`: Injected into `zero_flag` of `alu_lane0`
- `[22]`: Injected into `carry_out` of `alu_lane0`
- `[23]`: Synchronous clear for `healed_err_cnt`

### Debug Readout Multiplexer (`mode == 2'b11`):
Selected by `nibble_in[2:0]` (`ui_in[2:0]`):
- `3'd0`: `result_reg[7:0]`
- `3'd1`: `instr_reg[7:0]`
- `3'd2`: `instr_reg[15:8]`
- `3'd3`: Status `{healed_err_cnt[2:0], alu_carry, alu_zero, hamming_ded_flag, hamming_sec_flag, tmr_disagreement}`
- `3'd4`: `fault_mask_reg[7:0]`
- `3'd5`: `fault_mask_reg[15:8]`
- `3'd6`: `fault_mask_reg[23:16]`
- `3'd7`: `8'hA5` (Silicon alive / bring-up signature byte)

---

## Pinout Summary

### Inputs (`ui_in`):
- `ui_in[3:0]`: 4-bit nibble input (`nibble_in`)
- `ui_in[5:4]`: Operational Mode (`00`=LoadInstr, `01`=Exec, `10`=LoadMask, `11`=Debug)
- `ui_in[6]`: Single-step strobe (`step_strobe`)
- `ui_in[7]`: Fault injection enable (`fault_inject_en`)

### Outputs (`uo_out`):
- `uo_out[7:0]`: ALU execution result (`result_reg[7:0]`) during normal operation, or selected debug register in debug mode.

### Dedicated Telemetry LEDs (`uio_out`):
All bidirectional pins configured as dedicated outputs (`uio_oe = 8'hFF`):
- `uio_out[0]`: `tmr_disagreement` (TMR voter corrected lane mismatch)
- `uio_out[1]`: `hamming_sec_flag` (Hamming SECDED corrected single-bit error)
- `uio_out[2]`: `hamming_ded_flag` (Hamming SECDED detected double-bit error)
- `uio_out[3]`: `alu_zero`
- `uio_out[4]`: `alu_carry`
- `uio_out[7:5]`: `healed_err_cnt[2:0]` (3-bit saturating healed-error counter)

---

## Bring-up & Verification Guide

1. **Power & Reset**:
   - Assert `rst_n = 0` for >= 2 clock cycles, then deassert `rst_n = 1`.
2. **Read Signature**:
   - Set `ui_in = 8'b0011_0111` (`mode = 2'b11`, `nibble_in = 3'd7`).
   - Observe `uo_out == 8'hA5`.
3. **Execute Simple Instruction**:
   - Shift 16-bit word `0xF205` into instruction register (loads `5` into `R1`).
   - Trigger execute strobe (`mode = 2'b01`, pulse `ui_in[6]`).
   - Observe `uo_out == 8'h05`.
