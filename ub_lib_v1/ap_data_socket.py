#!/usr/bin/env python
# -*- coding: UTF_8 -*-7

# @copyright  this code is the property of Ubertone. 
# You may use this code for your personal, informational, non-commercial purpose. 
# You may not distribute, transmit, display, reproduce, publish, license, create derivative works from, transfer or sell any information, software, products or services based on this code.
# @author Stéphane Fischer

## @package ap_data_socket
#\brief Classe gérant une connexion TCP en mode multi-thread
#
# le programme appelant peut utiliser les fonction suivantes 
# - ap_data_socket ( HOST, PORT ) le constructeur de la classe
# - open ()
# - close ()
# - wait_connexion ()
# - set_connexion_timeout () : defini le timeout
# - test ()
# - send_frame ()
# - recv_frame ()
# - set_event ()
# - read_frame ()
# - send_recv_frame ()
# - clear_buffer ()


# GESTION DES EXCEPTIONS SYSTEME
# les exceptions système KeyboardInterrupt et SystemExit attrapées par le thread
# ap_socket_recv_th sont remontées dans tous les thread utilisant la data_socket
# via :
# - l'attente (wait) sur un evenement ap_socket_event (reçu par la fonction
# set_event)
# - l'appel aux fonctions open, close, wait_connexion, test, send_frame, set_event,
# recv_frame, send_recv_frame, read_frame, clear_buffer. 
#
# Si la socket n'est pas utiliée il faut la fermer par un close.
# Le driver est aussi susceptible de cloturer la socket en cas d'inactivité.
# Ainsi il est important, en cas d'exception, que l'appelant teste si is_open
# et au besoin refasse un open()
# ATTENTION, si la socket reste ouvert sans être utilisée, il est indispensable :
# - d'avoir au moins un évenement en attente (même un fake) pour pouvoir attrapper 
# toute erreur du thread de réception (i.e. un déconnexion)
# - ou utiliser la fonction test
# la fonction private_reset ne doit pas etre appelée par l'utilisateur, plutot
# faire un close(), puis open() si besoin

# TODO ? gérer avec un flag interne AP_DS_SYS_EXCEPT remonté via event ? à priori on abandonne cette idée,
#        la transmission des exception via _catch_exception_from_socket_thread fonctionne bien.

# en cas de deconnexion ou timeout on remonte une execption pour que
# l'appelent puisse attendre la reconnexion (automatique)
#
# TODO ? changer wait_buffer en event_list? waiting_list? et intégrer le flag dans les ap_socket_event ?

# Flag interne à data socket (entre 0 et 99)
# 0 : signal à l'interlocuteur la cloture de la socket
# 1 : vérifie que la connexion est toujours active (keepalive) 
# TODO ? ajouter ici le connexion_timeout ? en effet la gestion du timeout 
#        devrait etre une partie intégrante du protocole datasocket
# TODO ? ajouter les flags internes pour les messages (prendre >9) :
# TAG_CONNEXION_RESET : un event sur ce tag permet de savoir si il y a eu une
# déconnexion (trame virtuelle, non transmise mais remonter vers l'utilisateur
# de la lib)
# TAG_DEBUG
# TAG_INFO
# TAG_WARNING
# TAG_ERROR
# TAG_CRITICAL
# TAG_SYS_EXCEPTION : remonter en cas d'exception systeme ?

#concernant la gestion des déconnexions de la data_socket :
#dans l'état actuel des choses, quoi qu'on fasse on ne peut pas être certain qu'il n'y a pas eu de déconnexion juste avant une demande de mesure. 
#
#Pour contourner le problème (qui je pense ne peux pas être traiter simplement dans le module ap_data_socket) je propose de :
#- ne pas réinitialiser le driver en cas de déconnexion (mais uniquement à la réception d'un nouveau settings). Ainsi après une déconnexion, le client peut toujours demander un profil.
#- modifier les requètes de demande de mesure de profils en ajoutant la ref du settings en plus du numéro de config. Ainsi si le driver reçoit une requète qui ne correspond pas a ce qu'il a en mémoire (i.e. changé par un autre client durant la déconnexion), le driver retourne une erreur.
#
#L'avantage ici c'est que la couche datasocket est vraiment indépendante des commandes. Elle se contente de fournir une bonne réactivité des échanges et de garantir que la connexion est toujours établie.
#
#Reste à gérer l'enregistrement des données brutes en cours. En temps normal, si le client souhaite un enregistrement il doit faire en sorte d'ajuster le timeout de la connexion (pour éviter toute déconnexion automatique de la part du driver). Par ailleurs en cas de déconnexion accidentelle, la couche de data_socket se reconnecte de manière assez réactive. Je propose donc qu'a la connexion au driver d'un nouveau client, le driver vérifie si il y a un enregistrement en cours, si c'est le cas il observe le temps écoulé depuis la déconnexion, si il est supérieur à 10 secondes (valeur à fixer) : on arrête l'enregistrement et on envoie une trame d'erreur (flag + code + message à déterminer). 
#


