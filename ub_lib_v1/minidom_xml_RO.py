#!/usr/bin/env python
# -*- coding: UTF_8 -*-
# doit rester compatible avec python 2.4

import subprocess # pour subprocess.Popen et wait
from copy import deepcopy

from xml.parsers.expat import ExpatError
from xml.dom import minidom
from errno import ENOENT

from ub_lib_v1.ub_class_template import UbClassTemplate
from ub_lib_v1.path_xml_builder import path_xml_t
import ub_lib_v1.exception_xml as EX

## /brief Converti "yes" or "true" en True, tout le reste en False 
# @param _val string to evaluate as bool
# @return True ou False
def evaluate_bool (_val):
	clean_val = (_val.strip()).lower()
	if clean_val=="yes" or clean_val=="y" or clean_val=="true":
		return True
	else:
		return False

class minidom_wrapper_ro (UbClassTemplate):
	"""
	Class to handle XML data structures.
	
	Inerits from ub_lib_v1.ub_class_template to handle the flag messages (INFO, WARNING, ERROR, DEBUG).
	The root element of the XML tree is extracted, when it's open from a file, and thus became the first element.
	The first element is referenced as '.' and not by his name.
	
	The xml_root can be a Document or an Element object on this read only version, beacause the methods createElement and createTextNode are not used.
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
		self.xml_root = None
		if isinstance(_xml_node, (minidom.Element, minidom.Document)) or _xml_node==None:
			self.xml_root = _xml_node
		else:
			self.info("ERROR, constructor: the given element must be a Document or Element object or None")
			raise EX.XML_InputError()
	
	def __del__(self):
		if isinstance(self.xml_root, minidom.Document):	# permet de ne pas faire un unlink sur un élément du Document XML après un get_elem (Si on créé un wrapper à partir d'un élément)  
			self.xml_root.unlink()
	
	def parse_file (self, _filename, _default=""):
		"""
		Parse a file, load the root element in the XML structure.
		@param _filename the filename of the xml file to parse
		@_default the default filename to parse in case _filename fails.
		"""
		#flag_debug_mess = False #why force to false??
		xml_tree = None
		
		shall_copy = False	#copy the default file (commande unix "cp")
		try:
			xml_tree = minidom.parse(_filename)
		except IOError as e:
			if e.errno==ENOENT:
				self.info("ERROR, parse_file: %s don't exist" %(_filename))
				shall_copy = True
				pass
			else:
				self.info("ERROR, parse_file: unknown error while reading %s" % (_filename))
				shall_copy = True
				raise e
		except ExpatError:
			self.info("ERROR, parse_file: while parsing %s" % (_filename))
			shall_copy = True
			pass
		
		if shall_copy and _default:
			try:
				self.info("WARNING, parse_file: try %s instead" % (_default))
				p = subprocess.Popen(['cp', _default, _filename], stdout=subprocess.PIPE)
				p.wait()
				xml_tree = minidom.parse(_default)
			except:
				self.info("ERROR, parse_file: while reading default config : %s" % _default)
				raise EX.XML_InputError()
		
		if xml_tree == None:
			self.info("ERROR, parse_file: can't extract any xml data, no xml loaded")
			raise EX.XML_NoDataError()
		else:
			self.xml_root = xml_tree
		
		return
	
	def parse_string(self, _string):
		"""
		Parse a string, load from the first element in the XML structure.
		@param _string the xml string to parse
		@param _parser use the sax parser (set anything different from "" or None)
		@TODO: ajouter des sécurités / vérifications en cas d'erreur ?
		"""
		self.xml_root = minidom.parseString(_string)
	
	def to_string(self, _auto_indent=False, _encoding="UTF-8"):
		"""
		Convert the XML structure to a string, encoded by "UTF-8" by default.
		The user can decide to automatically indent the xml.
		@param _auto_indent include indentation of the xml tree for human readability.
		@param _encoding change encoding of the string.
		"""
		self._check_root("to_string")
		
		if not _auto_indent:
			return self.xml_root.toxml(_encoding)
		else:
			return self.xml_root.toprettyxml(encoding=_encoding)
	
	def _check_root(self, _caller):
		"""
		Check if the xml root is loaded
		"""
		if self.xml_root == None:
			self.info("ERROR, %s: Please load XML data before !"%(_caller))
			raise EX.XML_NoDataError()
	
	def _clear_path(self):
		"""
		Delete the path_xml_t object and replace by None
		"""
		del self._current_path
		self._current_path = None
	
	def _build_path(self, _user_xpath, _list_elem, _attr_name, _attr_value, _caller):
		"""
		Construct a path from a list of elements names and allows to specify attributes name & value + position for the last element.
		If the user gives the elements, then the first "." is automatically added.
		The _list_elem can be a single string as well (then the method wrap the string in a list)
		The user can build his own path from the path_xml_t class and give it to minidom_wrapper object.
		"""
		self._check_root(_caller)
		
		if isinstance(_list_elem , str):
			_list_elem = [_list_elem]
		
		if isinstance(_user_xpath, path_xml_t):
			self._current_path = deepcopy(_user_xpath.path)
		elif isinstance(_user_xpath, str):
			self._current_path = _user_xpath.strip('/')
		elif isinstance(_list_elem, list):
			if len(_list_elem) > 0:
				xml_path=path_xml_t()
				xml_path.extend_path(_list_elem)
				xml_path.insert_attribute_predicate(_attr_name, _attr_value)
				self._current_path = deepcopy(xml_path.path)
				del xml_path
			else:
				self._clear_path()
		else:
			self._clear_path()
		
		if self._current_path == None:
			self.info("ERROR, %s: Uncorrect input path !"%(_caller))
			raise EX.XML_InputError()
		
	def _find_elem(self, _check_search=False, _caller=''):
		"""
		Find the elements corresponding to the given path (self._current_path).
		The function return a list of elements or None if nothing is found.
		Support the '.' and '..' notation for the current node and the parent node.
		@param _max_n_elem: maximal number of elements to return. Default is None, to return everything.
		Always return a list (empty if nothing found)
		"""
		search_list = [self.xml_root]
		list_elem, list_attr = self._path_analyse()
		for i in range(len(list_elem)):
			target = list_elem[i]
			att_n, att_v = list_attr[i]
			next_search_list = []
			for node in search_list:
				if target == '.':
					new_node = [node]
				elif target == '..':
					new_node = [node.parentNode]
				else:
					new_node = node.getElementsByTagName(target)
				if new_node != None:
					next_search_list.extend(new_node)
			search_list = self._select_by_attribute(next_search_list, att_n, att_v)
			del next_search_list
		
		if _check_search:
			if not search_list:
				self.info("ERROR, %s: can't find element \"%s\" in XML"%(_caller, self._current_path))
				raise EX.XML_SearchError()
			elif len(search_list) > 1:
				self.info("ERROR, %s: found too many elements \"%s\"  in XML"%(_caller, self._current_path))
				raise EX.XML_SearchError()
		
		return search_list
	
	def _select_by_attribute(self, _element_list, _attr_name, _attr_value):
		"""
		Select the elements in _element_list, with the given _attr_name & _attr_value.
		if _attr_name is None, then it will select all nodes automatically.
		if _attr_value is None, the selected elements will be on the name of the attribute, no matter the attribute value.
		"""
		result = []
		if _attr_name != None:
			for element in _element_list:
				if  element.hasAttribute(_attr_name):
					if _attr_value != None:
						#the _attr_name is in the attributes, get the attribute value
						attr_value = element.getAttribute(_attr_name)
						if _attr_value == attr_value:
							#this element has an attribute with the good name & value, keep element
							result.append(element)
					else:
						#no value to check, keep element
						result.append(element)
		else:
			#no name to check, keep all
			result.extend(_element_list)
		return result
	
	def _path_analyse(self):
		"""
		analyse the xml path according to the string in self._current_path
		The syntax of the string has to be a simple version of the xpath norm.
		It separates the nodes according to '/', accept the '.' and '..' (géré par _find_node).
		The attribute name has to be identified by an '@' before and the value follows an '=', everything into '[]' or '{}' ex: "[@attr_name='attr_value']"
		Un seul attribut peut-être lu par élément !!
		return 2 list, the first one is the list of elements and the second list is the correspnding attribute with its attribute value.
		If no attribute is precised, then None will be set by default.
		"""
		elems = self._current_path.split('/')
		string_discard = "=@/[]{}\"\'"
		elements = []
		attributes = []
		for text in elems:
			attn = None
			attv = None
			group = text.split('@')
			if len(group)>1:
				txt_attr = group[1]
				grp_attr = txt_attr.split('=')
				if len(grp_attr) > 1:
					attv = grp_attr[1].strip(string_discard)
				attn = grp_attr[0].strip(string_discard)
			if attn == '':
				attn=None
			if attv == '':
				attv=None
			attributes.append((attn, attv))
			elements.append(group[0].strip(string_discard))
		return elements, attributes
	
	def _extract_text_node(self, _xml_element):
		"""
		Loop on the firstChild node until if finds a text node or None.
		Return None if nothing
		"""
		loop = True
		text_node = None
		node = _xml_element
		while loop:
			if node == None:
				loop = False
				continue
			if node.nodeType == node.TEXT_NODE:
				loop = False
				text_node = node
			else:
				node = node.firstChild
		
		return text_node
	
	def _extract_text_data(self, _xml_element):
		"""
		Loop on the firstChild node until if finds a text node or None.
		Return an empty string if nothing
		"""
		txt_node = self._extract_text_node(_xml_element)
		if txt_node:
			return txt_node.data
		else:
			return ""
	
	def _format_text(self, _data_txt, _mult, _type, _caller):
		if _type == "text" or _type == "txt":
			if _data_txt == None:
				result = ''
			else:
				result = _data_txt.strip()
		elif not _data_txt:		#evite les ValueErrror avec '' ou None dans int ou float. Aussi retourne None si la liste est vide avec les type bool
				result = None
		elif _type == "bool":
			result = evaluate_bool(_data_txt)
		elif _type == "int" or _type == "float" :
			try:
				result = float(_data_txt)*_mult
				if _type == "int":
					result = int(round(result))
			except ValueError:
				self.info("Error, %s: Unable to read %s (%s)"%(_caller, _type, _data_txt))
				raise ValueError
		else:
			self.info("Warning, %s: Unknown data type to return ! Return as read"%(_caller))
			result = _data_txt
		
		return result
	
	def _extract_mult(self, _xml_element):
		"""
		Private method to extract mult value from _xml_element.
		Always return a number (default 1.0), force the mult value to 1.0 in xml if the attribute is here but cannot be read as a float.
		"""
		if _xml_element.hasAttribute("mult"):
			mult_txt = _xml_element.getAttribute("mult")
			try:
				mult = float(mult_txt)
			except ValueError:
				self.info("Warning, _extract_mult: Unable to read mult value (%s), force to 1.0"%(mult_txt))
				mult = 1.0
				_xml_element.setAttribute("mult", "1.0")
		else:
			mult = 1.0
		return mult
	
	def get_elem(self, _user_xpath='.', _list_elem=[], _attr_name=None, _attr_value=None):
		"""
		The method get_new_elem provides a new object minidom_wrapper, with the root node set according to given path 
		
		The method takes as input a list of strings, representing a sequence of elements to search for.
		In that case, the first node (root node) is automaticaly take into account (the "." is added by default)
		The user can specify the attribute (name and value) to select the last element in _list_elem, and the position of the last element (default first).
		Otherwise, the user can provide a path_xml_t object (priority), describing the path to the element.
		
		Returns None if an error occurs, or if the element is not found.
		If the element is found, a list of minidom nodes is returned.
		
		Warning, any operation on the return object will affect the current XML data !
		"""
		self._build_path(_user_xpath, _list_elem, _attr_name, _attr_value, "get_elem")
		
		search = self._find_elem()
		if not search:		#if []
			self.info("ERROR, get_elem: no \"%s\" element found in XML"%(self._current_path))
			raise EX.XML_SearchError()
		
		self._clear_path()
		return search
	
	def get_data(self, _data_type="text", _user_xpath='.', _list_elem=[], _attr_name=None, _attr_value=None):
		"""
		The method get_text_from_elem provides the text from the element
		
		The method takes as input a list of strings, representing a sequence of elements to search for.
		The user can specify the attribute (name and value) to select the last element in _list_elem, and the position of the last element (default first).
		Otherwise, the user can provide a path_xml_t object (priority), describing the path to the element.
		@param _data_type precise the type of data to return. Accept "text", "int", "float", "bool"
		Returns None if an error occurs, or if the element is not found.
		return an empty string if the node is empty
		"""
		self._build_path(_user_xpath, _list_elem, _attr_name, _attr_value, "get_data")
		
		search = self._find_elem(True, "get_data")
		
		self._clear_path()
		search = search[0]
		data = self._extract_text_data(search)
		mult = self._extract_mult(search)
		return self._format_text(data, mult, _data_type, "get_data")
	
	def get_attribute(self, _attr_to_read, _data_type="text", _user_xpath='.', _list_elem=[], _attr_name=None, _attr_value=None):
		"""
		Read the value of the attribute, as text (as written in XML), for the given element.
		@param _data_type precise the type of data to return. Accept "text", "int", "float", "bool"
		"""
		self._build_path(_user_xpath, _list_elem, _attr_name, _attr_value, "get_attribute")
		
		search = self._find_elem(True, "get_attribute")
		
		self._clear_path()
		search = search[0]
		attr_txt = None
		if search.hasAttribute(_attr_to_read):
			attr_txt = search.getAttribute(_attr_to_read)
		return self._format_text(attr_txt, 1.0, _data_type, "get_attribute")
	
	def get_nb_elem (self, _user_xpath='.', _list_elem=[], _attr_name=None, _attr_value=None):
		"""
		Count the number of elements, as given by user, present in the XML.
		If no elements present, print a warning and return 0.
		To find all the recurences of elem, in all childs of sub-element, uses _list_elem = [".", "sub-elem", "//", "elem"]
		"""
		self._build_path(_user_xpath, _list_elem, _attr_name, _attr_value, "get_nb_elem")
		
		search = self._find_elem()
		nb_elems = len(search)
		if nb_elems == 0:
			self.info("INFO, get_nb_elem: no \"%s\" element found in XML"%(self._current_path))
		
		self._clear_path()
		return nb_elems
	

