# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


def make_instr(op, rd, rs1, rs2=0, imm3=0, use_imm=False):
    """Encodes a 16-bit instruction word."""
    val = 0
    if use_imm:
        val |= (1 << 15)
        val |= ((op & 7) << 12)
        val |= ((rd & 7) << 9)
        val |= ((rs1 & 7) << 6)
        val |= (imm3 & 7)
    else:
        val |= ((op & 7) << 12)
        val |= ((rd & 7) << 9)
        val |= ((rs1 & 7) << 6)
        val |= ((rs2 & 7) << 3)
    return val


async def pulse_strobe(dut, base_val):
    """Pulses the step_strobe input (ui_in[6]) with sufficient cycles for 2-FF synchronizer."""
    dut.ui_in.value = base_val | (1 << 6)
    await ClockCycles(dut.clk, 4)
    dut.ui_in.value = base_val & ~(1 << 6)
    await ClockCycles(dut.clk, 4)


async def load_instruction(dut, instr):
    """Loads a 16-bit instruction via 4 nibbles in mode 2'b00."""
    nibbles = [
        (instr >> 12) & 0xF,
        (instr >> 8) & 0xF,
        (instr >> 4) & 0xF,
        instr & 0xF,
    ]
    for n in nibbles:
        base = (0 << 4) | n  # mode 0, nibble n, fault_inject_en=0
        dut.ui_in.value = base
        await ClockCycles(dut.clk, 2)
        await pulse_strobe(dut, base)


async def load_fault_mask(dut, mask):
    """Loads a 24-bit fault mask via 6 nibbles in mode 2'b10."""
    nibbles = [
        (mask >> 20) & 0xF,
        (mask >> 16) & 0xF,
        (mask >> 12) & 0xF,
        (mask >> 8) & 0xF,
        (mask >> 4) & 0xF,
        mask & 0xF,
    ]
    for n in nibbles:
        base = (2 << 4) | n  # mode 2, nibble n, fault_inject_en=0
        dut.ui_in.value = base
        await ClockCycles(dut.clk, 2)
        await pulse_strobe(dut, base)


async def execute(dut, fault_en=False):
    """Executes the current instruction in mode 2'b01."""
    fault_bit = (1 << 7) if fault_en else 0
    base = fault_bit | (1 << 4)  # mode 1
    dut.ui_in.value = base
    await ClockCycles(dut.clk, 2)
    await pulse_strobe(dut, base)


async def read_debug(dut, sel):
    """Reads a debug byte via mode 2'b11."""
    base = (3 << 4) | (sel & 0x7)
    dut.ui_in.value = base
    await ClockCycles(dut.clk, 6)
    return int(dut.uo_out.value)


async def setup_dut(dut):
    """Initializes clock and performs synchronous reset."""
    clock = Clock(dut.clk, 20, unit="ns")  # 50 MHz
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0

    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


@cocotb.test()
async def test_reset_and_signature(dut):
    """Verifies reset initialization and 0xA5 alive signature byte."""
    await setup_dut(dut)

    # In mode 3 (Debug Readout), sel 7 must return 0xA5
    sig = await read_debug(dut, 7)
    assert sig == 0xA5, f"Expected signature 0xA5, got 0x{sig:02X}"

    # Dedicated outputs check: uio_oe must be 0xFF
    assert dut.uio_oe.value == 0xFF, f"Expected uio_oe=0xFF, got 0x{int(dut.uio_oe.value):02X}"