from threading import Event, RLock
from time import localtime, mktime
from copy import deepcopy
from struct import calcsize, pack

from ub_lib_v1.ap_socket_recv_thread import ApSocketRecvTh
from ub_lib_v1.ap_socket import sendAll
from ub_lib_v1.ap_exception import ap_socket_exception, ap_socket_error
from ub_lib_v1.ap_socket_event import ap_socket_event
from ub_lib_v1.ub_class_template import UbClassTemplate, txt_regular_blue
import traceback

# vérifie la taille des entiers gérée par le protocole 
if (calcsize('i') != 4):
	print ("WARNING : calcsize i != 4")
	exit

AP_DATA_SOCKET_SELECTIVE = 1
AP_DATA_SOCKET_NON_SELECTIVE = 2

CMD_TCP_TIMEOUT_SOCKET = 10007
ANS_TCP_TIMEOUT_SOCKET = 20007


class ApDataSocket(UbClassTemplate):
	
	## \brief Constructeur de la data_socket
	# @param[in] _host the host address string
	# @param[in] _port the socket port (integer)
	# @param[in] _is_reset optionnal - Event that warn in cas of connexion reset : not used in this project
	def __init__(self, _host, _port, _is_reset=Event()):
		UbClassTemplate.__init__(self)

		self.flag_debug_mess=False
		self.debug_marker_start=txt_regular_blue
		self.debug("init")
		self.version="1.02"
		self.mode=AP_DATA_SOCKET_SELECTIVE
		self.socket_id = -1
		self.host = _host
		self.port = _port

		# variable décrivant si la connexion est ouverte, permettant une recconnexion automatique par 
		self.is_open = False
		# timeout de déconnexion :
		self.timeout = 18
		self.tic = mktime(localtime())
		   # rafraichi/stimulé par chaque appel à frame_ready.wait()
		self.event_is_connected = Event()
		self.event_is_reset = _is_reset 
		# reprends l'exception attrapée dans socket_recv_thread :
		self.system_exception = None
		# self.test_system_exception = False
		self.wait_buffer = []
		self.recv_buffer = [] # on ne peut pas utiliser un objet queue car 
		# on n'attends pas une frame quelconque mais avec un tag particulier
		self.__socket_lock = RLock()

	#	def read_frame(self, _flag=None): si None on pop le premier (tester si 0)
	def __pop_frame(self, _flag=None):
		if not len(self.recv_buffer):
			raise ap_socket_exception (322, "data_socket_c::__pop_frame : recv_buffer empty")

#		self.debug("data_socket_c::__pop_frame : size = %d"%(len(self.recv_buffer)))
		if _flag==None and len(self.recv_buffer) > 0:
			self.debug("pop any frame")
			return self.recv_buffer.pop(0)

		for i in range(len(self.recv_buffer)):
			if self.recv_buffer[i][0] == _flag:
#				self.debug("data_socket_c::__pop_frame : data ready")
				# il faut extraire la bonne
				flag, size, data = self.recv_buffer.pop(i)
	#			self.debug("data_socket_c::__pop_frame : get data")
				return flag, size, data
		
		raise ap_socket_exception (303, "data_socket_c: flag %d not found in recv_buffer"%(_flag))

	## \brief Attache un évènement d'un thread
	# pour une réception ultérieure (type BLOC_END) 
	# version sans lock 
	def __private_set_event(self, _flag):
		self.debug("flag %d" % (_flag))
		# abort on the same flag 
		for i in range(len(self.wait_buffer)):
			if self.wait_buffer[i][0]==_flag:
				self.debug("flag %d twice !" % _flag)
				raise ap_socket_exception(320, "data_socket_c: flag %d twice !" % _flag)
		
		sock_event = ap_socket_event(self)
		self.wait_buffer.append((_flag, sock_event))

		return sock_event

	# pseudo private (utilisé dans socket_event
	def _catch_exception_from_socket_thread(self):
		""" @brief Catch any exception raised in socket thread

		this mechanism allows to avoid exception from beeing lost when the receive thread fails and quit
		"""
		if self.system_exception :
			self.info("exception received from socket thread : %s"%str(self.system_exception)) 
			tmp = deepcopy(self.system_exception)
			self.system_exception = None
			raise tmp

