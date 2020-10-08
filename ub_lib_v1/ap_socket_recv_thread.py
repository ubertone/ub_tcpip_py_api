#!/usr/bin/env python
# -*- coding: UTF_8 -*-7
# @copyright  this code is the property of Ubertone. 
# You may not use this code for your personal, informational, non-commercial purpose. 
# You may not distribute, transmit, display, reproduce, publish, license, create derivative works from, transfer or sell any information, software, products or services based on this code.
# @author Stéphane Fischer

import socket
from threading import Thread
from struct import unpack, pack, calcsize
from time import sleep
#from os import strerror
import traceback
import gc

from ub_lib_v1.ap_socket import sendAll, recvAll
from ub_lib_v1.ap_exception import ap_socket_error
from ub_lib_v1.ub_class_template import UbClassTemplate, txt_regular_purple

CMD_TCP_TIMEOUT_SOCKET = 10007
ANS_TCP_TIMEOUT_SOCKET = 20007


class ApSocketRecvTh(Thread, UbClassTemplate):
	def __init__(self, _data_socket, _host, _port):
		UbClassTemplate.__init__(self)

		self.flag_debug_mess=True
		self.debug_marker_start=txt_regular_purple
		Thread.__init__(self)
		self.daemon = True # force l'arrêt du thread en cas d'arret du programme
		self.data_socket = _data_socket
		self.HOST = _host
		self.PORT = int(_port)
		self.debug("initialized")

	## \brief Récupération d'une trame de donnée \n
	# @param _socket (socket) : la socket pour récupérer les données
	# @param _timeout (float) : le timeout qui est de 10.0
	# @return flag (int) : l'entier permettant de savoir de quel type est la commande
	# @return tab_size (int) : la taille des données
	# @return data (struct) : les données
	def __recv_anyframe__(self, _socket):
		sendAll(_socket,pack('i', 1)) # flag keepalive

		# lecture du flag
		flag = unpack('i', recvAll( _socket, calcsize('i')))[0] 
		while flag < 2 and flag !=0:
			flag = unpack('i', recvAll( _socket, calcsize('i')))[0] 
		if flag == 0:
			raise ap_socket_error(30, "__recv_anyframe__ : driver error while reading the socket")
		
		# lecture de la taille du bloc de données
		tab_size = unpack('i', recvAll( _socket, calcsize('i')))[0] 
		
		# lecture du bloc de données
		data = recvAll( _socket,tab_size)
		if len(data)!=tab_size:
			raise ap_socket_error(31, "__recv_anyframe__ : taille de frame erronée (%d/%d)"%(len(data),tab_size))

		return flag, tab_size, data


	def run(self):
		""" @brief Boucle du thread """
		self.debug("run")
		print_connect_failed = 0 # pour le print connexion failed
		sleep_before_reconnect = 1
		while(self.data_socket.is_open): 
			self.data_socket.event_is_connected.clear()
			self.data_socket.event_is_reset.set()
			try:
				########################
				# connexion au serveur #
				########################
				self.debug("lock before connecting")
				self.data_socket.lock()
				try:
					self.debug("create socket")
					self.data_socket.socket_id = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					# TODO attention à surveiller : il arrive, après déconnexion, que la socket semble se
					# reconnecté alors que ce n'est pas le cas !!!
					self.debug("try to connect")

					# TODO ? plutot utiliser connect() qui raise une exception en cas d'echec ? pas sûr.
					connect_err = self.data_socket.socket_id.connect_ex((self.HOST, self.PORT))
					if connect_err != 0:
						self.debug("connexion failed")
						# connexion failed
						if connect_err != print_connect_failed: # print lors du premier passage
							self.info("connexion to %s:%d failed (with error %d), try undefinitely"%(self.HOST, self.PORT, connect_err))
							print_connect_failed = connect_err

						sleep_before_reconnect *=2 #on augmente progressivement le délai
						if sleep_before_reconnect > 30: # le temps de déconnexion par défaut du driver est de 20 secondes
							sleep_before_reconnect = 30
						sleep (sleep_before_reconnect) # on attends un peu avant d'essayer de se reconnecter
						continue
					self.info("connected to the driver (%s:%d)"%(self.HOST,self.PORT))
					print_connect_failed = 0

					self.data_socket.socket_id.settimeout(None) # on force le mode bloquant (bien que ce soit a priori le mode par défaut)

					# at startup, reset the timeout on server side : TODO ? intégrer dans le protocole ?
					sendAll(self.data_socket.socket_id,pack('i', CMD_TCP_TIMEOUT_SOCKET)+pack('i', 4)+pack("i",int(self.data_socket.timeout+2)))
					# le retour est récupéré plus loin dans la boucle de réception.

					self.data_socket.event_is_connected.set()
					self.data_socket.event_is_reset.clear()
				
				finally:
					self.data_socket.unlock()

				##################################
				# Boucle de réception des trames #
				##################################
				while(1):
					# ici on n'a pas besoin de mettre un critère d'interruption de la boucle 
					# car on va principalement être en attente bloquante dans __recv_anyframe__
					# et ce dernier va générer une exception si la socket est coupée
					
					# pour test :
