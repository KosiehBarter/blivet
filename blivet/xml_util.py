from . import util
import xml.etree.ElementTree as ET
from socket import gethostname
import importlib
from collections import namedtuple

import pdb

# debug
import traceback

################################################################################
##### BASIC FUNCTIONS
def create_basics():
    """
        This function creates root element and subelements that will be filled
        with Devices and Formats. Returns tuple: ET.Element and list
    """
    super_elems = []

    root_elem = ET.Element("Blivet-XML-Tools")
    super_elems.append(ET.SubElement(root_elem, "Devices"))
    super_elems.append(ET.SubElement(root_elem, "Formats"))
    super_elems.append(ET.SubElement(root_elem, "InternalDevices"))
    return (root_elem, super_elems)

def save_file(root_elem, dump_device=None, custom_name=None, rec_bool=False):
    """
        Saves a XML file upon specified criteria.
        Decides, if to save specific device data or whole Blivet.devices.
        Also, adds -recursive string to name and automatically appends ".xml".
    """
    # Get basic name, if custom, then custom
    final_name = gethostname().split(".")[0]
    if custom_name != None:
        final_name = custom_name
    # Append device name if specified
    if dump_device != None:
        final_name = final_name + dump_device
    # Will the name contain recursive?
    if rec_bool == True:
        final_name = final_name + "-recursive"
    # Finally, append extension
    final_name = final_name + ".xml"
    ET.ElementTree(root_elem).write(final_name, xml_declaration=True, encoding="utf-8")

def select_device(dev_list, dump_device, rec_bool):
    """
        Docstring
    """
    selected_devs = []
    for dev in dev_list:
        if dump_device in dev.name:
            selected_devs.append(dev)
            if rec_bool:
                break
    return selected_devs

def export_iterate(device_list, super_elems, master_root_elem):
    """
        :param list super_elems: List of super elements (under the root element)
    """
    # Define basic types
    disk_elems = []

    for dev in device_list:
        if hasattr(dev, "to_xml"):
            dev_name = str(type(dev)).split("'")[1]
            disk_elems.append(ET.SubElement(super_elems[0], dev_name.split(".")[-1]))
            disk_elems[-1].set("type", dev_name)
            disk_elems[-1].set("ObjectID", str(getattr(dev, "id")))
            dev._to_xml_init(master_root_elem, devices_list=device_list)
            dev.to_xml()

################################################################################
##### BASIC DEFINITION
class XMLUtils(util.ObjectID):
    def _to_xml_init(self, root_elem, devices_list=None, object_override=None,
                     parent_override=None, xml_done_ids=set()):
        """
            :param ET.Element root_elem: Root element of the XML file
            or not.
            :param object_override: This is object that is not in devicetree.
            :param set xml_done_ids: set of IDs that are done to prevent duplicates
        """
        self.xml_root_elem = root_elem
        self.xml_devices_list = devices_list
        self.device_elems = self.xml_root_elem[0]
        self.format_elems = self.xml_root_elem[1]
        self.intern_elems = self.xml_root_elem[2]
        self.xml_iterables = {list, tuple, dict, "collections.OrderedDict",
                              "blivet.devices.lib.ParentList"}

        # Determine, what object to parse
        if object_override is None:
            self.xml_object = self
        else:
            self.xml_object = object_override

        # Determine where to store new elements
        self.xml_parent_elem = parent_override
        if self.xml_parent_elem is None:
            self.xml_parent_elem = self.device_elems[-1]

        self.xml_elems_list = [] # Elements will be stored here
        self.xml_attrs_done = set() # To prevent duplicates in xml_elems_list
        self.xml_done_ids = xml_done_ids # As above, but for ids

        self.xml_attr_list = dir(self.xml_object) # List of attrs to gather

        # Subsection for allowed attributes and types
        self.xml_allowed_types = ["str", "int", "float", "set", "dict", "list",
                              "blivet.size.Size", "tuple", "bool", "NoneType",
                              "complex", "blivet.devices.",
                              "blivet.formats.", "blivet.devicelibs.",
                              "XMLFormat"]
        self.xml_unallowed_types = ["parted.", "LVMCacheStats"]
        self.xml_ign_attrs = ["passphrase", "xml", "abc", "dependencies", "dict",
                              "id"]