#######################################################################
# Fonctions privées et également accessible par le thread socket_recv  
# et ap_socket_event                                                  #
#######################################################################

	## \brief Fait un lock sur la socket
	def lock(self):
		self.__socket_lock.acquire()

	## \brief Enlève le lock de la socket
	def unlock(self):
		self.__socket_lock.release()


	## \brief ajoute la nouvelle recv_buffer à la liste et prévient le demandeur
	# utilisé uniquement par le thread socket_recv
	def push_recv_buffer(self, flag, tab_size, data):
		self.debug("size recv_buffer = %d"%(len(self.recv_buffer)))
		self.debug("size wait_buffer = %d"%(len(self.wait_buffer)))
		self.lock()

		try:
			# on accepte plusieurs frames avec le même flag (pour l'instant on prévient
			for i in range(len(self.recv_buffer)):
				if self.recv_buffer[i][0] == flag:
	#				self.recv_buffer.pop(i)
					self.debug("INFO flag %d already in recv_buffer : user have to clear"%(flag))

			# en mode non selectif, toutes les trames recues sont mises dans le buffer
			if not self.mode==AP_DATA_SOCKET_SELECTIVE:
				# on ajoute la trame TCP dans la liste
				self.recv_buffer.append((flag, tab_size, data))
				self.debug("data is set (non-selective mode)")

			find_flag=False
			# on commence par les requettes les plus anciennes
			for i in range(len(self.wait_buffer)):
				if self.wait_buffer[i][0] == flag:
					find_flag=True
					if self.mode==AP_DATA_SOCKET_SELECTIVE:
						# on ajoute la trame TCP dans la liste
						self.recv_buffer.append((flag, tab_size, data))
						self.debug("data %s is set (selective mode)"%(flag))
					# on leve l'event
					self.wait_buffer[i][1].set()
					# on supprime la requête
	#				self.debug( "del request %s"%(flag))
					del self.wait_buffer[i]
					break # on ne traite qu'une seule requête

			# si on arrive ici en mode sélectif, c'est que le falg n'est pas attendu
			if self.mode==AP_DATA_SOCKET_SELECTIVE and not find_flag:
				self.debug("INFO frame %d is lost (selective mode)"%flag)
				
		finally:
			self.unlock()

	## \brief deconnecte la socket 
	# le recv_thread va ensuite se reconnecter automatiquement si nécessaire (si is_open)
	# utiliser wait_connexion() pour attendre que la connexion soit établie
	def private_reset(self):
		self.event_is_connected.clear()
		self.event_is_reset.set()
		try:
			self.socket_id.shutdown(socket.SHUT_RDWR)
		except:
			self.debug("socket was already shutdown")

		try:
			self.socket_id.close()
			# self.is_open = False  NON !! erreur d'utilisation de cette variable 
		except: # jamais constaté
			self.info("WARNING socket was not open")

		for req in self.wait_buffer:
			self.debug("remove request waiting on %d"%(req[0]))
			# on leve l'event
			req[1].set()

		# on vide la liste des trames attendues:
		self.wait_buffer = []
		# on ne vide pas le buffer des trames, c'est à l'utilisateur de le faire
		# avec la methode clear_buffer() en cas d'exception


	# pour gérér le timeout : si timeout-> sortir de la queue
	# utilisé uniquement par le wait de ap_event en cas de timeout
	# inclu un lock
	# on gère aussi le timeout de déconnexion. Celui-ci est compté (tic) à 
	# partir du dernier de la réception d'un flag
	# TODO fonction publique ? (elle est utilisée dans webserver_apf02)
	# @param l'objet Event
	def del_event(self, _event) :
		self.debug("try to delete event")
		self.lock()
		try:
			self._catch_exception_from_socket_thread()

			self.tic = mktime(localtime())
			# abort on the same flag 
			for i in range(len(self.wait_buffer)):
				if self.wait_buffer[i][1]==_event:
					self.debug("delete event for flag %s"%(self.wait_buffer[i][0]))
					self.wait_buffer.pop(i)
					break
					# il ne peut y avoir qu'une seule fois le même flag /
					# le même event
		finally:
				self.unlock()

