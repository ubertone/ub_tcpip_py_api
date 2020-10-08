#!/usr/bin/env python
# -*- coding: UTF_8 -*-

# @copyright  this code is the property of Ubertone. 
# You may use this code for your personal, informational, non-commercial purpose. 
# You may not distribute, transmit, display, reproduce, publish, license, create derivative works from, transfer or sell any information, software, products or services based on this code.
# @author Jean Luc Bielmann, Stéphane Fischer

import inspect
import re
import sys

from datetime import datetime
from time import strftime, time

txt_regular_black ='\033[30m'
txt_regular_red= '\033[31m'
txt_regular_green ='\033[32m'
txt_regular_yellow ='\033[33m'
txt_regular_blue ='\033[34m'
txt_regular_purple ='\033[35m'
txt_regular_cyan ='\033[36m'
txt_regular_white ='\033[37m'
txt_regular_reset = "\033[0m"

class UbClassTemplate:

	debug_marker_start = txt_regular_reset
	debug_marker_end = txt_regular_reset

	global_debug_active = True
	global_debug_force = False

	def __init__(self):
		self.time_start = None
		self.flag_debug_mess = False

	# Childs need to declare :
	# - self.flag_debug_mess: True/False
	# - self.lock (optionnal): Lock()
	# - self.debug_marker_start
	# - self.debug_marker_end

	# \brief A virtual method designed to be overloaded by children class. Nobody should load, files, start thread, or do some other initialization stuff in constructor. This must be done in the load method.
	def post_init(self):
		pass

	def log (self, pattern_string, *string_args):
		self.__print_log(pattern_string, string_args)

	# \brief For internal messages which are not warnings or errors !
	def debug (self, pattern_string, *string_args):
		# on optimise avec le test pour éviter de traiter les chaines pour rien si le debug est desactivé
		if UbClassTemplate.global_debug_active and ( UbClassTemplate.global_debug_force or self.flag_debug_mess ):
			self.__print_log(pattern_string, string_args)

	# \brief Please always use this function for internal warnings and errors !
	def info (self, pattern_string, *string_args):
		self.__print_log(pattern_string, string_args)

	def fatal (self, pattern_string, *string_args):
		# TODO san : inform the watchdog
		self.__print_log(pattern_string, string_args)
		# TODO une fois que l'on a informé le watchdog, réactiver l'exit
		# exit(-1)

	def profiler_start (self):
		self.time_start = time()

	def profiler_stop (self, _message="", _threshold=0.0 ):
		delta = time() - self.time_start
		if delta >= _threshold:
			self.log("%s - Total time: %.02fs" % (_message,delta))

	def __print_log(self, pattern_string, string_args):
		# TODO on pourrait rajouter ici l'info sur le thread : thread.get_ident()
		# TODO on pourrait ajouter un arg pour traceback
		d = datetime.now()
		tic = strftime("%y/%m/%d %H:%M:%S.", d.timetuple()) + ("%06d" % d.microsecond)
		classname = self.__class__.__name__
		stack = inspect.stack()
		method = stack[2][3]
		parent = ""
		if len(stack)>3:
			parent = re.sub(r'.py', r'', re.sub(r'.*/', r'', stack[3][1])) + "/" + stack[3][3]

		output_message = self.__build_output_message( pattern_string, string_args )

		print ("[%s] %s%s::%s:%s %s\n<< %s"% (tic, self.debug_marker_start, classname, method, self.debug_marker_end, output_message, parent) )
		sys.stdout.flush()

	def __build_output_message(self, pattern_string, string_args):

		if len( string_args ) == 0:
			output_message = pattern_string
		elif isinstance(string_args[0], tuple):
			output_message = pattern_string % string_args[0]
		else:
			output_message = pattern_string % string_args

		return output_message