################################################################################
##### Check ignored
    def _to_xml_check_igns(self, in_attr):
        if in_attr.startswith("__") or\
            self._to_xml_check_xml_ign_attrs(in_attr) or\
            not self._to_xml_check_allowed_types() or\
            self._to_xml_check_ign_types() or\
            in_attr in self.xml_attrs_done:
            return True
        else:
            return False

    def _to_xml_check_ign_types(self):
        for ig_type in self.xml_unallowed_types:
            if ig_type in self.xml_tmp_str_type:
                return True
        return False

    def _to_xml_check_allowed_types(self):
        for al_type in self.xml_allowed_types:
            if al_type in self.xml_tmp_str_type:
                return True
        return False

    # Check ignored in set
    def _to_xml_check_xml_ign_attrs(self, in_attr):
        for ig_attr in self.xml_ign_attrs:
            if ig_attr in in_attr:
                return True
        return False

    def _to_xml_check_ids(self):
        self.xml_tmp_id = getattr(self.xml_object, "id")
        if self.xml_tmp_id in self.xml_done_ids:
            return True

################################################################################
##### List parsing
    def _to_xml_parse_iterables(self, list_obj=None,
                                par_elem=None):
        """
            Parses anything, that can be iterated
        """
        # Set basic, before we can start
        sublist = []
        if list_obj is None:
            list_obj = self.xml_tmp_obj
        if par_elem is None:
            par_elem = self.xml_elems_list[-1]

        for item in list_obj:
            sublist.append(ET.SubElement(par_elem, "item"))
            self._to_xml_get_data(in_obj=item)
            # Check for dict
            if type(list_obj) is dict:
                sublist[-1].set("attr", item)
                item = list_obj.get(item)

            elif isinstance(self.xml_tmp_obj, tuple):
                sublist[-1].set("type", self.xml_tmp_str_type)
                item = dict(item.__dict__)

            # Reload data type
            self._to_xml_get_data(in_obj=item)
            self._to_xml_set_data_type(sublist[-1])
            # Check for any iterable
            if self.xml_tmp_type in self.xml_iterables or self.xml_tmp_str_type in self.xml_iterables:
                self._to_xml_parse_iterables(list_obj=self.xml_tmp_obj, par_elem=sublist[-1])

            else:
                self._to_xml_set_value(sublist[-1])
                if hasattr(self.xml_tmp_obj, "to_xml") and self.xml_tmp_obj not in self.xml_devices_list:
                    self._to_xml_get_data(in_obj=self.xml_tmp_obj)
                    self._to_xml_parse_device()


################################################################################
##### Parsing objects, that are under devices (mostly formats), that have to_xml
    def _to_xml_parse_sub_to_xml(self, parse_override=False, obj_override=None):
        """
            Parses a object, that also has to_xml() method. Basically it runs
            to_xml() on object has it.
        """
        if obj_override is not None:
            self.xml_tmp_obj = obj_override
        self._to_xml_set_data_type(self.xml_elems_list[-1])
        self._to_xml_set_value(self.xml_elems_list[-1])
        self.tmp_full_name = str(type(self.xml_tmp_obj)).split("'")[1]

        if self.tmp_id not in self.xml_done_ids:
            self.xml_done_ids.add(self.tmp_id)

            # Import all required
            DeviceFormat = getattr(importlib.import_module("blivet.formats"), "DeviceFormat")
            Device = getattr(importlib.import_module("blivet.devices"), "Device")
            # For DeviceFormat
            if isinstance(self.xml_tmp_obj, DeviceFormat):
                self._to_xml_parse_format()
            # For Device
            elif isinstance(self.xml_tmp_obj, Device):
                return
            # Anything else
            else:
                self._to_xml_parse_object()
        # Skip it, when ID is in xml_done_ids
        else:
            pass

    def _to_xml_parse_object(self):
        """
            Similar to format, this does the same like parse_format, but for devices.
        """
        self.xml_elems_list[-1].text = None
        self.xml_elems_list[-1].set("type", self.tmp_full_name)
        self.xml_elems_list[-1].set("ObjectID", str(self.tmp_id))

        new_obj_init = getattr(self.xml_tmp_obj, "_to_xml_init")
        new_obj_init = new_obj_init(self.xml_root_elem,
                                        object_override=self.xml_tmp_obj,
                                        parent_override=self.xml_elems_list[-1],
                                        xml_done_ids=self.xml_done_ids)
        # Finally, start parsing
        getattr(self.xml_tmp_obj, "to_xml")()

    def _to_xml_parse_format(self):
        """
            Special section for DeviceFormat
        """
        # Start adding elements to format section
        self.xml_elems_list.append(ET.SubElement(self.format_elems,
                                                 self.tmp_full_name.split(".")[-1]))
        self.xml_elems_list[-1].set("type", self.tmp_full_name)
        self.xml_elems_list[-1].set("ObjectID", str(self.tmp_id))

        new_obj_init = getattr(self.xml_tmp_obj, "_to_xml_init")
        new_obj_init = new_obj_init(self.xml_root_elem,
                                    parent_override=self.format_elems[-1],
                                    xml_done_ids=self.xml_done_ids)
        # Finally, start parsing
        getattr(self.xml_tmp_obj, "to_xml")()

