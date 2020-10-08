#!/usr/bin/env python
# -*- coding: UTF_8 -*-
# @copyright  this code is the property of Ubertone. 
# You may use this code for your personal, informational, non-commercial purpose. 
# You may not distribute, transmit, display, reproduce, publish, license, create derivative works from, transfer or sell any information, software, products or services based on this code.
# @author Stéphane Fischer, Damien Dufour
# code repris de Stream_analyse_v2.1 et apf02_handler_extract

import array
from math import sqrt, floor

from struct import unpack, calcsize, error as struct_error
from datetime import datetime

from ub_lib_v1.ap_exception import ap_protocol_error


def __unpackInt__ (self, _data):
	""" @brief extract an integer from binary
	@param _data binary data received by TCP/IP
	@return the interger that has been extracted from data
	"""
	if len(_data)>=calcsize('i'):
		try:
			return unpack('i',_data)[0]
		except struct_error:
			print("struct error")
			raise ap_protocol_error (122, "unexpected chunk content")


class data_profile_t:
	def __init__(self, _config, _ref=0):
		self.t = 0.
		self.ref = _ref
		
		self.position = array.array('f')
		self.velocity = array.array('f')
		self.amplitude = array.array('f')
		self.variance = array.array('f')
		self.snr = array.array('f')
		self.sat = array.array('f')
		self.ny_jp = array.array('f')
		self.sigma = array.array('f')
		
		self.n_vol_total = _config['n_vol']*_config['n_subvol']
		self.n_ech = _config['n_ech']

		self.I = list()
		self.Q = list()

	# Not used
	def set_position_data(self, _origin=0., _interval_vol=0., _n_vol=0, _interval_subvol=0., _n_subvol=1):
		self.n_vol_total = _n_vol*_n_subvol
		for i in range(_n_vol):
			for j in range(_n_subvol) :
				self.position.append(_origin + _interval_vol*i + _interval_subvol*j)
	
	# données sous forme de donnée brute (binaire = 'string') ou array.
	def set_data_from_binary(self, velocity=[], amplitude=[], facteur_qualite=[]):
		self.velocity = array.array('f',velocity)
		self.variance = array.array('f',amplitude)
		self.amplitude = array.array('f',amplitude)
		facteur_qualite = array.array('i',facteur_qualite)
		#print "lecture tableau taille = %d"%facteur_qualite.buffer_info()[1]
		for i in range(facteur_qualite.buffer_info()[1]):
			if self.variance[i]<0.: # En effet il arrive que la variance soit négative avec l'option de filtrage des écho fixe
				self.variance[i]=float('NaN')
				#print ("WARNING negative variance at cell %d"%i)
			self.amplitude[i] = sqrt(self.variance[i])
			self.snr.append((float(facteur_qualite[i]&0x000000FF)*20.0/255.0) -10.0)		#2013/03/04 Damien : plage SNR : [-10dB +10dB]
			self.sat.append(float((facteur_qualite[i]>>8)&0x000000FF))
			self.ny_jp.append(float((facteur_qualite[i]>>16)&0x000000FF))
			self.sigma.append(float((facteur_qualite[i]>>24)&0x000000FF))
	
	def set_doppler_from_binary(self, IQ_b=[], n_ech=0, n_vol=0):
		self.n_ech = n_ech
		if self.n_vol_total == 0:
			self.n_vol_total = n_vol
		
		IQ = array.array('h', IQ_b)
		for i in range(self.n_vol_total) :
			self.I.append(array.array('f',IQ[(2*i)::(2*self.n_vol_total)]))
			self.Q.append(array.array('f',IQ[(2*i)+1::(2*self.n_vol_total)]))
	
	# \brief Utilise une frame pour récupérer un profil voulu (pour fichier binaires en v2)
	# @param _flag (int) : l'entier permettant de savoir de quel type est la commande
	# @param _size (int) : la taille du bloc
	# @param _data : le bloc de données binaire
	def interpret_chunk (self, data) : 
#		print "reading profile for version UDT002"
		head_size = calcsize('iIIii')
		ref, size_data, size_raw, sec, n_sec =  unpack('iIIii', data[0:head_size])
		#print "sec = %d ; n_sec=%d"%(sec, n_sec)

		if size_data == 0 and size_raw ==0:
			raise ap_protocol_error (120, "empty chunk")
		# ref_config : la référence des settings (numéro unique)
		self.ref = (ref&0xFFFFFF00)>>8
		# num_config : le numéro de la configuration utilisée (1 à 5)
		self.num_config = ref&0x000000FF
		if self.num_config < 1 or self.num_config > 16: #TODO utiliser const pour le max
			raise ap_protocol_error (121, "unexpected number of configurations (%d)"%self.num_config)
			# TODO ? raise IndexError ("configuration not available (%d / %d)"%(_config_meas_id, len(self.settings.config)))
			# ou laisser à l'appelant : oui, plutot ça.
		self.t = sec+n_sec*1e-9
		
		if size_data:
			#print ("size_data = %d"%size_data)
			# floating + integer arrays
			tab_size = int(size_data/3)
			offset = head_size
			velocity_tmp = array.array('f', data[offset : offset+tab_size])
			offset+= tab_size
			variance_tmp = array.array('f', data[offset : offset+tab_size])
			offset+= tab_size
			facteur_qualite = array.array('i', data[offset : offset+tab_size])
			offset+= tab_size
			# extraction des profils :
			self.set_data_from_binary(velocity_tmp, variance_tmp, facteur_qualite)
		#print "taille facteur_qualite %d"%(facteur_qualite.size)

		if size_raw and self.n_ech :
				print ("read doppler data (n_ech = %d)"%(self.n_ech))
				self.set_doppler_from_binary(data[offset:], self.n_ech, self.n_vol_total)
		

