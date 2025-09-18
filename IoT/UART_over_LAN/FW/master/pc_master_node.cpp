


#include <libserial/SerialPort.h>



void init() {



	LibSerial::SerialPort motor_ctrl_sensor_hub_serial;


	string usb_port = "/dev/ttyUSB0"

	try{
		motor_ctrl_sensor_hub_serial.Open(usb_port);
		motor_ctrl_sensor_hub_serial.SetBaudRate(LibSerial::BaudRate::BAUD_115200);
		motor_ctrl_sensor_hub_serial.SetStopBits(LibSerial::StopBits::STOP_BITS_1);
	}catch(...){
		RCLCPP_ERROR_STREAM(
			this->get_logger(),
			"Cannot open Sabertooth at \"" << usb_port << "\"!"
		);
		RCLCPP_INFO_STREAM(
			this->get_logger(),
			"Proceeding in powerless mode"
		);
	}

}


void write_pkg() {
	pkg_m2s_t& p = *reinterpret_cast<pkg_m2s_t*>(wr_buf.data());
	p.magic = PKG_MAGIC;
	p.payload.speed[0] = speed[0];
	p.payload.speed[1] = speed[1];
	p.payload.ramp_rate_ms = 2000; // TODO
	p.crc = CRC16().add(p.payload).get_crc();

	if(motor_ctrl_sensor_hub_serial.IsOpen()){
		motor_ctrl_sensor_hub_serial.Write(
			wr_buf
		);
	}
}


void FW_Node::read_pkg() {

	if(!motor_ctrl_sensor_hub_serial.IsOpen()){
		return;
	}
	
	for(u8 i = 0; i < sizeof(pkg_magic_t); i++){
		try{
			motor_ctrl_sensor_hub_serial.Read(
				rd_buf,
				1,
				1 // [ms]
			);
		}catch(LibSerial::ReadTimeout& e){
			// Timeout.
			return;
		}

		reinterpret_cast<u8*>(&obs_magic)[i] = rd_buf[0];

		if(
			reinterpret_cast<u8*>(&exp_magic)[i] !=
			reinterpret_cast<u8*>(&obs_magic)[i]
		){
			// Lost magic.
			return;
		}
	}

	try{
		motor_ctrl_sensor_hub_serial.Read(
			rd_buf,
			sizeof(pkg_s2m_t)-sizeof(pkg_magic_t),
			// Until all bytes are received.
			10*sizeof(pkg_s2m_t)*1000/9600*2+5 // [ms]
		);
	}catch(LibSerial::ReadTimeout& e){
		RCLCPP_WARN(this->get_logger(), "Cannot read sensor pkg!");
		return;
	}

	
	pkg_s2m_t p;
	p.magic = obs_magic;

	copy(
		rd_buf.begin(),
		rd_buf.end(),
		reinterpret_cast<uint8_t*>(&p) + sizeof(pkg_magic_t)
	);


	pkg_crc_t obs_crc = CRC16().add(p.payload).get_crc();
	if(obs_crc != p.crc){
		RCLCPP_WARN(this->get_logger(), "Wrong CRC!");
		DEBUG(obs_crc);
		DEBUG(p.crc);
		return;
	}


}