################################################################################
########### Special occasion of sub-to_xml
    def _to_xml_parse_device(self):
        """
            Special section for any other device, that is not in blivet.devices
        """
        # Get basic data and ID
        self.xml_tmp_id = getattr(self.xml_tmp_obj, "id")
        if self.xml_tmp_id in self.xml_done_ids:
            return
        self.xml_done_ids.add(self.xml_tmp_id)
        self.xml_elems_list.append(ET.SubElement(self.intern_elems, self.xml_tmp_str_type.split(".")[-1]))
        self.xml_elems_list[-1].set("type", self.xml_tmp_str_type)
        self.xml_elems_list[-1].set("ObjectID", str(self.xml_tmp_id))

        new_obj_init = getattr(self.xml_tmp_obj, "_to_xml_init")
        new_obj_init = new_obj_init(self.xml_root_elem,
                                    parent_override=self.intern_elems[-1],
                                    object_override=self.xml_tmp_obj,
                                    devices_list=self.xml_devices_list,
                                    xml_done_ids=self.xml_done_ids)
        # Finally, start parsing
        getattr(self.xml_tmp_obj, "to_xml")()


################################################################################
##### Set data
    def _to_xml_get_data(self, in_attrib=None, in_obj=None):
        """ This basically gets the object.
        """
        # Decide if it is already completed object or not
        if in_obj is not None:
            self.xml_tmp_obj = in_obj
        else:
            self.xml_tmp_obj = getattr(self.xml_object, in_attrib)

        self.xml_tmp_type = type(self.xml_tmp_obj)
        self.xml_tmp_str_type = str(self.xml_tmp_type).split("'")[-2]

    def _to_xml_set_value(self, par_elem):
        """
            This just sets the data's value into element text.
            If obj_override is True, the object is re-assigned back.
        """
        # Set this, because we need it for re-assigning.
        tmp_obj = None
        # Special condition for size
        if "Size" in self.xml_tmp_str_type:
            par_elem.set("Size", str(self.xml_tmp_obj))
            self.xml_tmp_obj = int(self.xml_tmp_obj)
        # Object that has ID
        elif hasattr(self.xml_tmp_obj, "id"):
            tmp_obj = self.xml_tmp_obj
            self.xml_tmp_obj = getattr(self.xml_tmp_obj, "id")
        par_elem.text = str(self.xml_tmp_obj)

        # Dirty trick: re-assign object back
        tmp_id = self.xml_tmp_obj
        self.xml_tmp_obj = tmp_obj
        self.tmp_id = tmp_id

    def _to_xml_set_data_type(self, par_elem):
        """
            This just sets the data's type converted in string, nothing else.
        """
        # Does it have ID?
        if hasattr(self.xml_tmp_obj, "id"):
            self.xml_tmp_str_type = "ObjectID"
        # Finally, set the type
        if par_elem.attrib.get("type") is None:
            par_elem.set("type", self.xml_tmp_str_type)

################################################################################
##### Base element appending
    def _to_xml_base_elem(self, in_attrib):
        self.xml_elems_list.append(ET.SubElement(self.xml_parent_elem, "prop"))
        self.xml_elems_list[-1].set("attr", in_attrib)