#######################################################################
# Fonctions publiques                                                 #
#######################################################################

	## \brief ouvre une socket précédemment cloturée
	# relance le thread de reception
	def open(self):
		self.lock()
		try:
			if self.is_open :
				raise ap_socket_exception (312, "data_socket_c::open : socket already open")
			if self.event_is_connected.isSet():
				raise ap_socket_exception (401, "BUG WARNING data_socket_c::open : socket connected")

			self.debug("créer le thread de reception")
			self.is_open = True 
			# Lancement du thread de réception de données
			th_sock = ApSocketRecvTh(self, self.host, self.port)
			self.debug("démarre le thread")
			th_sock.start()
		finally:
				self.unlock()

	def close(self):
		""" @brief cloture la socket
		arrete le thread de reception
		"""
		self.info("demande de cloture de la socket")

		self.lock()
		try:
			self._catch_exception_from_socket_thread()
			try:
				sendAll(self.socket_id,pack('i', 0))
			except: # on ne remonte pas d'exception en cas d'échec
				self.info("WARNING, fail to send close commande to the driver")
				print (traceback.format_exc())
			self.is_open = False

			self.private_reset()
		finally:
			self.unlock()

		# on vide le buffer des trames TCP
	#	self.clear_buffer() # pas utile, génère une erreur

		self.debug("cloture la socket et arrete le thread de reception")

	def _is_active(self):
		""" @brief test si la data_socket est active
		"""
		# le timeout est dépassé et aucun élément attendu
		# si le driver se déconnecte si pas de requete durant la durée de timeout et qu'il n'y a pas de requete en cours il faut
		# cloturer pour éviter de garder la main sur le driver (utilisé par recv_thread)
		if mktime(localtime()) - self.tic > self.timeout and not len(self.wait_buffer):
			self.debug("the socket is inactive (timeout %f/%f)"%(mktime(localtime()) - self.tic , self.timeout))
			return False
		else :
			return True

	def test (self):
		self.send_frame(1, '')
		# tester (keepalive ?) si la socket est opérationnelle,
		# sinon faire un reset + exception

	# TODO ? rajouter un timeout
	def wait_connexion(self):
		""" @brief wait for the connexion with the driver to be established

		open the socket if needed 
		"""
		# sous python3 on utiliserait simplement :
#		self.event_is_connected.wait()
		# mais sous python2 wait n'est pas interrompu par un KeyboardInterrupt, alors on boucle, c'est moche mais il n'y a pas le choix
    # allow CTRL-C while waiting...
		self.debug ("attente de l'ouverture de la socket")
		while not self.event_is_connected.isSet():
			if not self.is_open:
				self.debug ("************* re-open the socket ******************")
				self.open()

			self.lock()
			try:
				# on vérifie qu'il n'y a pas d'exception transmise par le thread de réception
				self._catch_exception_from_socket_thread()
			finally:
				self.unlock()
			self.event_is_connected.wait(0.5)

	# \brief defini le timeout
	def set_connexion_timeout(self, _timeout):
		""" @brief defini le timeout
		gestion du timeout (pour éviter que le thread se connect en boucle alors que la socket n'est pas utilisée)
		a chaque requete on tic, dans le thread : si deconnexion on verifie le délai, si passé, on cloture.
		a chaque requet on verifie is_open : si non ap_socket_error
		pas protégé par un lock car c'est fait dans send_recv_frame
		"""
		if not self.event_is_connected.isSet():
			raise ap_socket_exception (319, "data_socket_c::set_connexion_timeout : socket is not connected")

		self.info ("setting timeout at %fs"%_timeout)
		self.timeout = _timeout
		flag, size, data = self.send_recv_frame(CMD_TCP_TIMEOUT_SOCKET, pack("i",_timeout+2.), ANS_TCP_TIMEOUT_SOCKET, 5.)
		self.debug ("done")

	## \brief envoie une trame TCP
	def send_frame(self, _flag, _message):
		self.lock()
		try:
			self._catch_exception_from_socket_thread()

			if not self.event_is_connected.isSet():
				self.debug ("socket not connected")
				raise ap_socket_exception (316, "data_socket_c::send_frame : socket is not connected")

			self.debug ("flag : %d"%(_flag))
			try:
				size = len(_message)
				sendAll(self.socket_id,pack('i', _flag)+pack('i', size)+_message)
																								# taille du message
																																 # chaine de caractere
			except ap_socket_error as sockexc:
				self.debug("ap_socket_error \"%s\""%str(sockexc))
				self.private_reset()
				raise sockexc
			except:
				self.debug( "sendAll fail, socket reconnect")
				print (traceback.format_exc())
				self.private_reset()
				raise ap_socket_error (118, "ap_data_socket::send_frame : sendAll fail, socket reconnect")
		
		finally:
			self.unlock()


	## \brief Attache un évènement à la réception d'un flag particulier
	# pour une réception par un autre thread. 
	# afin d'éviter de rater l'évenement, il est conseiller de faire le set_event
	# (et le wait sur l'evenement) avant d'envoyer la trame susceptible de le
	# déclancher
	def set_event(self, _flag):
		self.lock()
		try:
			# on vérifie qu'il n'y a pas d'exception transmise par le thread de réception
			self._catch_exception_from_socket_thread()

			if not self.event_is_connected.isSet():
				raise ap_socket_exception (315, "data_socket_c::set_event : socket is not connected")