@cocotb.test()
async def test_all_alu_opcodes(dut):
    """Verifies all 8 ALU opcodes and carry/zero flags."""
    await setup_dut(dut)

    # Initialize R1 = 5, R2 = 3 using PASS_B (op 7, use_imm 1)
    await load_instruction(dut, make_instr(op=7, rd=1, rs1=0, imm3=5, use_imm=True))
    await execute(dut)
    assert int(dut.uo_out.value) == 5

    await load_instruction(dut, make_instr(op=7, rd=2, rs1=0, imm3=3, use_imm=True))
    await execute(dut)
    assert int(dut.uo_out.value) == 3

    # Op 0: ADD R3 = R1 + R2 -> 5 + 3 = 8
    await load_instruction(dut, make_instr(op=0, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut)
    assert int(dut.uo_out.value) == 8, f"ADD failed: got {int(dut.uo_out.value)}"

    # Op 1: SUB R3 = R1 - R2 -> 5 - 3 = 2
    await load_instruction(dut, make_instr(op=1, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut)
    assert int(dut.uo_out.value) == 2, f"SUB failed: got {int(dut.uo_out.value)}"

    # Op 2: AND R3 = R1 & R2 -> 5 & 3 = 1
    await load_instruction(dut, make_instr(op=2, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut)
    assert int(dut.uo_out.value) == 1, f"AND failed: got {int(dut.uo_out.value)}"

    # Op 3: OR R3 = R1 | R2 -> 5 | 3 = 7
    await load_instruction(dut, make_instr(op=3, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut)
    assert int(dut.uo_out.value) == 7, f"OR failed: got {int(dut.uo_out.value)}"

    # Op 4: XOR R3 = R1 ^ R2 -> 5 ^ 3 = 6
    await load_instruction(dut, make_instr(op=4, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut)
    assert int(dut.uo_out.value) == 6, f"XOR failed: got {int(dut.uo_out.value)}"

    # Op 5: SHL R3 = R1 << 1 -> 5 << 1 = 10
    await load_instruction(dut, make_instr(op=5, rd=3, rs1=1, imm3=1, use_imm=True))
    await execute(dut)
    assert int(dut.uo_out.value) == 10, f"SHL failed: got {int(dut.uo_out.value)}"

    # Op 6: SHR R3 = R3 >> 1 -> 10 >> 1 = 5
    await load_instruction(dut, make_instr(op=6, rd=3, rs1=3, imm3=1, use_imm=True))
    await execute(dut)
    assert int(dut.uo_out.value) == 5, f"SHR failed: got {int(dut.uo_out.value)}"

    # Op 7: PASS_B with immediate: R3 = 4
    await load_instruction(dut, make_instr(op=7, rd=3, rs1=0, imm3=4, use_imm=True))
    await execute(dut)
    assert int(dut.uo_out.value) == 4, f"PASS_B failed: got {int(dut.uo_out.value)}"

    # Zero flag test: R3 - R3 -> 0
    await load_instruction(dut, make_instr(op=1, rd=3, rs1=3, rs2=3, use_imm=False))
    await execute(dut)
    assert int(dut.uo_out.value) == 0
    uio = int(dut.uio_out.value)
    zero_flag = (uio >> 3) & 1
    assert zero_flag == 1, f"Expected zero_flag=1, got {zero_flag}"

    # Carry flag test: 224 + 56 = 280 -> 24 with carry_out=1
    await load_instruction(dut, make_instr(op=7, rd=1, rs1=0, imm3=7, use_imm=True))
    await execute(dut)
    await load_instruction(dut, make_instr(op=5, rd=1, rs1=1, imm3=5, use_imm=True))
    await execute(dut)  # R1 = 7 << 5 = 224

    await load_instruction(dut, make_instr(op=7, rd=2, rs1=0, imm3=7, use_imm=True))
    await execute(dut)
    await load_instruction(dut, make_instr(op=5, rd=2, rs1=2, imm3=3, use_imm=True))
    await execute(dut)  # R2 = 7 << 3 = 56

    await load_instruction(dut, make_instr(op=0, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut)
    assert int(dut.uo_out.value) == 24
    uio = int(dut.uio_out.value)
    carry_flag = (uio >> 4) & 1
    assert carry_flag == 1, f"Expected carry_flag=1, got {carry_flag}"


@cocotb.test()
async def test_register_file_rw(dut):
    """Verifies writing and reading back all 8 registers R0-R7."""
    await setup_dut(dut)

    # Write distinct values into all registers R0..R7
    for reg_idx in range(8):
        await load_instruction(
            dut, make_instr(op=7, rd=reg_idx, rs1=0, imm3=reg_idx, use_imm=True)
        )
        await execute(dut)
        assert int(dut.uo_out.value) == reg_idx

    # Read back all registers R0..R7 via ADD R0 = Rx + 0
    for reg_idx in range(8):
        await load_instruction(
            dut, make_instr(op=0, rd=0, rs1=reg_idx, imm3=0, use_imm=True)
        )
        await execute(dut)
        assert int(dut.uo_out.value) == reg_idx, (
            f"Readback of R{reg_idx} failed: got {int(dut.uo_out.value)}"
        )


@cocotb.test()
async def test_tmr_fault_injection(dut):
    """Verifies TMR fault masking, disagreement detection, and error counter increment."""
    await setup_dut(dut)

    # Setup R1 = 5, R2 = 3
    await load_instruction(dut, make_instr(op=7, rd=1, rs1=0, imm3=5, use_imm=True))
    await execute(dut)
    await load_instruction(dut, make_instr(op=7, rd=2, rs1=0, imm3=3, use_imm=True))
    await execute(dut)

    # 1. Single-bit corruption on ALU Lane 0 result bus (mask bit 13 = 1)
    await load_fault_mask(dut, 1 << 13)
    await load_instruction(dut, make_instr(op=0, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut, fault_en=True)

    # TMR voter must heal the single lane corruption
    assert int(dut.uo_out.value) == 8, (
        f"TMR fault recovery failed: got {int(dut.uo_out.value)}"
    )

    uio = int(dut.uio_out.value)
    tmr_disagreement = uio & 1
    healed_err_cnt = (uio >> 5) & 7
    assert tmr_disagreement == 1, "tmr_disagreement must be asserted"
    assert healed_err_cnt == 1, f"Expected healed_err_cnt=1, got {healed_err_cnt}"

    # 2. Multi-bit corruption on ALU Lane 0 result bus (mask bits [16:13] = 0xF)
    await load_fault_mask(dut, 0xF << 13)
    await load_instruction(dut, make_instr(op=0, rd=3, rs1=1, rs2=2, use_imm=False))
    await execute(dut, fault_en=True)

    assert int(dut.uo_out.value) == 8
    uio = int(dut.uio_out.value)
    assert (uio & 1) == 1, "tmr_disagreement must be asserted on multi-bit lane fault"
    assert ((uio >> 5) & 7) == 2, "healed_err_cnt must increment to 2"


@cocotb.test()
async def test_hamming_secded_single_bit_recovery(dut):
    """Verifies Hamming (13,8) SECDED transparent single-bit error recovery."""
    await setup_dut(dut)

    # Write R1 = 5
    await load_instruction(dut, make_instr(op=7, rd=1, rs1=0, imm3=5, use_imm=True))
    await execute(dut)

    # Flip bit 3 in R1 read codeword (data bit 0): mask = 1 << 3
    await load_fault_mask(dut, 1 << 3)
    # Read R1 via ADD R4 = R1 + 0
    await load_instruction(dut, make_instr(op=0, rd=4, rs1=1, imm3=0, use_imm=True))
    await execute(dut, fault_en=True)

    # Output must be completely uncorrupted (5)
    assert int(dut.uo_out.value) == 5, (
        f"Hamming SEC recovery failed: got {int(dut.uo_out.value)}"
    )

    uio = int(dut.uio_out.value)
    sec_flag = (uio >> 1) & 1
    ded_flag = (uio >> 2) & 1
    healed_err_cnt = (uio >> 5) & 7
    assert sec_flag == 1, f"Expected sec_flag=1, got {sec_flag}"
    assert ded_flag == 0, f"Expected ded_flag=0, got {ded_flag}"
    assert healed_err_cnt == 1, f"Expected healed_err_cnt=1, got {healed_err_cnt}"

    # Flip overall parity bit (bit 0): mask = 1 << 0
    await load_fault_mask(dut, 1 << 0)
    await load_instruction(dut, make_instr(op=0, rd=4, rs1=1, imm3=0, use_imm=True))
    await execute(dut, fault_en=True)

    assert int(dut.uo_out.value) == 5
    uio = int(dut.uio_out.value)
    assert ((uio >> 1) & 1) == 1, "sec_flag must be 1 on parity bit error"
    assert ((uio >> 2) & 1) == 0, "ded_flag must be 0"
    assert ((uio >> 5) & 7) == 2, "healed_err_cnt must increment to 2"


@cocotb.test()
async def test_hamming_secded_double_bit_detection(dut):
    """Verifies Hamming (13,8) SECDED double-bit error detection (DED)."""
    await setup_dut(dut)

    # Write R1 = 5
    await load_instruction(dut, make_instr(op=7, rd=1, rs1=0, imm3=5, use_imm=True))
    await execute(dut)

    # Inject 2-bit flip in R1 read codeword: bits 3 and 5 (mask = (1<<3) | (1<<5))
    await load_fault_mask(dut, (1 << 3) | (1 << 5))
    # Execute instruction reading R1
    await load_instruction(dut, make_instr(op=0, rd=4, rs1=1, imm3=0, use_imm=True))
    await execute(dut, fault_en=True)

    uio = int(dut.uio_out.value)
    sec_flag = (uio >> 1) & 1
    ded_flag = (uio >> 2) & 1
    healed_err_cnt = (uio >> 5) & 7

    assert ded_flag == 1, f"Expected ded_flag=1 on 2-bit error, got {ded_flag}"
    assert sec_flag == 0, f"Expected sec_flag=0 on 2-bit error, got {sec_flag}"
    assert healed_err_cnt == 0, "Counter should not increment for unhealed DED error"