################################################################################
##### EXPORT FUNCTION
    def to_xml(self):
        """
            This is the main function, that does the export.
            All of the above are subfunctions / methods, that are used by to_xml().
        """
        for attr in self.xml_attr_list:
            try:
                # Temporaily get str_type
                tmp_obj = getattr(self.xml_object, attr)
                self.xml_tmp_str_type = str(type(tmp_obj)).split("'")[-2]
                # Check, if it is allowed attrib or not
                if self._to_xml_check_igns(attr):
                    continue
                # Basic fix - replace all underscore attrs with non-underscore
                if attr.startswith("_") and hasattr(self.xml_object, attr[1:]):
                    attr = attr[1:]
                # Add to completed attributes, so we can avoid duplicates. Also add ids
                self.xml_attrs_done.add(attr)
                # Temporaily get object
                self._to_xml_get_data(attr)
                # Create basic element
                self._to_xml_base_elem(attr)
                # Set basic data to element
                self._to_xml_set_data_type(self.xml_elems_list[-1])

                # Anything that can be iterated
                if (self.xml_tmp_type in self.xml_iterables and self.xml_tmp_obj is not None) or\
                ("ParentList" in self.xml_tmp_str_type and self.xml_tmp_obj is not None):
                    self._to_xml_parse_iterables(self.xml_tmp_obj)

                elif hasattr(self.xml_tmp_obj, "to_xml"):
                    self._to_xml_parse_sub_to_xml()

                # Normal attribute
                else:
                    self._to_xml_set_value(self.xml_elems_list[-1])

            except Exception as e:
                check_issue = str(e)
                if "unreadable attribute" in check_issue or\
                    "can only be accessed" in check_issue:
                    continue
                #else:
                    #print (e, attr, self.xml_tmp_obj)
                    #print("TRACEBACK")
                    #traceback.print_tb(e.__traceback__)

    def _getdeepattr(self, obj, name):
        """This behaves as the standard getattr, but supports
           composite (containing dots) attribute names.

           As an example:

           >>> import os
           >>> from os.path import split
           >>> getdeepattr(os, "path.split") == split
           True
        """

        for attr in name.split("."):
            obj = getattr(obj, attr)
        return obj

    def _hasdeepattr(self, obj, name):
        """
            This behaves like getdeepattr, but returns a booolean if True or False if not.
            Implementation by kvalek@redhat.com, inspired by getdeepattr

            This is stand-alone version, original method version used in blivet/util.py, as part of to_xml() project.

            Example (done in ipython3)
            dap2._hasdeepattr(dap2, "parents.items")
            True
        """

        for attr in name.split("."):
            try:
                obj = getattr(obj, attr)
            except AttributeError:
                return False
        return True

################################################################################
###################### IMPORT FUNCTIONS ########################################
###################### BASIC INITIALIZATION ####################################
class FromXML(object):
    def __init__(self, xml_file):
        """
            Basic initialization
        """
        super(FromXML, self).__init__()

        # Get master trees
        self.fxml_tree_devices = ET.parse(xml_file).getroot()[0]
        self.fxml_tree_formats = ET.parse(xml_file).getroot()[1]
        self.fxml_tree_interns = ET.parse(xml_file).getroot()[2]
        # Lists to store devices to - Preparation
        self.fxml_devices = []
        self.fxml_formats = []
        self.fxml_interns = []
        # Little optimalization: use dict to get object if its imported already
        self.fulltypes_stack = {}

    def from_xml(self):
        """
            Populates a list with tuple containing class name and populated
            dictionary.
        """
        pass

