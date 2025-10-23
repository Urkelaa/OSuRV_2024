import smbus
import time
import math

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
        print("Nevaseci CLK broj (0–2).")
        return
    if freq < 2500 or freq > 200000000:
        print("Frekvencija van opsega (2.5 kHz – 200 MHz).")
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

# Komandna linija za korisnika
def user_command_loop(bus, address):
    print("\n=== Clock Gen Click CLI ===")
    print("Komande:")
    print(" init                 - Inicijalizuj Si5351A")
    print(" set <clk> <freq>     - Podesi CLK0–CLK2 na zeljenu frekvenciju (npr. set 0 1000000)")
    print(" on <clk>             - Ukljuci izlaz (CLK0–2)")
    print(" off <clk>            - Iskljuci izlaz (CLK0–2)")
    print(" read <reg>           - Procitaj registar (npr. read 0)")
    print(" status               - Prikazi status registra (0x00)")
    print(" exit                 - Resetuj i izadji iz programa\n")

    while True:
        cmd = input(">> ").strip().lower().split()
        if not cmd:
            continue

        if cmd[0] == "exit":
            print("Izlaz iz programa i resetovanje uredjaja...")
            reset_and_disable_clocks(bus, address)
            break

        elif cmd[0] == "init":
            try:
                if initialize(bus, address):
                    print("Inicijalizacija zavrsena uspesno.")
                else:
                    print("Inicijalizacija neuspesna.")
            except OSError:
                print("Greska pri inicijalizaciji (I2C).")

        elif cmd[0] == "set" and len(cmd) == 3:
            try:
                clk = int(cmd[1])
                freq = int(cmd[2])
                set_frequency(bus, address, clk, freq)
            except ValueError:
                print("Upotreba: set <clk 0-2> <frekvencija u Hz>")
            except OSError:
                print("Greska pri podešavanju frekvencije (I2C).")

        elif cmd[0] == "on" and len(cmd) == 2:
            try:
                clk = int(cmd[1])
                if 0 <= clk <= 2:
                    reg3 = read_register(bus, address, 0x03) & 0xF8
                    write_register(bus, address, 0x03, reg3 & ~(1 << clk))
                    print(f"CLK{clk} ukljucen.")
                else:
                    print("CLK broj mora biti 0, 1 ili 2.")
            except ValueError:
                print("Nevazeci CLK broj.")
            except OSError:
                print("Greska pri ukljucivanju izlaza (I2C).")

        elif cmd[0] == "off" and len(cmd) == 2:
            try:
                clk = int(cmd[1])
                if 0 <= clk <= 2:
                    reg3 = read_register(bus, address, 0x03) & 0xF8
                    write_register(bus, address, 0x03, reg3 | (1 << clk))
                    print(f"CLK{clk} iskljucen.")
                else:
                    print("CLK broj mora biti 0, 1 ili 2.")
            except ValueError:
                print("Nevazeci CLK broj.")
            except OSError:
                print("Greska pri iskljucivanju izlaza (I2C).")

        elif cmd[0] == "read" and len(cmd) == 2:
            try:
                reg = int(cmd[1])
                if 0 <= reg <= 255:
                    value = read_register(bus, address, reg)
                    print(f"Registar 0x{reg:02X} = 0x{value:02X}")
                else:
                    print("Registar mora biti izmedju 0 i 255.")
            except ValueError:
                print("Nevazeci broj registra.")
            except OSError:
                print("Greska pri citanju registra (I2C).")

        elif cmd[0] == "status":
            try:
                value = read_register(bus, address, 0x00)
                print(f"Status [0x00] = 0x{value:02X}")
            except OSError:
                print("Greska pri citanju statusa (I2C).")

        else:
            print("Nepoznata komanda.")

# Glavna funkcija
def main():
    try:
        bus = smbus.SMBus(I2C_BUS)
        bus.read_byte_data(SI5351A_ADDRESS, 0x00)
        print("Si5351A detektovan na adresi 0x60.")
        user_command_loop(bus, SI5351A_ADDRESS)
    except OSError:
        print("Si5351A nije detektovan. Proveri I2C vezu.")

if __name__ == "__main__":
    main()