#					if self.data_socket.test_system_exception :
#						raise SystemExit

					# on attend une requête attendant une réponse
					flag, tab_size, data = self.__recv_anyframe__(self.data_socket.socket_id) 
									# on met en bloquant avec attente infinie ? que se passe
									# t'il dans ce cas si on veut killer le thread ?
					self.debug("on recoit flag %d (size = %d)"%(flag, tab_size))
					# ATTENTION, le retour ANS_TCP_TIMEOUT_SOCKET de la commande faite plus 
					#    haut n'est pas traitée, mais ce n'est pas indispensable, mieux vaut
					#    garder un code simple
					self.data_socket.push_recv_buffer(flag, tab_size, data) # intègre le lock
					
			##########################
			# gestion des exceptions #
			##########################
			# On ne remonte aucune exception par "raise" car on est dans un thread (il n'y a personne au dessus pour la rattraper)
			# On utilise donc le mécanisme de transfert via self.data_socket.system_exception
			except OSError as serr:
				self.data_socket.system_exception = ap_socket_error(serr.errno, serr.strerror)
				self.info ("%d : %s"%(serr.errno, serr.strerror))

			except ap_socket_error as sexcept:
				if sexcept.code == 21 :
					self.info("socket closed by driver (probably due to inactivity)")
					self.data_socket.system_exception = None # pas d'exception, c'est une situation normale
					self.data_socket.is_open = False # on force la cloture de la data_socket (pour ne pas garder la main sur le driver)
				else:
					self.info("ap_socket_error \"%s\"-> reset"%sexcept.message)
					# on transmet l'erreur à la prochaine fonction externe qui tente un acces à la socket :
					self.data_socket.system_exception = sexcept

			except: # jamais vu pour l'instant
				self.data_socket.system_exception = ap_socket_error(132, "socket_recv_th : unexpected exception while receiving frame")
				self.info("WARNING unexpected exception while receiving frame")
				print (traceback.format_exc())

			# si on n'arrive là c'est qu'il y a eu une exception pour nous faire sortir de la boucle while(1)
			try:
				self.data_socket.lock()
				try:
					self.data_socket.private_reset() # inclu un event_is_connected.clear()
					# si il y a eu une exception et que la data_socket n'est pas active, on force la déconnexion (pour ne pas garder la main sur le driver)
					if self.data_socket.system_exception and not self.data_socket._is_active() :
						self.info("closing because of exception while socket is inactive")
						self.data_socket.is_open = False
				finally:
					self.data_socket.unlock()
			except:
				self.info("WARNING unexpected exception")
				print (traceback.format_exc())

			if self.data_socket.is_open:
				self.info("try to reconnect")
				continue
			else: # la socket est cloturée
				self.info("data_socket has been closed")
				break
		
		# on force le Garbage Collector a libérer la memoire non référencée
		# car d'expérience on a beaucoup d'intervention du OOM consécutif à l'arret de ce thread
		# c'est très "cuisine", mais bon ...
		gc.collect() 