################################################################################
################# TOOL FUNCIONS ################################################
    def _fxml_get_elem_data(self, in_elem):
        """
            Gets all information from a element.
            :param ET.Element in_elem: Element to "parse"
        """
        self.fxml_tmp_value = in_elem.text
        self.fxml_tmp_type_str = in_elem.attrib.get("type")
        self.fxml_tmp_attr = in_elem.attrib.get("attr")
        self.fxml_tmp_id = in_elem.text
        self.fxml_tmp_element = in_elem

    def _fxml_get_module(self):
        """
            Reconstructs the class based on type
            Returns: class
        """
        # Try to get type, if it is already in types dictionary
        tmp_type = self.fulltypes_stack.get(self.fxml_tmp_type_str)
        if tmp_type is not None:
            self.fxml_tmp_type = tmp_type
        else:
            # If it fails, create one
            tmp_imp_path = ""

            # Iterate through the "fulltype" and get all that is everyhing before
            # last dot. Also, make correct path
            for mod_str in range(len(self.fxml_tmp_type_str.split(".")) - 1):
                if tmp_imp_path == "":
                    tmp_imp_path = self.fxml_tmp_type_str.split(".")[0]
                else:
                    tmp_imp_path = tmp_imp_path + "." + self.fxml_tmp_type_str.split(".")[mod_str]
            # Create the class itself
            tmp_mod_name = self.fxml_tmp_type_str.split(".")[-1]
            # Create a tempovary object that we store later in fulltypes_stack
            tmp_class_obj = getattr(importlib.import_module(tmp_imp_path), tmp_mod_name)
            self.fulltypes_stack.update({tmp_type: tmp_class_obj})
            self.fxml_tmp_obj = tmp_class_obj

# We want special class just for processing.
# The reason is that we want shared information we read from FromXML.
class FXMLProcess(FromXML):
    def __init__(self, parent_override=None, dest_override=None):
        """
            Docstring
        """
        # Define where to parse from
        self.fxml_source_list = parent_override
        if self.fxml_source_list is None:
            self.fxml_source_list = self.fxml_tree_devices
        # Define where to store
        self.fxml_dest_list = dest_override
        if self.fxml_dest_list is None:
            self.fxml_dest_list = self.fxml_devices

    # TODO: DODELAT, mas novou architekturu, viz poznamky na papire




################################################################################
################# Iterating ####################################################
    def _fxml_test_parse_one(self):
        """
            Debug ONLY: Gets specified object and performs full parse
        """
        TEST_CONSTANT = "./DiskDevice"

        if self.parent_override is None:
            self.fxml_source_list = self.fxml_tree_devices
        if self.dest_override is None:
            self.fxml_dest_list = self.fxml_devices

        test_elem = self.fxml_source_list.find(TEST_CONSTANT)
        self._fxml_get_elem_data(test_elem)
        self._fxml_determine_type()
        self.fxml_dest_list.append({"class": self.fxml_tmp_obj})
        self.fxml_dest_list[-1].update({"ObjectID": self.fxml_tmp_id})
        self._fxml_iterate_element(test_elem)
        self._fxml_finalize_object()

    def _fxml_iterate_tree(self):
        """
            docstring
        """
        for elem in self.fxml_source_list:
            # Parses all possible data from elem and determine type
            self._fxml_get_elem_data(elem)
            self._fxml_determine_type()


    def _fxml_iterate_element(self, in_elem):
        for elem in in_elem:
            self._fxml_get_elem_data(elem)
            self._fxml_determine_type()
            self.fxml_dest_list[-1].update({self.fxml_tmp_attr: self.fxml_tmp_value})


