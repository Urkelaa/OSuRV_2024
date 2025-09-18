
#pragma once

#include "type_shorts.h"
#include "CRC16.hpp"

#define PKG_MAGIC 0xdeda



typedef u16 pkg_magic_t;
typedef u16 pkg_crc_t;

#define struct_packed struct __attribute__((packed))

struct_packed header_t {
	u8 src : 4;
	u8 dst : 4;
};

struct_packed pkg_m2s_t {
	pkg_magic_t magic;
	header_t header;
	struct_packed {
		i16 servo_angle;
	} payload;
	pkg_crc_t crc;
};

struct_packed pkg_s2m_t {
	pkg_magic_t magic;
	header_t header;
	struct_packed {
		u8 status;
	} payload;
	pkg_crc_t crc;
};

