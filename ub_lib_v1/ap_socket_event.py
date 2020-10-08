#!/usr/bin/env python
# -*- coding: UTF_8 -*-
from threading import Event
from ub_lib_v1.ap_exception import ap_socket_error, ap_socket_timeout
from ub_lib_v1.ub_class_template import UbClassTemplate, txt_regular_blue

# @copyright  this code is the property of Ubertone. 
# You may use this code for your personal, informational, non-commercial purpose. 
# You may not distribute, transmit, display, reproduce, publish, license, create derivative works from, transfer or sell any information, software, products or services based on this code.
# @author Stéphane Fischer


# on considère 3 niveau d'erreur / exception
# 100 à 199 : erreur critique au niveau de la socket entrainant une deconnexion
#             puis reconnexion au driver
# 200 à 299 : erreur de timeout, la socket est toujours connectée
# 300 à 399 : requête inattendue (set_event : evennement déjà en attente)

## \brief Classe ap_socket_event gère les evenements lié à la réception d'un
# flag par la socket
# seul la fonction wait() est à utiliser

class ap_socket_event (UbClassTemplate):
	def __init__(self, _socket):
		UbClassTemplate.__init__(self)
		self.flag_debug_mess=True
		self.debug_marker_start=txt_regular_blue

		self.sock_event = Event()
		self.socket = _socket

# TODO ? mémoriser le flag associé ?
	def set(self):
		return self.sock_event.set()

	def clear(self):
		return self.sock_event.clear()

	def isSet(self):
		# On utilise le mécanisme de remonter d'exception
		self.socket._catch_exception_from_socket_thread()
		
		if not self.socket.event_is_connected.isSet():
			self.debug("socket_error")
			raise ap_socket_error (308, "ap_socket_event::wait : CONNEXION FAILURE")

		return self.sock_event.isSet()

	def wait(self, _timeout=None):
		self.sock_event.wait(_timeout)
		# théoriquement wait retourne False en cas de timeout, mais ça n'a pas l'air
		# d'être le cas

		# On utilise le mécanisme de remonter d'exception
		self.socket._catch_exception_from_socket_thread()

		if not self.socket.event_is_connected.isSet():
			self.debug("socket_error")
			raise ap_socket_error (309, "ap_socket_event::wait : CONNEXION FAILURE")

		if not self.isSet():
			# si le flag attendu par l'évennement est bien arrivé, le thread de
			# réception le supprime de la liste. Par contre en cas de timeout, 
			# on supprime l'event de la liste
			self.socket.del_event(self)
			self.debug("socket_timeout")
			raise ap_socket_timeout (208, "ap_socket_event::wait : TIMEOUT")

		self.debug("Event ready")

