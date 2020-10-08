#!/usr/bin/env python
# -*- coding: UTF_8 -*-

from copy import deepcopy

class path_xml_t:
	"""
	Class used to build normalized path to navigate to the xml tree (see xpath)
	The method handle the following syntax: https://docs.python.org/2/library/xml.etree.elementtree.html#supported-xpath-syntax
	"""
	def __init__(self, _path=None):
		"""
		Constructor initilise the path to '.' by default, this represent the first node (root) of the XML.
		"""
		if _path == None:
			self.path = "."
		else:
			self.path = _path
	
	def duplicate(self):
		"""
		Returns a new object path_xml_t with the same path.
		"""
		return path_xml_t(self.path)
	
	def get_path(self):
		"""
		Return a deepcopy of the string path
		"""
		return deepcopy(self.path)
	
	def clear(self):
		"""
		Delete the current path and reset to '.'
		"""
		del self.path
		self.path = "."
	
	def extend_path(self, _list_element):
		"""
		Extend path allows to concatenates the list of elements to find to search in the XML
		The method takes cares of the separations caracteres.
		The method handle the following syntax (https://docs.python.org/2/library/xml.etree.elementtree.html#supported-xpath-syntax):
		'tag' : Selects all child elements with the given tag
		'*' : Selects all child elements
		'.' : Selects the current node
		'//' :  Selects all subelements, on all levels beneath the current element
		'..' : Selects the parent element
		"""
		for elem in _list_element :
			if elem == '.':
				continue
			elif elem == '//':
				self.path += elem
			else:
				self.path += "/%s"%(elem)
	
	def insert_attribute_predicate(self, _name_attr=None, _value_attr=None):
		"""
		Insert attribute predicate (square brackets) at end of path, allows to select specific elements with the given attribute
		The method takes cares of the separations caracteres.
		"""
		if _name_attr != None:
			safe_name_attr = _name_attr.strip()
			attr_str = "[@%s"%(safe_name_attr)
			if _value_attr != None:
				safe_value_attr = _value_attr.replace("\'", "").strip()
				attr_str += "=\'%s\']"%(safe_value_attr)
			else:
				attr_str += "]"
			
			self.path += attr_str
	
	def insert_tag_predicate(self, _tag_child=None, _text_tag_child=None):
		"""
		Insert tag predicate (square brackets) at end of path, allows to select specific elements with the given first child's tag
		The method takes cares of the separations caracteres.
		"""
		if _tag_child != None:
			safe_tag_child = _tag_child.strip()
			tag_str = "[%s"%(safe_tag_child)
			if _text_tag_child != None:
				safe_text_tag_child = _text_tag_child.replace("\'", "").strip()
				tag_str += "=\'%s\']"%(safe_text_tag_child)
			else:
				tag_str += "]"
			
			self.path += tag_str
	
	def insert_position_predicate(self, _position=None):
		"""
		Insert position predicate (square brackets) at end of path, allows to select elements with specific positions
		The method takes cares of the separations caracteres, accept only numbers.
		"""
		if _position != None:
			if isinstance(_position, int) :
				self.path += "[%d]"%(_position)
			else:
				print ("Error: Cannot insert position predicate because position is not an int ! (%s)")%(_position)
	
	