################################################################################
################# Type parsing #################################################
    def _fxml_set_type_simple(self):
        """
            Type, that is simple and does not need anything else
        """
        # Define simple types and values
        simple_types = {"int": int, "float": float} # Note: str missing intentionally, parsed by default.
        simple_values = {"True": True, "False": False}

        if simple_types.get(self.fxml_tmp_type_str) is not None:
            tmp_type = simple_types.get(self.fxml_tmp_type_str)
            self.fxml_tmp_value = tmp_type(self.fxml_tmp_value)
        elif "str" in self.fxml_tmp_type_str:
            return
        else:
            self.fxml_tmp_value = simple_values.get(self.fxml_tmp_value)

    def _fxml_set_type_iterable(self, in_elem=None):
        """
            Any iterable type
        """
        list_objects = {"list": list(), "dict": dict(), "set": set(), "tuple": []}
        list_elem = list_objects.get(self.fxml_tmp_type_str)
        if in_elem is None:
            in_elem = self.fxml_tmp_element

        # Save attribute for later use, because we are going to refresh it in loop
        tmp_attr = self.fxml_tmp_attr
        tmp_type_decide = self.fxml_tmp_type_str

        for elem in in_elem:
            # Get basic data about the element
            self._fxml_get_elem_data(elem)
            self._fxml_determine_type()

            if type(list_elem) is list:
                list_elem.append(self.fxml_tmp_value)
            elif type(list_elem) is dict:
                list_elem.update({self.fxml_tmp_attr: self.fxml_tmp_value})
            elif type(list_elem) is set:
                list_elem.add(self.fxml_tmp_value)

        # Decide if it was tuple, or not
        if tmp_type_decide == "tuple":
            list_elem = tuple(list_elem)
        # Finally, assign previous atribute and completed value
        self.fxml_tmp_attr = tmp_attr
        self.fxml_tmp_value = list_elem


    def _fxml_set_type_complex(self):
        """
            Any type, that is complex - has a dot in it
        """
        self._fxml_get_module()

        # TODO: Implement
        if "size.Size" in self.fxml_tmp_type_str:
            self.fxml_tmp_value = self.fxml_tmp_obj(int(self.fxml_tmp_value))

    def _fxml_set_obj_id(self):
        """
            Docstring
        """
        for item in self.fxml_source_list:
            if item.get(self.fxml_tmp_id) is not None:
                self.fxml_tmp_value = item.get(self.fxml_tmp_id)
                return

        tmp = self.fxml_tree_root.find(".//*[@ObjectID='%s']" % (self.fxml_tmp_id))
        if "format" in tmp.attrib.get("type"):
            format_instance = FromXML(parent_override=self.fxml_tree_formats,
                                      dest_override=self.fxml_formats,
                                      el_devices=self.fxml_tree_devices,
                                      el_formats=self.fxml_tree_formats,
                                      el_interns=self.fxml_tree_interns,
                                      list_devices=self.fxml_devices,
                                      list_formats=self.fxml_formats,
                                      list_interns=self.fxml_interns,
                                      fulltypes=self.fulltypes_stack)


    def _fxml_determine_type(self):
        """
            Determine type to correctly assign it
        """
        iterables = {"list", "dict", "tuple"}
        simples = {"str", "int", "float", "bool"}
        # Dots are special, check them indenpentently
        if self.fxml_tmp_type_str in simples:
            self._fxml_set_type_simple()
        elif self.fxml_tmp_type_str in iterables:
            self._fxml_set_type_iterable()
        elif "." in self.fxml_tmp_type_str:
            self._fxml_set_type_complex()
        elif "ObjectID" in self.fxml_tmp_type_str:
            self._fxml_set_obj_id()

################################################################################
################# Final initialization #########################################
    def _fxml_finalize_object(self):
        tmp_obj = self.fxml_dest_list[-1].get("class")
        tmp_obj.__init_xml__(self.fxml_dest_list[-1])

