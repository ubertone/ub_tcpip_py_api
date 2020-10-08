# -*- coding: UTF_8 -*-
import unittest

# Add project path for accessing to the lib
import sys, os
project_name="/ub_tcpip_py_api"
webui_path = os.path.abspath(__file__).split(project_name)[0]+project_name
sys.path.insert(0, webui_path)
#-------------------------------------

from struct import pack, unpack, calcsize, error as struct_error

# import modules
from ub_lib_v1.ap_data_socket import ApDataSocket
from ub_lib_v1.apf02_frame_flags import *
from ub_lib_v1.ub_settings import read_settings
from ub_lib_v1.ub_profile import data_profile_t
from ub_lib_v1.ap_exception import ap_protocol_error

def unpackInt (_data):
	""" @brief extract an integer from binary
	@param _data binary data received by TCP/IP
	@return the interger that has been extracted from data
	"""
	if len(_data)>=calcsize('i'):
		try:
			return unpack('i',_data)[0]
		except struct_error:
			print ("struct error")
			raise ap_protocol_error (122, "unexpected chunk content")


# The main test class
class TestTcpIpDriver(unittest.TestCase):

	def test_01_connexion(self):
		# Create an instance of the socket with the driver
		socket = ApDataSocket('192.168.88.1', 3490)
		default_timeout = 10
		socket.wait_connexion()

		# Read driver version
		_, _, data = socket.send_recv_frame(CMD_TCP_DRIVER_VERSION, b'', ANS_TCP_DRIVER_VERSION, default_timeout)
		print ("Driver version : %s" %(str(data)))

		socket.close()
		

	def test_02_average_meas(self):
		# Create an instance of the socket with the driver
		socket = ApDataSocket('192.168.88.1', 3490)
		default_timeout = 3
		socket.wait_connexion()

		# Power on the electronic Front End
		socket.send_recv_frame(CMD_TCP_FRONT_ON, b'', ANS_TCP_FRONT_ON, default_timeout)

		#load settings 
		settings, settings_str = read_settings("./settings_models/settings.ublab_2c.xml")

		flag, size, data = socket.send_recv_frame(CMD_TCP_CONFIG, settings_str.encode('UTF8'), ANS_TCP_CONFIG, default_timeout)
		if len(data):
			print("the following settings have been applied : \n %s"%(data))
		else:
			print("CMD_TCP_CONFIG failed")
		
		# measurement of one block with first config
		  # create event associated with block end flag reception :
		event_bloc_end_received = socket.set_event(ANS_TCP_BLOC)
		  # select configuration to run :
		current_config_key = 1
		config = settings['config%d'%current_config_key]
		block_duration = config['n_profile']*config['n_ech']/config['prf']

		  # start acquisition :
		socket.send_frame(CMD_TCP_BLOC, pack('i', current_config_key))
		  # set timeout (depending on the parameters: PRF, n_ech, n_profile) extended by 10% + 1 sec
		timeout = block_duration * 1.1 + 1. # in seconds
		  # wait for block end :
		event_bloc_end_received.wait(timeout)
		  # read block end chunck
		flag, size, data = socket.read_frame(ANS_TCP_BLOC)
		ret = unpackInt(data)
		if ret==1: 
			print("Block stopped by the application (with CMD_TCP_STOP) or data overflow (you should adjust settings to reduce the flow of data)")
		if ret==2:
			print("WARNING Configuration number is out of range !")

		  # read average profile
		flag, size, data = socket.send_recv_frame(CMD_TCP_PROFILE_AAVG, b'', ANS_TCP_PROFILE_AAVG, default_timeout)

		# TODO attention, pour extrire les profils, il faut connaitre n_vol et n_subvol (et _n_ech pour le IQ)
		acoustic_profile = data_profile_t(config)

		acoustic_profile.interpret_chunk(data)

		print (acoustic_profile.amplitude)

		socket.close()



# We need this to be able to run the tests outside a test framework.
if __name__ == '__main__':
	unittest.main()
