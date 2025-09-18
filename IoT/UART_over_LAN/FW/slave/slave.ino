
///////////////////////////////////////////////////////////////////////////////

#define SW_UART_TX 2
#define SW_UART_RX 3

///////////////////////////////////////////////////////////////////////////////

#include "SoftwareSerial2.h"

#include "avr_io_bitfields.h"

#include "fw_pkgs.hpp"

///////////////////////////////////////////////////////////////////////////////

SoftwareSerial sw_ser(SW_UART_RX, SW_UART_TX);

auto& hw_ser = Serial;

#define DEBUG(x) \
	do{ \
		hw_ser.print(#x" = "); hw_ser.println(x); \
	}while(0)
#define DEBUG_HEX(x) \
	do{ \
		hw_ser.print(#x" = 0x"); hw_ser.println(x, HEX); \
	}while(0)
#define DEBUG_BYTES(x) \
	do{ \
		hw_ser.print("0x"); \
		for(size_t i = 0; i < sizeof(x); i++){ \
			u8 b = reinterpret_cast<const u8*>(&x)[i]; \
			u8 nl = b & 0xf; \
			u8 nu = b >> 4; \
			hw_ser.print(int(nu), HEX); \
			hw_ser.print(int(nl), HEX); \
		} \
		hw_ser.println(); \
	}while(0)

///////////////////////////////////////////////////////////////////////////////


///////////////////////////////////////////////////////////////////////////////

void setup() {
	
	sw_ser.begin(115200);
	
	hw_ser.begin(115200);


	DEBUG(sizeof(pkg_m2s_t));
	DEBUG(sizeof(pkg_s2m_t));
}

///////////////////////////////////////////////////////////////////////////////

void poll_pkg() {
	watchdog_apply();

	if(sw_ser.available() < 1){
		return;
	}

	int len;

	pkg_magic_t exp_magic = PKG_MAGIC;
	pkg_magic_t obs_magic = 0;
	
	for(u8 i = 0; i < sizeof(pkg_magic_t); i++){
		u8 b;
		len = sw_ser.readBytes(
			&b,
			1
		);
		if(len != 1){
			hw_ser.println("ERROR: Lost start of pkg!");
			return;
		}

		reinterpret_cast<u8*>(&obs_magic)[i] = b;

		if(
			reinterpret_cast<u8*>(&exp_magic)[i] !=
			reinterpret_cast<u8*>(&obs_magic)[i]
		){
			// Lost magic.
			//hw_ser.println("ERROR: Lost magic!");
			return;
		}
	}

	pkg_m2s_t p;
	p.magic = obs_magic;

	len = sw_ser.readBytes(
		reinterpret_cast<u8*>(&p) + sizeof(pkg_magic_t),
		sizeof(p) - sizeof(pkg_magic_t)
	);
	
	pkg_crc_t obs_crc = CRC16().add(p.header).add(p.payload).get_crc();
	if(obs_crc != p.crc){
		hw_ser.println("ERROR: Wrong CRC!");
		return;
	}

	set_servo_angle(
		p.payload.servo_angle
	);
}




void send_pkg() {
	pkg_s2m_t p;
	p.magic = PKG_MAGIC;

	p.payload.status = 1; // Ok

	p.crc = CRC16().add(p.header).add(p.payload).get_crc();

	sw_ser.write(
		reinterpret_cast<u8*>(&p),
		sizeof(p)
	);
}


typedef unsigned long ms_t;

void loop() {
	poll_pkg();

	// Send slower than reading.
	static ms_t t_prev;
	ms_t t_curr = millis();
	if((t_curr - t_prev) > 1000/SENSOR_HZ) {
		t_prev = t_curr;
		send_pkg();
	}
	
}