#			sock_event = self.__private_set_event(_flag)
#			return sock_event
			return self.__private_set_event(_flag)
		finally:
			self.unlock()


	## \brief reception d'une trame identifiée par son flag
	# à utiliser pour l'attente courte d'une trame (le thread dort jusqu'à sa
	# réception)
	def recv_frame(self, _flag, _timeout=10.):
		self.lock() # on encadre le pop et le set_event par un seul lock pour éviter
		            # l'arrivée d'une trame entre les deux
		try:
			self._catch_exception_from_socket_thread()
			
			if not self.event_is_connected.isSet():
				raise ap_socket_exception (314, "data_socket_c::recv_frame : socket is not connected")

			try:
				flag, size, data = self.__pop_frame(_flag)
				self.debug( "A VALIDER trame %d déjà présente dans le buffer (pas de gestion d'event)"%(_flag))
				return flag, size, data
			except ap_socket_exception : # si la trame n'est pas dispo
																	 # dans le buffer, on set un event
				# ici on utilise l'event interne : frame ready
				frame_ready = self.__private_set_event(_flag)
		finally:
			self.unlock()
		
		self.info("data_socket_c::recv_frame : wait frame_ready")
		
		# le unlock doit être fait avant le wait pour permettre à recv_sock_th 
		# d'écrire dans le buffer
		frame_ready.wait(_timeout)
		# la trame est arrivée, on la lit
		return self.read_frame(_flag)

	## \brief envoie une trame TCP et recoit une réponse
	# à utiliser avec l'option AP_DATA_SOCKET_SELECTIVE pour éviter de perdre une
	# trame qui arrive avant qu'on ai eu temps de la lire
	# ATTENTION, on utilise la fonction send_recv_frame pour garantir qu'il n'y aura pas d'autre requète
	# (d'un autre thread par ex.) avant d'avoir pu recevoir la réponse. 
	# Afin de garantir que l'appelant ne va pas lire la réponse à une requète 
	# précédente, la fonction vérifie que cette réponse n'est pas déjà présente,
	# sinon elle remonte l'exception 317 : data_socket_c::send_recv_frame : flag 20007 already received.
	# pour éviter ça, il faut vider le buffer de réception (clear_buffer() ou clear_buffer(20007)) avant d'appeler la fonction.
	def send_recv_frame(self, _flag_send, _message_send, _flag_recv, _timeout=10.):
		self.lock() # on encadre le pop et le set_event par un seul lock pour éviter
		            # l'arrivée d'une trame entre les deux
		try:
			self._catch_exception_from_socket_thread()

			if not self.event_is_connected.isSet():
				self.info("socket not connected")
				raise ap_socket_exception (318, "data_socket_c::send_recv_frame : socket is not connected")

			self.debug ("send : %d ; recv %d"%(_flag_send, _flag_recv))
			try: #on verifie si le flag est déjà présent (il sera jeté)
				flag, size, data = self.__pop_frame(_flag_recv)
			except ap_socket_exception as e: # ici l'exception est normale et attendue
				#normalement le buffer ne contient pas le flag et lève une exception 322 (empty) ou 303 (not found)
				self.debug("socket exception normal apres pop_frame %s"%(str(e)))
			else: # si pas d'exception, c'est anormal:
				# la forme est une peu bizarre ici, on pourrait remplacer par une fonction qui test l'inexistance du flag dans le buffer
				self.info("flag %d already received"%(_flag_recv)) 
				raise ap_socket_exception (317, "data_socket_c::send_recv_frame : flag %d already received"%(_flag_recv))
												# the developper should clear_buffer before using send_recv_frame

			try:
				self.debug ("set event %d"%(_flag_recv))
				frame_ready = self.__private_set_event(_flag_recv)
				if _message_send is None:
					self.info ("Warning, data to send is None")
					_message_send = "" # to avoid fail of len()

				message_size = len(_message_send)
				self.debug ("sendAll %d"%(_flag_send))
				sendAll(self.socket_id,pack('i', _flag_send)+pack('i', message_size)+_message_send)
																								# taille du message
																																 # chaine de caractere
			except ap_socket_error as sockexc:
				self.debug("ap_socket_error \"%s\""%str(sockexc))
				self.private_reset()
				raise sockexc
			except:
				# l'emission à échoué, on coupe la connexion pour qu'elle soit relancée 
				# par sock_recv_th
				self.info( "sendAll fail, socket reconnect")
				print (traceback.format_exc())
				self.private_reset()
				raise ap_socket_error (119, "ap_data_socket::send_recv_frame : sendAll fail, socket reconnect")

		finally:
			self.unlock()

		self.debug ("wait %d"%(_flag_recv))
		frame_ready.wait(_timeout)
		self.debug ("wake up %d"%(_flag_recv))
		# la trame est arrivée, on la lit
		flag, size, data = self.read_frame(_flag_recv)
		return flag, size, data


	## \brief lecture d'une trame dans le buffer de réception
	# retourne la trame
	# remonte une socket_exception si la trame est absente 
	def read_frame(self, _flag=None):
		self.lock()
		try:
			try:
				self._catch_exception_from_socket_thread()

				self.debug("ready to read the frame")
				flag, size, data = self.__pop_frame(_flag)
				return flag, size, data
			
			except ap_socket_error as sockexc:
				self.debug("ap_socket_error \"%s\""%str(sockexc))
				self.private_reset()
				raise sockexc
			except:
				self.info("ERROR while getting the frame with flag = %s"%(_flag))
				print (traceback.format_exc())
				raise ap_socket_error (120, "ERROR while getting the frame with flag = %s"%(_flag))

		finally:
			self.unlock()

	## \brief nettoie le buffer des trames TCP
	# à utiliser en cas d'exception par exemple
	# peut être utilisé à tout moment
	# @param _flag défini le type de trames à supprimer du buffer \
	#              si ce paramètre n'est pas spécifié, le buffer est entièrement vidé
	# @return nombre de trames supprimées
	def clear_buffer (self, _flag=None):
		self.lock()
		try:
			self.debug ("clearing buffer")
			self._catch_exception_from_socket_thread()
				
			if _flag==None:
				size = len(self.recv_buffer)
				if self.flag_debug_mess :
					for frame in self.recv_buffer:
						self.debug ("del recv_buffer flag=%d"%frame[0])
				self.recv_buffer = []
			else:
				size = 0
				for i in reversed(range(len(self.recv_buffer))):
					if self.recv_buffer[i][0] == _flag:
						size += 1
						self.debug ("del recv_buffer flag=%d" % _flag)
						del self.recv_buffer[i]
			
			self.debug("receive buffer cleared (%d frames)"%size)
			return size

		finally:
			self.unlock()

###########################
# Fonctions pour debug    #
###########################
# TODO a mettre dans les test unitaires 

	## \brief Display the content of wait_buffer
	def dbg_show_wait_buffer (self):
		if len(self.wait_buffer):
			for i in range(len(self.wait_buffer)):
				print ("*** wait_buffer[%d]: flag=%d") % (i, self.wait_buffer[i][0])
		else:
			print ("*** wait_buffer is empty !")

	## \brief Display the content of recv_buffer
	def dbg_show_recv_buffer (self):
		if len(self.recv_buffer):
			for i in range(len(self.recv_buffer)):
				print ("*** recv_buffer[%d]: flag=%d size=%d") % (i, self.recv_buffer[i][0], self.recv_buffer[i][1])
		else:
			print ("*** recv_buffer is empty !")

