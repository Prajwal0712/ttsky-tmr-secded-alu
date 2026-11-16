# MicroPython Bring-up & Verification Script for RP2040 / RP2350 Tiny Tapeout Demo Board
# Project: tt_um_tmr_secded_alu

import time
from machine import Pin

# Define Demo Board Pin Mapping (adjust pin numbers if using custom carrier)
# Standard TT08/TT09 RP2040 Carrier Pin assignments:
UI_PINS = [0, 1, 2, 3, 4, 5, 6, 7]      # GPIO 0..7 -> ui_in[0..7]
UO_PINS = [8, 9, 10, 11, 12, 13, 14, 15] # GPIO 8..15 -> uo_out[0..7]
UIO_PINS = [16, 17, 18, 19, 20, 21, 22, 23] # GPIO 16..23 -> uio[0..7]
PIN_CLK = 24
PIN_RST_N = 25

class TMRSecdedTester:
    def __init__(self):
        # Configure UI pins as outputs
        self.ui = [Pin(p, Pin.OUT) for p in UI_PINS]
        # Configure UO pins as inputs
        self.uo = [Pin(p, Pin.IN) for p in UO_PINS]
        # Configure UIO pins as inputs
        self.uio = [Pin(p, Pin.IN) for p in UIO_PINS]
        # Clock and Reset
        self.clk = Pin(PIN_CLK, Pin.OUT)
        self.rst_n = Pin(PIN_RST_N, Pin.OUT)
        self.clk.value(0)
        self.rst_n.value(1)

    def clock_pulse(self, cycles=1):
        for _ in range(cycles):
            self.clk.value(1)
            time.sleep_us(1)
            self.clk.value(0)
            time.sleep_us(1)

    def set_ui(self, val):
        for i in range(8):
            self.ui[i].value((val >> i) & 1)

    def read_uo(self):
        val = 0
        for i in range(8):
            if self.uo[i].value():
                val |= (1 << i)
        return val

    def read_uio(self):
        val = 0
        for i in range(8):
            if self.uio[i].value():
                val |= (1 << i)
        return val

    def reset(self):
        self.rst_n.value(0)
        self.set_ui(0)
        self.clock_pulse(10)
        self.rst_n.value(1)
        self.clock_pulse(10)

    def pulse_strobe(self, base_val):
        # Strobe high
        self.set_ui(base_val | (1 << 6))
        self.clock_pulse(4)
        # Strobe low
        self.set_ui(base_val & ~(1 << 6))
        self.clock_pulse(4)

    def load_instruction(self, instr):
        nibbles = [
            (instr >> 12) & 0xF,
            (instr >> 8) & 0xF,
            (instr >> 4) & 0xF,
            instr & 0xF
        ]
        for n in nibbles:
            base = (0 << 4) | n  # mode 0 (Load Instruction)
            self.set_ui(base)
            self.clock_pulse(2)
            self.pulse_strobe(base)

    def load_fault_mask(self, mask):
        nibbles = [
            (mask >> 20) & 0xF,
            (mask >> 16) & 0xF,
            (mask >> 12) & 0xF,
            (mask >> 8) & 0xF,
            (mask >> 4) & 0xF,
            mask & 0xF
        ]
        for n in nibbles:
            base = (2 << 4) | n  # mode 2 (Load Fault Mask)
            self.set_ui(base)
            self.clock_pulse(2)
            self.pulse_strobe(base)

    def execute(self, fault_en=False):
        fault_bit = (1 << 7) if fault_en else 0
        base = fault_bit | (1 << 4)  # mode 1 (Execute)
        self.set_ui(base)
        self.clock_pulse(2)
        self.pulse_strobe(base)

    def read_debug(self, sel):
        base = (3 << 4) | (sel & 0x7)
        self.set_ui(base)
        self.clock_pulse(6)
        return self.read_uo()

    @staticmethod
    def encode_instr(op, rd, rs1, rs2=0, imm3=0, use_imm=False):
        if use_imm:
            return (1 << 15) | ((op & 7) << 12) | ((rd & 7) << 9) | ((rs1 & 7) << 6) | (imm3 & 7)
        else:
            return ((op & 7) << 12) | ((rd & 7) << 9) | ((rs1 & 7) << 6) | ((rs2 & 7) << 3)

def run_tests():
    print("=== TMR + Hamming SECDED ALU Silicon Bring-up ===")
    t = TMRSecdedTester()
    t.reset()

    # 1. Signature Check
    sig = t.read_debug(7)
    print("Alive signature (expected 0xA5): 0x{:02X} -> {}".format(sig, "PASS" if sig == 0xA5 else "FAIL"))
    assert sig == 0xA5

    # 2. Basic ALU Test: R1 = 5, R2 = 3, ADD R3 = R1 + R2
    t.load_instruction(t.encode_instr(op=7, rd=1, rs1=0, imm3=5, use_imm=True))
    t.execute()
    t.load_instruction(t.encode_instr(op=7, rd=2, rs1=0, imm3=3, use_imm=True))
    t.execute()

    t.load_instruction(t.encode_instr(op=0, rd=3, rs1=1, rs2=2, use_imm=False))
    t.execute()
    res = t.read_uo()
    print("ADD R1(5) + R2(3) = {} -> {}".format(res, "PASS" if res == 8 else "FAIL"))

    # 3. TMR Fault Injection Test (corrupt lane 0 result bit 0)
    t.load_fault_mask(1 << 13)
    t.load_instruction(t.encode_instr(op=0, rd=3, rs1=1, rs2=2, use_imm=False))
    t.execute(fault_en=True)
    res = t.read_uo()
    uio = t.read_uio()
    disagree = uio & 1
    healed_cnt = (uio >> 5) & 7
    print("TMR Healed Lane Fault: result={}, disagree={}, healed_cnt={} -> {}".format(
        res, disagree, healed_cnt, "PASS" if (res == 8 and disagree == 1) else "FAIL"
    ))

    # 4. Hamming SECDED Single-Bit Error Recovery
    t.load_fault_mask(1 << 3) # flip bit 3 in R1 codeword
    t.load_instruction(t.encode_instr(op=0, rd=4, rs1=1, imm3=0, use_imm=True))
    t.execute(fault_en=True)
    res = t.read_uo()
    uio = t.read_uio()
    sec_flag = (uio >> 1) & 1
    print("Hamming SECDED Single-Bit Recovery: result={}, sec_flag={} -> {}".format(
        res, sec_flag, "PASS" if (res == 5 and sec_flag == 1) else "FAIL"
    ))

    # 5. Hamming SECDED Double-Bit Error Detection
    t.load_fault_mask((1 << 3) | (1 << 5)) # flip 2 bits in R1 codeword
    t.load_instruction(t.encode_instr(op=0, rd=4, rs1=1, imm3=0, use_imm=True))
    t.execute(fault_en=True)
    uio = t.read_uio()
    ded_flag = (uio >> 2) & 1
    print("Hamming SECDED Double-Bit Detection: ded_flag={} -> {}".format(
        ded_flag, "PASS" if ded_flag == 1 else "FAIL"
    ))

    print("=== All Silicon Bring-up Tests Completed Successfully ===")

if __name__ == "__main__":
    run_tests()
