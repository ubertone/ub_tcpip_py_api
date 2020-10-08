#!/usr/bin/env python
# -*- coding: UTF_8 -*-

from copy import deepcopy
from xml.dom import minidom

from ub_lib_v1.minidom_xml_RO import minidom_wrapper_ro, EX

class minidom_wrapper (minidom_wrapper_ro):
	"""
	Class to handle XML data structures.
	
	Inerits from modules.ub_lib.ub_class_template to handle the flag messages (INFO, WARNING, ERROR, DEBUG).
	The root element of the XML tree is extracted, when it's open from a file, and thus became the first element.
	The first element is referenced as '.' and not by his name.
	
	With minidom, self.xml_root  has to be a Document object otherwise some methods cannot be used (ex: createElement, createTextNode)
	"""
	
	def __init__ (self, _xml_node=None, _flag_debug_mess = False):
		"""
		Class constructor, can take an existing xml tree as input.
		flag debug message can be activated.
		@param _xml_node an etree node object or None.
		@param _flag_debug_mess a bool to activate the degug message.
		"""
		flag_debug_mess = _flag_debug_mess		# used in prjtemplate
		self._current_path = None
		self.xml_root = None			#Si xml_root n'est pas instancié alors il y a une exception lors de l'appel de __del__
		if isinstance(_xml_node, minidom.Document) or _xml_node==None:
			self.xml_root = _xml_node
		else:
			self.info("ERROR, constructor: the given element must be a Document object or None")
			raise EX.XML_InputError()
	
	def _get_parent_path(self):
		"""
		Return the parent path according to _current_path, without the last element, the child name is return as well.
		If only one element in the _current_path, the parent node is the root node (the one in self.xml_root).
		A Warning is raised if the last element name is one of: '.', '..', ' '
		"""
		sep = '/'
		elems = self._current_path.split(sep)
		if len(elems) <1:
			self.info("WARNING, _get_parent_path: no child name to extract !")
			return None, None
		elif len(elems) ==1:
			last_elem_name = elems[0]
			parent_path = '.'
			if last_elem_name == '.' or last_elem_name == '..' or last_elem_name == '':
				self.info("WARNING, _get_parent_path: invalid child name (%s) !"%(last_elem_name))
				return None, None
		else:
			last_elem_name = elems.pop()
			parent_path = sep.join(elems)
		return parent_path, last_elem_name
	
	def _make_parent(self, _caller):
		old_path = deepcopy(self._current_path)
		parent_path, child_name = self._get_parent_path()
		self._clear_path()
		if parent_path:
			self.set_elem(child_name, parent_path)
		else:
			self.info("ERROR, %s: can't find parent node of \"%s\" in XML, can't set data"%(_caller, old_path))
			raise EX.XML_SearchError()
		self._current_path = old_path
		search = self._find_elem()
		
		return search
	
	def set_elem(self, _new_element, _user_xpath='.', _list_elem=[], _attr_name=None, _attr_value=None):
		"""
		Set the _new_element at the end of the given path.
		_new_element can be a string or a node
		Bug minidom, ne peut pas faire de appendChild à l'élément root
		"""
		self._build_path(_user_xpath, _list_elem, _attr_name, _attr_value, "set_elem")
		
		search = self._find_elem(True, "set_elem")
		parent = search[0]
		self._clear_path()
		if isinstance(_new_element, minidom.Element):		#append an Element (Node is not suitable, doesn't have getElementbyTagName)
			if parent.parentNode is None:
				parent.insertBefore(_new_element, parent.lastChild)		#bug sur le noeud root, on ne peut pas faire de appendChild
			else:
				parent.appendChild(_new_element)
		elif isinstance(_new_element, str):				#create & append node
			new_name = _new_element.strip()
			new_node = self.xml_root.createElement(new_name)
			if parent.parentNode is None:
				parent.insertBefore(new_node, parent.lastChild)		#bug sur le noeud root, on ne peut pas faire de appendChild
			else:
				parent.appendChild(new_node)
		else:
			self.info("ERROR, set_elem: _new_element must be a string or a node !")
			raise EX.XML_InputError()
		
		return
	
	def set_data(self, _new_data, _user_xpath='.', _list_elem=[], _attr_name=None, _attr_value=None):
		"""
		Add/Change the content of the text field for the given element.
		Set None to erase data
		"""
		self._build_path(_user_xpath, _list_elem, _attr_name, _attr_value, "set_data")
		
		search = self._find_elem()
		if not search:
			search = self._make_parent("set_data")
			#pas de vérification sur le retour de _find_elem mais le nouveau noeud créé devrait être trouvé, sinon set_elem lève une erreur si le parent du parent n'existe pas.
		
		if len(search) > 1:
			self.info("ERROR, set_data: found too many elements \"%s\" in XML"%(self._current_path))
			raise EX.XML_SearchError()
		
		self._clear_path()
		search = search[0]
		if isinstance(search, minidom.Document):
			self.info("ERROR, set_data: Cannot set data to a Document node (root node) !")
			raise EX.XML_InputError()
		
		txt_node = self._extract_text_node(search)
		if isinstance(_new_data, str):
			insert_data = _new_data.strip()
		elif isinstance(_new_data, int):
			if search.hasAttribute("mult"):
				search.removeAttribute("mult")
			insert_data = repr(_new_data)
		elif isinstance(_new_data, float):
			mult = self._extract_mult(search)
			insert_data = repr(_new_data/mult)
		else:
			insert_data = repr(_new_data)
		
		if _new_data == None :	#remove text node
			if txt_node != None:
				removed_node = search.removeChild(txt_node)
				removed_node.unlink()
		elif txt_node==None:	#create text node
			new_txt_node = self.xml_root.createTextNode(insert_data)
			search.appendChild(new_txt_node)	#unlink on returned node ?
		else:					#existing node, change content
			del txt_node.data
			txt_node.data = insert_data
		
		return
	
	def set_attribute(self, _attr_to_write, _new_attr_value, _user_xpath='.', _list_elem=[], _attr_name=None, _attr_value=None):
		"""
		Add/Write the value of the attribute for the given element, uses repr method if _new_attr_value is not a string.
		Uses _new_attr_value = None to remove the _attr_to_write from the list of attributes.
		"""
		self._build_path(_user_xpath, _list_elem, _attr_name, _attr_value, "set_attribute")
		
		search = self._find_elem()
		if not search:
			search = self._make_parent("set_attribute")
		
		if len(search) > 1:
			self.info("ERROR, set_attribute: found too many elements \"%s\" in XML"%(self._current_path))
			raise EX.XML_SearchError()
		
		self._clear_path()
		search = search[0]
		if isinstance(search, minidom.Document):
			self.info("ERROR, set_attribute: Cannot set attribute to a Document node (root node) !")
			raise EX.XML_InputError()
		
		if _new_attr_value == None:
			if search.hasAttribute(_attr_to_write):
				search.removeAttribute(_attr_to_write)
		else:
			if isinstance(_new_attr_value, str):
				write_in_attr = _new_attr_value.strip()
			else:
				write_in_attr = repr(_new_attr_value)
			search.setAttribute(_attr_to_write, write_in_attr)
		
		return
	