"""

    def _fxml_get_elem_data(self, elem, parent=False):

            :param ET.Element elem: Element to gather data from
            Gets all data from ET.Element.

        if parent:
            self.fxml_elem_current = elem # This is the element we are working on currently
            self.fxml_elem_attrib = elem.attrib
        else:
            self.fxml_elem_attrib = elem.attrib.get("attr")
            self.fxml_elem_type = elem.attrib.get("type")
        self.fxml_elem_value = elem.text

    def _fxml_assign_attrib(self):

            This does following: gets attribute name from element and assigns
            value from elem.text.

        if "." not in self.fxml_elem_type and self.fxml_elem_type not in self.fxml_iterables:
            self._fxml_get_simple_type()
            self.obj_elements[-1].update(\{self.fxml_elem_attrib: self.fxml_elem_value\})
        else:
            self.obj_elements[-1].update(\{self.fxml_elem_attrib: None\})

################################################################################
################# ITERATE FUNCIONS #############################################
    def _fxml_iterate_tree(self):

            Iterate through the tree to get all elements.


        for elem in self.obj_root:
            self._fxml_get_elem_data(elem, True)
            self._fxml_parse_module()

            # Special - append class and id to dictionary
            self.obj_elements.append({"fxml_class": self.fulltypes_stack.get(self.fxml_elem_attrib.get("type")),
                                     "xml_id": self.fxml_elem_attrib.get("ObjectID")})
            # Start parsing the attributes
            self._fxml_iterate_object()


    def _fxml_iterate_object(self):
        for elem in self.fxml_elem_current:
            self._fxml_get_elem_data(elem)
            self._fxml_assign_attrib()

################################################################################
################# ATTRIBUTE TYPING FUNCIONS ####################################
    def _fxml_get_simple_type(self):

            This function basically determines, what kind of type the value will be.

        ## Define basic types
        basic_types =
        basic_values =
        none_type = {"None": None}

        tmp_type = basic_types.get(self.fxml_elem_type)
        tmp_val = basic_values.get(self.fxml_elem_value)
        # First get anything that is str
        if self.fxml_elem_type == "str":
            return
        else:
            if tmp_val is not None:
                self.fxml_elem_value = tmp_val
            elif tmp_type is not None:
                self.fxml_elem_value = tmp_type(self.fxml_elem_value)
            else:
                self.fxml_elem_value = None

    def _fxml_get_iterable_type(self):
        pass

################################################################################
################# PARSING FUNCIONS #############################################
    def _obsolete_fxml_parse_basic_list(self, in_elem_list):

            This function gets an element that is a list. It loops trough it and
            returns just list filled (or empty) with values that are subelements

        temp_list = []

        for inc in in_elem_list:
            if inc == None:
                return temp_list
            else:
                tmp_val = in_elem_list.attrib.get("attr")
                if tmp_val == "parents" or tmp_val == "members":
                    temp_list.append(int(inc.text))
                else:
                    temp_list.append(self._obsolete_fxml_parse_value(inc))
        return temp_list

    def _obsolete_fxml_parse_value(self, in_elem, in_list = None, index = None):

            Gets the data out of attr="" and <tag>VALUE</tag>. It basically determines
            if its a basic typed value or complex value.



        ## Define advanced attributes like parents, we want to skip them at the beginning
        par_typed_attrs = ["parents", "ancestors", "members"]

        tmp_attr_type = in_elem.attrib.get("type")

        ## Parse string by default
        if tmp_attr_type == "str":
            res_value = in_elem.text

        ## Parse ints and floats
        elif tmp_attr_type in basic_types.keys():
            res_value = basic_types.get(tmp_attr_type)(in_elem.text)

        else:
            ## Parse "static" values
            if in_elem.text in basic_values.keys():
                res_value = basic_values.get(in_elem.text)

            ## Basic list
            elif "list" in in_elem.tag and in_elem.attrib.get("attr") not in par_typed_attrs:
                res_value = self._obsolete_fxml_parse_basic_list(in_elem)

            ## RAID levels. We want them as strings.
            elif in_elem.attrib.get("attr") == "level":
                res_value = in_elem.text

            ## Complicated types, Size first
            elif "." in tmp_attr_type and "Size" in tmp_attr_type:
                mod_path, mod_name = self._obsolete_fxml_parse_module(None, tmp_attr_type)
                res_value = getattr(importlib.import_module(mod_path), mod_name)(value = int(in_elem.text))

            ## ParentList
            elif "." in tmp_attr_type and "ParentList" in tmp_attr_type or in_elem.attrib.get("attr") in par_typed_attrs[1:]:
                mod_path, mod_name = self._obsolete_fxml_parse_module(None, tmp_attr_type)
                res_value = self._obsolete_fxml_parse_basic_list(in_elem)
                res_value = self._obsolete_fxml_get_parent_obj(in_list, res_value)

            else:
                res_value = None

        return res_value

    def _obsolete_fxml_parse_attrs(self, in_master_list, in_elem, index):

            This basically walks trough element tree and updates dictionary with
            attributes.

        ## Firstly, define what we want to skip for first time
        ignored_attrs = ["fulltype"]

        for inc in in_elem:
            ## Dissasemble tuple into simpler objects
            temp_obj_str = in_master_list[index][0]
            temp_dict = in_master_list[index][1]
            ## Ignore certain attributes
            if inc.tag in ignored_attrs:
                continue
            elif inc.tag == "Child_ID":
                attr_value = self._obsolete_fxml_get_child_id(int(inc.text))
                #attr_value = self.format_list[index][-1]
            else:
                attr_value = self._obsolete_fxml_parse_value(inc, in_master_list, index)
            temp_dict.update({inc.attrib.get("attr"): attr_value})

            ## Reassemble afterwards
            in_master_list[index] = (temp_obj_str, temp_dict)

    def _obsolete_fxml_get_child_id(self, in_id):
        for inc in self.format_list:
            if in_id == inc[1].get("xml_id"):
                return inc[2]

################################################################################
################# INIT FUNCIONS ################################################
    def _obsolete_fxml_init_class(self, in_master_list, list_index, forced_obj):

            This finally intializes class object

        temp_obj_str = in_master_list[list_index][0]
        temp_obj_dict = in_master_list[list_index][1]
        mod_path, mod_name = self._obsolete_fxml_parse_module(None, temp_obj_str)

        ## Get name, because its general for all
        obj_name = temp_obj_dict.get("name")
        obj_arg_dict = {}

        arg_list = getfullargspec(getattr(importlib.import_module(mod_path),
                                          mod_name).__init__)[0][2:]
        if forced_obj == "Format":
            temp_obj = getattr(importlib.import_module(mod_path),
                               mod_name)(exists = temp_obj_dict.get("exists"),
                                         options = temp_obj_dict.get("options"),
                                         uuid = temp_obj_dict.get("uuid"),
                                         create_options = temp_obj_dict.get("create_options"))
            in_master_list[list_index] = (temp_obj_str, temp_obj_dict, temp_obj)

        elif "BTRFS" in forced_obj:
            temp_obj = getattr(importlib.import_module(mod_path),
                               mod_name)(parents = temp_obj_dict.get("parents"),
                                         exists = temp_obj_dict.get("exists"))
            self.devicetree._add_device(temp_obj)
            in_master_list[list_index] = (temp_obj_str,
                                          temp_obj_dict,
                                          temp_obj)

        else:
            for inc in arg_list:
                if inc == "fmt":
                    obj_arg_dict.update({"fmt": self.format_list[list_index][-1]})
                elif inc == "maxsize":
                    obj_arg_dict.update({inc: temp_obj_dict.get("max_size")})
                elif inc == "grow":
                    obj_arg_dict.update({inc: temp_obj_dict.get("growable")})
                elif inc == "primary":
                    obj_arg_dict.update({inc: temp_obj_dict.get("is_primary")})
                elif inc == "xml_import":
                    obj_arg_dict.update({"xml_import": True})
                elif inc == "xml_dict":
                    obj_arg_dict.update({"xml_dict": temp_obj_dict})
                else:
                    obj_arg_dict.update({inc: temp_obj_dict.get(inc)})

            ## Finally, Init it
            if temp_obj_dict.get("name") not in self.completed_devices:
                temp_obj = getattr(importlib.import_module(mod_path),
                                   mod_name)(obj_name, **obj_arg_dict)
                if hasattr(temp_obj, "_obsolete_fxml_set_attrs"):
                    temp_obj._obsolete_fxml_set_attrs(temp_obj_dict, arg_list)
                self.devicetree._add_device(temp_obj)
                in_master_list[list_index] = (temp_obj_str, temp_obj_dict, temp_obj)
                self.completed_devices.append(temp_obj.name)

################################################################################
################# BASIC LOOP FUNCIONS ##########################################
    def _obsolete_fxml_loop_trough(self, in_master_list, in_master_elem, forced_obj):

            This function does the hard work - decides upon forced_obj to get
            specific object from in_master_list to set attributes on.

        counter = 0
        for inc in in_master_list:
            ## "disassemble" object into simpler, get name in this instance
            temp_name = inc[0]
            temp_dict = inc[1]
            if forced_obj in temp_name.split(".")[-1] or forced_obj == "Format":
                list_index = in_master_list.index(inc)
                self._obsolete_fxml_parse_attrs(in_master_list, in_master_elem[list_index], list_index)
                self._obsolete_fxml_init_class(in_master_list, list_index, forced_obj)
            else:
                continue

            counter += 1

    def _obsolete_fxml_get_basenames(self, in_master_elem, in_master_list):

            This function will get basic names of the elements. This name can be
            parsed into modules.

        for inc in in_master_elem:
            in_master_list.append((inc[0].text, \{\}))
            in_master_list[-1][1].update({"name": inc.attrib.get("name")})
            in_master_list[-1][1].update({"xml_id": int(inc.attrib.get("id"))})
################################################################################
################################################################################
"""
