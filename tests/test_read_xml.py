# -*- coding: UTF_8 -*-
import unittest

# Add project path for accessing to the lib
import sys, os
project_name="/ub_tcpip_py_api"
webui_path = os.path.abspath(__file__).split(project_name)[0]+project_name
sys.path.insert(0, webui_path)
#-------------------------------------

from ub_lib_v1.ub_settings import read_settings

# The main test class
class TestXML(unittest.TestCase):
	def test_01_open (self):
		settings, _ = read_settings("./settings_models/settings.ublab_2c.xml")

		print (settings)


# We need this to be able to run the tests outside a test framework.
if __name__ == '__main__':
	unittest.main()
