import smbus
import time
import math
import argparse
import sys

# I2C parametri
I2C_BUS = 1
SI5351A_ADDRESS = 0x60
XTAL_FREQ = 25000000
VCO_FREQ = 800000000

# Funkcija za upis u registar
def write_register(bus, address, reg, value, retries=5, skip_verify=False):
    for attempt in range(retries):
        try:
            bus.write_byte_data(address, reg, value)
            if skip_verify or reg == 0xB1 or reg == 1 or reg == 187:
                return
            read_back = bus.read_byte_data(address, reg)
            if read_back != value:
                if attempt == retries - 1:
                    raise OSError(f"Neuspesan upis u registar {reg}")
                time.sleep(0.05)
                continue
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(0.05)

# Funkcija za citanje iz registra
def read_register(bus, address, reg, retries=5):
    for attempt in range(retries):
        try:
            return bus.read_byte_data(address, reg)
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(0.05)

# Inicijalizacija Si5351A cipa  Synthesis Stage 1
def initialize(bus, address):
    # Cekanje da uređaj završi inicijalizaciju
    for _ in range(100):
        try:
            status = read_register(bus, address, 0x00)
            if (status & 0x80) == 0:
                break
            time.sleep(0.05)
        except OSError:
            time.sleep(0.05)
    else:
        print("Greska: inicijalizacija Si5351A nije zavrsena (SYS_INIT=1)")
        return False

    # Reset i osnovna konfiguracija
    write_register(bus, address, 2, 0x18)
    write_register(bus, address, 1, 0x00, skip_verify=True)
    write_register(bus, address, 149, 0x00)
    write_register(bus, address, 0x03, 0xFF)

    # Postavljanje kapacitivnosti kristala na 10 pF
    write_register(bus, address, 0xB7, 0xD2)

    # Gasenje neiskoriscenih ulaza
    write_register(bus, address, 19, 0x80)
    write_register(bus, address, 20, 0x80)
    write_register(bus, address, 21, 0x80)
    write_register(bus, address, 22, 0xC0)
    write_register(bus, address, 23, 0x80)

    # Povezivanje PLLA sa kristalom
    write_register(bus, address, 0x0F, 0x00)
    write_register(bus, address, 0xBB, 0x50, skip_verify=True)

    # Podesavanje PLLA
    p1 = 128 * 32 - 512
    write_register(bus, address, 26, 0x00)
    write_register(bus, address, 27, 0x01)
    write_register(bus, address, 28, 0x00)
    write_register(bus, address, 29, (p1 >> 8) & 0xFF)
    write_register(bus, address, 30, p1 & 0xFF)
    write_register(bus, address, 31, 0x00)
    write_register(bus, address, 32, 0x00)
    write_register(bus, address, 33, 0x00)

    # Reset PLLA
    try:
        write_register(bus, address, 0xB1, 0x20, skip_verify=True)
        time.sleep(0.1)
    except OSError:
        pass

    # Provera zakljucavanja PLLA
    for attempt in range(3):
        for _ in range(50):
            status = read_register(bus, address, 0x00)
            if (status & 0xA0) == 0:
                print("Si5351A inicijalizovan uspesno.")
                return True
            time.sleep(0.05)
        write_register(bus, address, 0xB7, 0xD2)
        write_register(bus, address, 0xB1, 0x20, skip_verify=True)
        time.sleep(0.1)
    print("Greska: PLLA se nije zakljucao.")
    return False

