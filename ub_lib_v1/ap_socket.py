# -*- coding: UTF_8 -*-

# @copyright  this code is the property of Ubertone. 
# You may use this code for your personal, informational, non-commercial purpose. 
# You may not distribute, transmit, display, reproduce, publish, license, create derivative works from, transfer or sell any information, software, products or services based on this code.
# @author Stéphane Fischer
# il s'agit simplement d'un surcouche aux sockets de base de l'OS permettant 
# d'envoyer et recevoir des blocs de taille prédéfinie.
# Les sockets sont bloquantes par défaut sous python. 
# C'est la couche ap_data_socket qui gère les timeout
# Notes : au besoin, utiliser socket.setblocking(0) pour les rendre non bloquantes
# ou utiliser settimeout() sur une socket bloquante

import socket
import traceback
#from os import strerror
#from errno import EAGAIN

from ub_lib_v1.ap_exception import ap_socket_error

# nombre de tentative en cas d'envoi ou de réception de blocs incomplets
limitation_reception_parts = 100


# TODO on pourrait simplement utiliser le sendall de python
def sendAll(_socket, _data):
	"""
	@brief Envoie l'intégralité d'un bloc de données par TCP/IP
	@param _data 
	
	s'y reprend à plusieurs fois si besoin
	"""
	try:
		total = _socket.send(_data)
		if total != len(_data):
			if total==0:
				print ("sendAll : return with no data sent TODO should raise an exception ?")
			print ("sendAll : some data have not been send (", total, "/", len(_data), ")")
			while (total<len(_data)):
				n = _socket.send(_data[total:len(_data)-1])
				total += n

	except OSError as serr:
#		if code == 32:  # Broken pipe
#			print ("DataThread : Lost connection to driver, try to reconnect")
#		elif code == 54:  # Connection reset by peer
#			print ("DataThread : Driver disconnect, try to reconnect")
#		elif code == 64:  # Host is down
#			print ("DataThread : Host is down, try to reconnect")
#		elif code == 111: # Connection refused
#			print ("DataThread : connection refused wait before try again, try to reconnect")
#		elif code == 106: #Transport endpoint is already connected
#			print ("DataThread : Transport endpoint is already connected, try to reconnect")
#		else:
#			print ("DataThread : Erreur non prevue :")
#			print code, msg
		raise ap_socket_error(10, "sendAll : socket error [%d] %s"%(serr.errno, serr.strerror))
	except IOError as inst:
		print ("sendAll : IOerror"), type(inst), inst
		raise ap_socket_error(11, "sendAll : IO error")
	except MemoryError as inst:
		print ("sendAll : MemoryError"), type(inst), inst
		raise ap_socket_error(12, "sendAll : Memory error")
	except: # on gère ici toutes les autres erreurs
		print ("sendAll : WARNING unexpected error -> email to stephane.fischer@ubertone.fr")
		print (traceback.format_exc())
		raise ap_socket_error(13, "sendAll : WARNING unexpected error -> email to stephane.fischer@ubertone.fr")
	return total


def recvAll(_socket, _size):
	"""
	@brief Permet de recevoir une quantité prédéterminée de données sur une socket TCP/IP
	@param _socket (socket) : la socket où récupérer les données
	@param _size (int) la taille des données à recevoir
	@return alldata : les données reçues (type différent en fonction de la commande)
	
	s'y reprend à plusieurs fois si besoin
	"""
	numbyte=0
	offset=0
	alldata=b''
	
	rest = _size
	i = 0
	try:
		while(rest):
			if offset > _size:
				raise ap_socket_error(20, "recvAll : negative buffer size")
			data = _socket.recv(rest)
			alldata += data
			numbyte = len(data)
			if not numbyte:
				raise ap_socket_error(21, "recvAll : recv return no data (%d/%d): connexion broken by peer"%(numbyte,rest)) # lorsque le serveur coupe la liaison, recv retourne 0
			offset += numbyte
			# même avec un timeout, plusieurs requêtes sont parfois nécessaire
			rest = _size - offset
			i+=1 #ce compteur permet d'envoyer une Excpetion en cas de temps d'attente trop long
			if i>limitation_reception_parts:
				raise ap_socket_error(22, "recvAll : recv in more than "+str(limitation_reception_parts)+" parts (reste "+ str(rest) +"/" + str(_size) +")")

	except OSError as serr:
		# socket.erreur déja constaté :
#	32: Broken pipe
#	54: Connection reset by peer
#	60: Operation timed out
#	64: Host is down
#	104: Connection reset by peer
#	106: Transport endpoint is already connected
#	111: Connection refused

		raise ap_socket_error(23, "recvAll : socket error [%d] %s"%(serr.errno, serr.strerror))
	except IOError as inst:
		print ("recvAll IOerror (not socket.error)"), type(inst), inst
		raise ap_socket_error(24, "recvAll : IO error")
	except MemoryError as inst:
		print ("recvAll MemoryError (not socket.error)"), type(inst), inst
		raise ap_socket_error(25, "recvAll : Memory error")
	except ap_socket_error : # on laisse passer
		raise
	except: # on gère ici toutes les autres erreurs
		# OverflowError: long int too large to convert to int
		print ("recvAll : WARNING unexpected error -> email to stephane.fischer@ubertone.fr")
		print (traceback.format_exc())
		raise ap_socket_error(26, "recvAll : WARNING unexpected error -> email to stephane.fischer@ubertone.fr")
	return alldata

