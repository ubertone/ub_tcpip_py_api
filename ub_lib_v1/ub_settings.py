# -*- coding: UTF_8 -*-

from ub_lib_v1.minidom_xml_RO import minidom_wrapper_ro as ub_xml

def read_settings (_path):
	# read the file in a string
	with open(_path, "r") as settings_file:
		settings_str = settings_file.read()
	
	# parse the xml file
	xml = ub_xml()
	xml.parse_file(_path)

	# create a dict with the settings parameters
	settings = {}

	settings['sound_speed'] = xml.get_data("float","body/sound_speed")

	# loop on acoustic configurations
	for i, ixml in enumerate (xml.get_elem("body/sequence/config")):
		config = {}
		config_xml = ub_xml(ixml)
		
		config['prf'] = config_xml.get_data("float","prf")
		config['n_ech'] = config_xml.get_data("int","n_ech")
		config['n_profile'] = config_xml.get_data("int","n_profile")
		config['n_vol'] = config_xml.get_data("int","n_vol")
		config['n_subvol'] = config_xml.get_data("int","n_subvol")

		settings['config%d'%(i+1)] = config

	settings['d0'] = xml.get_data("float","body/geometry/d0")
	settings['gamma'] = xml.get_data("float","body/geometry/gamma")

	return settings, settings_str