# Podesavanje izlazne frekvencije Synthesis Stage 2
def set_frequency(bus, address, clk_num, freq):
    if clk_num < 0 or clk_num > 2:
        print("Nevaseci CLK broj (0-2).")
        return
    if freq < 2500 or freq > 200000000:
        print("Frekvencija van opsega (2.5 kHz - 200 MHz).")
        return

    r = 1
    r_div = 0
    ms_div = VCO_FREQ / freq
    if freq < 500000:
        for r_val in [1, 2, 4, 8, 16, 32, 64, 128]:
            temp_ms_div = VCO_FREQ / (freq * r_val)
            if 8 <= temp_ms_div <= 2048:
                r = r_val
                ms_div = temp_ms_div
                break
        else:
            print("Nije moguce podesiti zeljenu frekvenciju.")
            return
        r_div = int(math.log2(r))
    else:
        ms_div = VCO_FREQ / freq

    if 150000000 < freq <= 200000000:
        ms_div = 4
        a = 4
        b = 0
        c = 1
        p1 = 0
        p2 = 0
        p3 = 1
        divby4 = 0x03
        integer_mode = 1
    else:
        a = math.floor(ms_div)
        fractional = ms_div - a
        b = math.floor(fractional * 1048575)
        c = 1048575
        if b == 0:
            c = 1
        p1 = 128 * a + math.floor(128 * b / c) - 512
        p2 = 128 * b - c * math.floor(128 * b / c)
        p3 = c
        divby4 = 0x00
        integer_mode = 1 if b == 0 and a % 2 == 0 else 0

    base_reg = 42 + clk_num * 8
    control_reg = 16 + clk_num

    # Upis vrednosti u registre za frekvenciju
    write_register(bus, address, base_reg, (p3 >> 8) & 0xFF)
    write_register(bus, address, base_reg + 1, p3 & 0xFF)
    write_register(bus, address, base_reg + 2, (r_div << 4) | (divby4 << 2) | ((p1 >> 16) & 0x03))
    write_register(bus, address, base_reg + 3, (p1 >> 8) & 0xFF)
    write_register(bus, address, base_reg + 4, p1 & 0xFF)
    write_register(bus, address, base_reg + 5, (((p3 >> 16) & 0x0F) << 4) | ((p2 >> 16) & 0x0F))
    write_register(bus, address, base_reg + 6, (p2 >> 8) & 0xFF)
    write_register(bus, address, base_reg + 7, p2 & 0xFF)

    # Podesavanje kontrolnog registra
    write_register(bus, address, control_reg, (integer_mode << 6) | (0 << 5) | (0 << 4) | (0x3 << 2) | 0x3)

    # Ukljucivanje izlaza
    reg3 = read_register(bus, address, 0x03) & 0xF8
    write_register(bus, address, 0x03, reg3 & ~(1 << clk_num))

    # Reset PLLA
    try:
        write_register(bus, address, 0xB1, 0x20, skip_verify=True)
        time.sleep(0.1)
    except OSError:
        pass

    print(f"CLK{clk_num} postavljen na {freq} Hz.")

# Reset i gasenje svih izlaza
def reset_and_disable_clocks(bus, address):
    print("Resetovanje Si5351A i gasenje svih izlaza...")
    try:
        write_register(bus, address, 0x03, 0xFF)
        for reg in range(16, 24):
            write_register(bus, address, reg, 0x80)
        write_register(bus, address, 0xB1, 0xA0, skip_verify=True)
        time.sleep(0.1)
        write_register(bus, address, 1, 0x00, skip_verify=True)
        print("Reset zavrsen, svi izlazi su iskljuceni.")
    except OSError:
        print("Greska tokom resetovanja. Proveri I2C konekciju.")


# Glavna funkcija
def main():
    parser = argparse.ArgumentParser(description="Si5351A kontrola putem komandne linije")
    subparsers = parser.add_subparsers(dest="command", help="Dostupne komande")

    subparsers.add_parser("init", help="Inicijalizuj Si5351A")
    set_parser = subparsers.add_parser("set", help="Podesi CLK izlaz")
    set_parser.add_argument("clk", type=int, help="Broj izlaza (0-2)")
    set_parser.add_argument("freq", type=int, help="Frekvencija u Hz")

    on_parser = subparsers.add_parser("on", help="Ukljuci CLK izlaz")
    on_parser.add_argument("clk", type=int, help="Broj izlaza (0-2)")

    off_parser = subparsers.add_parser("off", help="Iskljuci CLK izlaz")
    off_parser.add_argument("clk", type=int, help="Broj izlaza (0-2)")

    read_parser = subparsers.add_parser("read", help="Procitaj registar")
    read_parser.add_argument("reg", type=int, help="Broj registra (0-255)")

    subparsers.add_parser("status", help="Prikazi status registra (0x00)")
    subparsers.add_parser("exit", help="Resetuj i iskljuci sve izlaze")

    args = parser.parse_args()

    try:
        bus = smbus.SMBus(I2C_BUS)
        bus.read_byte_data(SI5351A_ADDRESS, 0x00)
    except OSError:
        print("Si5351A nije detektovan. Proveri I2C vezu.")
        sys.exit(1)

    cmd = args.command
    if cmd == "init":
        initialize(bus, SI5351A_ADDRESS)
    elif cmd == "set":
        set_frequency(bus, SI5351A_ADDRESS, args.clk, args.freq)
    elif cmd == "on":
        reg3 = read_register(bus, SI5351A_ADDRESS, 0x03) & 0xF8
        write_register(bus, SI5351A_ADDRESS, 0x03, reg3 & ~(1 << args.clk))
        print(f"CLK{args.clk} ukljucen.")
    elif cmd == "off":
        reg3 = read_register(bus, SI5351A_ADDRESS, 0x03) & 0xF8
        write_register(bus, SI5351A_ADDRESS, 0x03, reg3 | (1 << args.clk))
        print(f"CLK{args.clk} iskljucen.")
    elif cmd == "read":
        val = read_register(bus, SI5351A_ADDRESS, args.reg)
        print(f"Registar 0x{args.reg:02X} = 0x{val:02X}")
    elif cmd == "status":
        val = read_register(bus, SI5351A_ADDRESS, 0x00)
        print(f"Status [0x00] = 0x{val:02X}")
    elif cmd == "exit":
        reset_and_disable_clocks(bus, SI5351A_ADDRESS)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
