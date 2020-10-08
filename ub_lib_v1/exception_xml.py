#!/usr/bin/env python
# -*- coding: UTF_8 -*-

class XML_Exception (Exception): 
	""" base exception class for xml wrapper """
	def __init__(self, _string_error=""):
		self.msg = _string_error
	
	def __str__(self):
		return self.msg

class XML_InputError(XML_Exception):
	"""Exception raised when errors in the input"""
	pass

class XML_NoDataError(XML_Exception):
	"""Exception raised when no data loaded"""
	pass

class XML_SearchError(XML_Exception):
	"""Exception raised when no data loaded"""
	pass

#~ class XML_ValueError(XML_Exception):
	#~ """Exception raised when no data loaded"""
	#~ pass

