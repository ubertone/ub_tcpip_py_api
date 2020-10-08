#!/usr/bin/env python
# -*- coding: UTF_8 -*-
# @copyright  this code is the property of Ubertone. 
# You may use this code for your personal, informational, non-commercial purpose. 
# You may not distribute, transmit, display, reproduce, publish, license, create derivative works from, transfer or sell any information, software, products or services based on this code.
# @author Stéphane Fischer

# on considère 3 niveau d'erreur / exception
#   1 à  99 : erreur dans ap_socket
# 100 à 199 : erreur critique au niveau de la socket entrainant une deconnexion
#             puis reconnexion au driver
# 200 à 299 : timeout, la socket est toujours connectée
# 300 à 399 : requête inattendue de la fonction appelante (set_event : evennement déjà en attente)
# 400 à 499 : assert
# Attention à éviter les doublons
# TODO ATTENTION pour le moment cette classification n'est pas tout à fait respectée ...

# liste actuelle des ap_socket_error :
# 10, "sendAll : socket error [%d] %s"%(code, msg))
# 11, "sendAll : IO error")
# 12, "sendAll : Memory error")
# 13, "sendAll : WARNING unexpected error -> email to stephane.fischer@ubertone.fr")
# 20, "recvAll : negative buffer size")
# 21, "recvAll : recv return no data (%d/%d): connexion broken by peer"%(numbyte,rest)) # lorsque le serveur coupe la liaison, recv retourne 0
# 22, "recvAll : recv in more than "+str(limitation_reception_parts)+" parts (reste "+ str(rest) +"/" + str(_size) +")")
# 23, "recvAll : socket error [%d] %s"%(code, msg))
# 24, "recvAll : IO error")
# 25, "recvAll : Memory error")
# 26, "recvAll : WARNING unexpected error -> email to stephane.fischer@ubertone.fr")
# 30, "__recv_anyframe__ : driver error while reading the socket")
# 31, "__recv_anyframe__ : taille de frame erronée (",len(data),"/",tab_size,")")
# 118, "ap_data_socket::send_frame : sendAll fail, socket reconnect")
# 119, "ap_data_socket::send_recv_frame : sendAll fail, socket reconnect")
# 308, "ap_socket_event::wait : CONNEXION FAILURE")
# 309, "ap_socket_event::wait : CONNEXION FAILURE")

# liste actuelle des ap_socket_timeout :
# 208, "ap_socket_event::wait : TIMEOUT"

# liste actuelle des ap_socket_exception :
# 303, "data_socket_c: flag %d not found in recv_buffer"%(_flag))
# 312, "data_socket_c::open : socket already open")
# 314, "data_socket_c::recv_frame : socket is not connected")
# 315, "data_socket_c::set_event : socket is not connected")
# 316, "data_socket_c::send_frame : socket is not connected")
# 317, "data_socket_c::send_recv_frame : flag %d already received"%(_flag_recv))
# 318, "data_socket_c::send_recv_frame : socket is not connected")
# 319, "data_socket_c::set_connexion_timeout : socket is not connected")
# 320, "data_socket_c: flag %d twice !" % _flag)
# 322, "data_socket_c::__pop_frame : recv_buffer empty")
# 401, "BUG WARNING data_socket_c::open : socket connected")

from copy import deepcopy

## \brief Classe ap_base_socket_exception (BaseException) qui gère les exceptions spéciales.
class ap_base_exception (Exception):
	def __init__(self, _code, _message):
		self.code = _code
		self.message = _message

	def __copy__(self):
		print ("__copy__()")
		return self.__class__(self.code, self.message)

	def __deepcopy__(self, memo):
		print ("__deepcopy__(%s)"% str(memo))
		return self.__class__(deepcopy(self.code, memo), deepcopy(self.message, memo))

	def __str__(self):
		return "%s %d : %s"%(self.__class__.__name__, self.code, self.message)

## \brief Classe ap_socket_error qui gère les erreurs de
#connexion.
class ap_socket_error (ap_base_exception):
	pass

## \brief Classe ap_socket_timeout qui gère les timeout.
class ap_socket_timeout (ap_base_exception):
	def __str__(self):
		return "socket_timeout %d : %s"%(self.code, self.message)

## \brief Classe ap_socket_exception qui gère les exception non critique
class ap_socket_exception (ap_base_exception):
	def __str__(self):
		return "socket_exception %d : %s"%(self.code, self.message)

## \brief Classe ap_protocol_error qui gère les erreurs de protocole
# ex. on demande a modifier les settings alors qu'un bloc est en cours pour une requete d'enregistrement...
class ap_protocol_error (ap_base_exception):
	def __str__(self):
		return "ap_protocol_error %d : %s"%(self.code, self.message)

