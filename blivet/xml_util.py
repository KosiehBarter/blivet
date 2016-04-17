from . import util
import xml.etree.ElementTree as ET
from socket import gethostname
import importlib
from collections import namedtuple
import inspect

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
    dev_counter = 0

    for dev in device_list:
        if hasattr(dev, "to_xml"):
            dev_name = str(type(dev)).split("'")[1]
            disk_elems.append(ET.SubElement(super_elems[0], dev_name.split(".")[-1]))
            disk_elems[-1].set("type", dev_name)
            disk_elems[-1].set("ObjectID", str(getattr(dev, "id")))
            dev._to_xml_init(master_root_elem, devices_list=device_list)
            dev.to_xml()
            dev_counter = dev_counter + 1
    super_elems[0].set("Count", str(dev_counter))


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
                              "id", "_levels"]

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
                sublist[-1].set("enforced", str(type(item)).split("'")[-2])

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
        # Just a small tweak, count it
        tmp_count = self.format_elems.attrib.get("Count")
        if tmp_count is not None:
            tmp_count = int(tmp_count) + 1
        else:
            tmp_count = 1
        self.format_elems.set("Count", str(tmp_count))
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
####################### IMPORT FUNCTIONS #######################################
class FromXML(object):
    def __init__(self, xml_file, devicetree):
        """
            Basic initialization
        """
        super(FromXML, self).__init__()

        # TODO: Predelat na XPath
        # Get master trees
        self.fxml_tree_root = ET.parse(xml_file).getroot()
        self.fxml_tree_devices = self.fxml_tree_root[0]
        self.fxml_tree_formats = self.fxml_tree_root[1]
        self.fxml_tree_interns = self.fxml_tree_root[2]
        # Lists to store devices to - Preparation
        # TODO: primo do devicetree
        self.ids_done = {} # ID = klic, hodnota = hotovy bliveti objekt
        # Little optimalization: use dict to get object if its imported already
        self.fulltypes_stack = {}
        # Define devicetree / populator
        self.devicetree = devicetree

############ ITERATION #########################################################
    def from_xml(self):
        """
            Parses element from device. Creates a class for device and prepares
            basic parsing.
        """
        # TEST OVERRIDE
        #self.fxml_tree_devices = self.fxml_tree_root.findall(".//LVMVolumeGroupDevice")

        for dev_elem in self.fxml_tree_devices:
            tempovary_dict = {} # Create a tempovary dictionary to store data
            # We just need 2 values, ID and type.
            tmp_str_type = dev_elem.attrib.get("type")
            tmp_id = dev_elem.attrib.get("ObjectID")
            # We know that it is complex type with dot
            tmp_obj = self._fxml_get_module(tmp_str_type)
            tempovary_dict["class"] = tmp_obj
            tempovary_dict["XMLID"] = tmp_id
            # Parse Device's attributes
            complete_object = self.from_xml_internal(dev_elem, tempovary_dict)
            self._fxml_check_device_tree(tempovary_dict, complete_object)

    def from_xml_internal(self, dev_elem, tempovary_dict, ret_bool=False):
        """
            This function walks through the elements and parses them.
        """
        # Not to be confused, we are walking through device's elems
        for attr_elem in dev_elem:
            # Get all possible basic data.
            tmp_attrib = attr_elem.attrib.get("attr")
            tmp_str_type = attr_elem.attrib.get("type")
            # Asign list to ignored attribute
            if tmp_str_type == "list" and tmp_attrib != "parents"\
                or tmp_attrib == "raw_device":
                tmp_value = []
            # Process other attributes if not
            else:
                tmp_value = self._fxml_determine_type(attr_elem)
            tempovary_dict[tmp_attrib] = tmp_value

        complete_object = self._fxml_finalize_object(tempovary_dict)
        # If we need to return the object back
        return complete_object

################## Type parsing #################################################
    def _fxml_process_simple(self, in_elem):
        """
            Processes simple values
        """
         # Define simple types and values
        simple_types = {"int": int, "float": float} # Note: str missing intentionally, parsed by default.
        simple_values = {"True": True, "False": False}
        # "unpack" the element
        tmp_str_type = in_elem.attrib.get("type")
        tmp_value = in_elem.text
        # First check type instances
        if simple_types.get(tmp_str_type) is not None:
            tmp_type = simple_types.get(tmp_str_type)
            tmp_value = tmp_type(tmp_value)
        elif "str" in tmp_str_type:
            # Special override for empty text
            if tmp_value is None:
                tmp_value = ""
            else:
                pass
        elif "." in tmp_str_type:
            tmp_value = in_elem.text
        else:
            tmp_value = simple_values.get(tmp_value)
        return tmp_value

    def _fxml_process_iterables(self, in_elem):
        """
            Any iterable type
        """
        # Define basics
        list_objects = {"list": list(), "dict": dict(), "set": set(), "tuple": list()}
        list_attribs = {"parents": list()}
        # Unpack element
        tmp_str_type = in_elem.attrib.get("type")
        tmp_attr = in_elem.attrib.get("attr")
        # Assign types
        list_object = list_objects.get(tmp_str_type)
        if list_object is None:
            list_object = list_attribs.get(tmp_attr)

        # Finally, start iterating
        for item_elem in in_elem: # Not to be confused, this element has children
            tmp_value = self._fxml_determine_type(item_elem)

            # Determine, which type of list to use
            if type(list_object) is list:
                list_object.append(tmp_value)
            elif type(list_object) is dict:
                lst_tmp_attr = item_elem.attrib.get("attr")
                list_object[lst_tmp_attr] = tmp_value
            elif type(list_object) is set:
                list_object.add(tmp_value)

        # Post-loop check for tuple
        if tmp_str_type == "tuple":
            tmp_value = tuple(list_object)
        return list_object

    def _fxml_process_complex(self, elem):
        """
            This processes any attribute, that is complex, ie has a dot in it.
        """
        tmp_str_type = elem.attrib.get("type")
        tmp_value = elem.text
        tmp_obj = self._fxml_get_module(tmp_str_type)
        # Special override for Size
        if "Size" in tmp_str_type:
            tmp_value = tmp_obj(int(tmp_value))
        else:
            tmp_enforced_type = elem.attrib.get("enforced")
            if tmp_enforced_type is not None:
                elem.set("type", tmp_enforced_type)
            tmp_dict = self._fxml_determine_type(elem)
            tmp_value = tmp_obj(**tmp_dict)

        return tmp_value

    def _fxml_process_object(self, elem):
        """
            Gets and parses object from given ID.
        """
        # Get ID first, then element
        tmp_id = elem.text
        # First, check if we already have the ID we want
        tmp_value = self.ids_done.get(tmp_id)
        if tmp_value is None:
            tmp_element = self.fxml_tree_root.find(".//*[@ObjectID='%s']" % (tmp_id))
            # Get object's type and parse it
            tmp_obj_type = tmp_element.attrib.get("type")
            tmp_obj = self._fxml_get_module(tmp_obj_type)
            # Create a dictionary for attributes
            tmp_dict = {"class": tmp_obj}
            tmp_dict["XMLID"] = tmp_id
            # Parse attributes to dict
            complete_obj = self.from_xml_internal(tmp_element, tmp_dict)
            self.ids_done[tmp_id] = complete_obj
            tmp_value = complete_obj
            self._fxml_check_device_tree(tmp_dict, tmp_value)
        else:
            tmp_value = self.ids_done.get(tmp_id)
        # At the end, do a devicetree check.
        return tmp_value

    def _fxml_determine_type(self, in_elem):
        """
            Decides, which subfunction to correctly type the attribute will be used
        """
        # Define basics first
        iterables = {"list", "dict", "tuple"}
        simples = {"str", "int", "float", "bool"}
        # unpack element
        tmp_str_type = in_elem.attrib.get("type")

        tmp_attr = in_elem.attrib.get("attr")
        if tmp_attr is None:
            tmp_attr = "dummy"

        if tmp_str_type in simples or "blivet.devicelibs" in tmp_str_type:
            tmp_value = self._fxml_process_simple(in_elem)
        elif tmp_str_type in iterables or "parents" in tmp_attr:
            tmp_value = self._fxml_process_iterables(in_elem)
        elif "." in tmp_str_type and "blivet.devicelibs" not in tmp_str_type:
            tmp_value =  self._fxml_process_complex(in_elem)
        elif tmp_str_type == "ObjectID":
            tmp_value = self._fxml_process_object(in_elem)
        else:
            tmp_value = None

        return tmp_value

################################################################################
########### Tool functions #####################################################
    def _fxml_finalize_object(self, in_dict):
        """
            From input dictionary, gets a object and initializes it
        """
        tmp_obj = in_dict.get("class")
        tmp_value = tmp_obj.__init_xml__(in_dict)
        return tmp_value

    def _fxml_check_device_tree(self, in_dict, in_obj):
        """
            Uses ObjectID to check from which segment was device loaded
        """
        tmp_id = in_dict.get("XMLID")
        result = self.fxml_tree_root.find(".//*[@ObjectID='%s']/.." % (tmp_id)).tag
        if result == "Devices":
            self.devicetree._add_device(in_obj)

    def _fxml_get_module(self, tmp_str_type):
        """
            Reconstructs the class based on type
            Returns: class
        """
        # Try to get type, if it is already in types dictionary
        tmp_type = self.fulltypes_stack.get(tmp_str_type)
        if tmp_type is not None:
            return tmp_type
        else:
            # If it fails, create one
            tmp_imp_path = ""

            # Iterate through the "fulltype" and get all that is everyhing before
            # last dot. Also, make correct path
            for mod_str in range(len(tmp_str_type.split(".")) - 1):
                if tmp_imp_path == "":
                    tmp_imp_path = tmp_str_type.split(".")[0]
                else:
                    tmp_imp_path = tmp_imp_path + "." + tmp_str_type.split(".")[mod_str]
            # Create the class itself
            tmp_mod_name = tmp_str_type.split(".")[-1]
            # Create a tempovary object that we store later in fulltypes_stack
            tmp_class_obj = getattr(importlib.import_module(tmp_imp_path), tmp_mod_name)
            self.fulltypes_stack.update({tmp_str_type: tmp_class_obj})
            return tmp_class_obj


#    def from_xml(self):
#        """
#            Docstring
#        """
#        for dev_elem in self.fxml_tree_devices:
#            tmp_value, tmp_type_str, tmp_attr,\
#            tmp_id, tmp_origin, tmp_obj = self._fxml_get_elem_data(dev_elem)
#            self._fxml_get_module()
#            device_dict = {"class": self.fxml_tmp_obj}
#            self.from_xml_internal(dev_elem, device_dict)
#            self.fxml_devices.append(device_dict)
#            pdb.set_trace()
#            self.devicetree.add_device(final_obj)
#
#
#    def from_xml_internal(self, in_elem, in_dict):
#        """
#            Docstring
#        """
#        post_enforced = {"children", "ancestors"}
#        attrib_stack = []
#
#        # TODO: NEJAK VYRESIT attrib_stack, aby bezel az na konci
#        # NERESIT children a ancestors
#
#        for attr_elem in in_elem:
#            self._fxml_get_elem_data(attr_elem)
#            if self.fxml_tmp_attr not in post_enforced:
#                self._fxml_determine_type(attr_elem)
#                in_dict[self.fmxl_tmp_attr] = self.fxml_tmp_value
#            else:
#                attrib_stack.append(attr_elem)
#                continue
#
##################################################################################
################### TOOL FUNCIONS ################################################
#    def _fxml_get_elem_data(self, in_elem):
#        """
#            Gets all information from a element.
#            :param ET.Element in_elem: Element to "parse"
#        """
#        fxml_tmp_value = in_elem.text
#        fxml_tmp_type_str = in_elem.attrib.get("type")
#        fxml_tmp_attr = in_elem.attrib.get("attr")
#        fxml_tmp_id = in_elem.text
#        fxml_tmp_origin = in_elem.get("origin")
#        fxml_tmp_obj = None
#        # Nepouzivat globalni / sdilene,duvod: rekurze
#        return (fxml_tmp_value,
#                fxml_tmp_type_str,
#                fxml_tmp_attr,
#                fxml_tmp_id,
#                fxml_tmp_origin,
#                fxml_tmp_obj)
#

#
#################################################################################


#
#

#
#    def _fxml_get_object(self):
#        # TODO: Podminka pro preskakovani, kdyz je hotovo, jinak nacti
#        # if <podminka>
#        # Zde prijde hledani rodice / formatu
#        obj_elem = self.fxml_tree_root.find(".//*[@ObjectID='%s']" % (self.fxml_tmp_id))
#        obj_dict = {}
#
#        # Finally, start parsing
#        self.from_xml_internal(obj_elem, obj_dict)
#        #print (obj_elem, obj_elem.attrib.get("ObjectID"))
#
#    def _fxml_determine_type(self, in_elem):
#        """
#            Determine type to correctly assign it
#        """

#        # Dots are special, check them indenpentently
#        if self.fxml_tmp_type_str in simples:
#            self._fxml_set_type_simple()
#        elif self.fxml_tmp_type_str in iterables or self.fxml_tmp_attr == "parents":
#            self._fxml_set_type_iterable(in_elem)
#        elif "." in self.fxml_tmp_type_str and "ParentList" not in self.fxml_tmp_type_str:
#            self._fxml_set_type_complex()
#        elif "ObjectID" in self.fxml_tmp_type_str:
#            self._fxml_get_object()
#
##################################################################################
################### Final initialization #########################################
#    def _fxml_finalize_object(self):
#        tmp_obj = self.fxml_dest_list[-1].get("class")
#        final_obj = tmp_obj.__init_xml__(self.fxml_dest_list[-1])
#        #self.ids_done[ # TODO: Resit lokalne ID]
#        return final_obj
#
#
##
##"""
##
##    def _fxml_get_elem_data(self, elem, parent=False):
##
##            :param ET.Element elem: Element to gather data from
##            Gets all data from ET.Element.
##
##        if parent:
##            self.fxml_elem_current = elem # This is the element we are working on currently
##            self.fxml_elem_attrib = elem.attrib
##        else:
##            self.fxml_elem_attrib = elem.attrib.get("attr")
##            self.fxml_elem_type = elem.attrib.get("type")
##        self.fxml_elem_value = elem.text
##
##    def _fxml_assign_attrib(self):
##
##            This does following: gets attribute name from element and assigns
##            value from elem.text.
##
##        if "." not in self.fxml_elem_type and self.fxml_elem_type not in self.fxml_iterables:
##            self._fxml_get_simple_type()
##            self.obj_elements[-1].update(\{self.fxml_elem_attrib: self.fxml_elem_value\})
##        else:
##            self.obj_elements[-1].update(\{self.fxml_elem_attrib: None\})
##
##################################################################################
################### ITERATE FUNCIONS #############################################
##    def _fxml_iterate_tree(self):
##
##            Iterate through the tree to get all elements.
##
##
##        for elem in self.obj_root:
##            self._fxml_get_elem_data(elem, True)
##            self._fxml_parse_module()
##
##            # Special - append class and id to dictionary
##            self.obj_elements.append({"fxml_class": self.fulltypes_stack.get(self.fxml_elem_attrib.get("type")),
##                                     "xml_id": self.fxml_elem_attrib.get("ObjectID")})
##            # Start parsing the attributes
##            self._fxml_iterate_object()
##
##
##    def _fxml_iterate_object(self):
##        for elem in self.fxml_elem_current:
##            self._fxml_get_elem_data(elem)
##            self._fxml_assign_attrib()
##
##################################################################################
################### ATTRIBUTE TYPING FUNCIONS ####################################
##    def _fxml_get_simple_type(self):
##
##            This function basically determines, what kind of type the value will be.
##
##        ## Define basic types
##        basic_types =
##        basic_values =
##        none_type = {"None": None}
##
##        tmp_type = basic_types.get(self.fxml_elem_type)
##        tmp_val = basic_values.get(self.fxml_elem_value)
##        # First get anything that is str
##        if self.fxml_elem_type == "str":
##            return
##        else:
##            if tmp_val is not None:
##                self.fxml_elem_value = tmp_val
##            elif tmp_type is not None:
##                self.fxml_elem_value = tmp_type(self.fxml_elem_value)
##            else:
##                self.fxml_elem_value = None
##
##    def _fxml_get_iterable_type(self):
##        pass
##
##################################################################################
################### PARSING FUNCIONS #############################################
##    def _obsolete_fxml_parse_basic_list(self, in_elem_list):
##
##            This function gets an element that is a list. It loops trough it and
##            returns just list filled (or empty) with values that are subelements
##
##        temp_list = []
##
##        for inc in in_elem_list:
##            if inc == None:
##                return temp_list
##            else:
##                tmp_val = in_elem_list.attrib.get("attr")
##                if tmp_val == "parents" or tmp_val == "members":
##                    temp_list.append(int(inc.text))
##                else:
##                    temp_list.append(self._obsolete_fxml_parse_value(inc))
##        return temp_list
##
##    def _obsolete_fxml_parse_value(self, in_elem, in_list = None, index = None):
##
##            Gets the data out of attr="" and <tag>VALUE</tag>. It basically determines
##            if its a basic typed value or complex value.
##
##
##
##        ## Define advanced attributes like parents, we want to skip them at the beginning
##        par_typed_attrs = ["parents", "ancestors", "members"]
##
##        tmp_attr_type = in_elem.attrib.get("type")
##
##        ## Parse string by default
##        if tmp_attr_type == "str":
##            res_value = in_elem.text
##
##        ## Parse ints and floats
##        elif tmp_attr_type in basic_types.keys():
##            res_value = basic_types.get(tmp_attr_type)(in_elem.text)
##
##        else:
##            ## Parse "static" values
##            if in_elem.text in basic_values.keys():
##                res_value = basic_values.get(in_elem.text)
##
##            ## Basic list
##            elif "list" in in_elem.tag and in_elem.attrib.get("attr") not in par_typed_attrs:
##                res_value = self._obsolete_fxml_parse_basic_list(in_elem)
##
##            ## RAID levels. We want them as strings.
##            elif in_elem.attrib.get("attr") == "level":
##                res_value = in_elem.text
##
##            ## Complicated types, Size first
##            elif "." in tmp_attr_type and "Size" in tmp_attr_type:
##                mod_path, mod_name = self._obsolete_fxml_parse_module(None, tmp_attr_type)
##                res_value = getattr(importlib.import_module(mod_path), mod_name)(value = int(in_elem.text))
##
##            ## ParentList
##            elif "." in tmp_attr_type and "ParentList" in tmp_attr_type or in_elem.attrib.get("attr") in par_typed_attrs[1:]:
##                mod_path, mod_name = self._obsolete_fxml_parse_module(None, tmp_attr_type)
##                res_value = self._obsolete_fxml_parse_basic_list(in_elem)
##                res_value = self._obsolete_fxml_get_parent_obj(in_list, res_value)
##
##            else:
##                res_value = None
##
##        return res_value
##
##    def _obsolete_fxml_parse_attrs(self, in_master_list, in_elem, index):
##
##            This basically walks trough element tree and updates dictionary with
##            attributes.
##
##        ## Firstly, define what we want to skip for first time
##        ignored_attrs = ["fulltype"]
##
##        for inc in in_elem:
##            ## Dissasemble tuple into simpler objects
##            temp_obj_str = in_master_list[index][0]
##            temp_dict = in_master_list[index][1]
##            ## Ignore certain attributes
##            if inc.tag in ignored_attrs:
##                continue
##            elif inc.tag == "Child_ID":
##                attr_value = self._obsolete_fxml_get_child_id(int(inc.text))
##                #attr_value = self.format_list[index][-1]
##            else:
##                attr_value = self._obsolete_fxml_parse_value(inc, in_master_list, index)
##            temp_dict.update({inc.attrib.get("attr"): attr_value})
##
##            ## Reassemble afterwards
##            in_master_list[index] = (temp_obj_str, temp_dict)
##
##    def _obsolete_fxml_get_child_id(self, in_id):
##        for inc in self.format_list:
##            if in_id == inc[1].get("xml_id"):
##                return inc[2]
##
##################################################################################
################### INIT FUNCIONS ################################################
##    def _obsolete_fxml_init_class(self, in_master_list, list_index, forced_obj):
##
##            This finally intializes class object
##
##        temp_obj_str = in_master_list[list_index][0]
##        temp_obj_dict = in_master_list[list_index][1]
##        mod_path, mod_name = self._obsolete_fxml_parse_module(None, temp_obj_str)
##
##        ## Get name, because its general for all
##        obj_name = temp_obj_dict.get("name")
##        obj_arg_dict = {}
##
##        arg_list = getfullargspec(getattr(importlib.import_module(mod_path),
##                                          mod_name).__init__)[0][2:]
##        if forced_obj == "Format":
##            temp_obj = getattr(importlib.import_module(mod_path),
##                               mod_name)(exists = temp_obj_dict.get("exists"),
##                                         options = temp_obj_dict.get("options"),
##                                         uuid = temp_obj_dict.get("uuid"),
##                                         create_options = temp_obj_dict.get("create_options"))
##            in_master_list[list_index] = (temp_obj_str, temp_obj_dict, temp_obj)
##
##        elif "BTRFS" in forced_obj:
##            temp_obj = getattr(importlib.import_module(mod_path),
##                               mod_name)(parents = temp_obj_dict.get("parents"),
##                                         exists = temp_obj_dict.get("exists"))
##            self.devicetree._add_device(temp_obj)
##            in_master_list[list_index] = (temp_obj_str,
##                                          temp_obj_dict,
##                                          temp_obj)
##
##        else:
##            for inc in arg_list:
##                if inc == "fmt":
##                    obj_arg_dict.update({"fmt": self.format_list[list_index][-1]})
##                elif inc == "maxsize":
##                    obj_arg_dict.update({inc: temp_obj_dict.get("max_size")})
##                elif inc == "grow":
##                    obj_arg_dict.update({inc: temp_obj_dict.get("growable")})
##                elif inc == "primary":
##                    obj_arg_dict.update({inc: temp_obj_dict.get("is_primary")})
##                elif inc == "xml_import":
##                    obj_arg_dict.update({"xml_import": True})
##                elif inc == "xml_dict":
##                    obj_arg_dict.update({"xml_dict": temp_obj_dict})
##                else:
##                    obj_arg_dict.update({inc: temp_obj_dict.get(inc)})
##
##            ## Finally, Init it
##            if temp_obj_dict.get("name") not in self.completed_devices:
##                temp_obj = getattr(importlib.import_module(mod_path),
##                                   mod_name)(obj_name, **obj_arg_dict)
##                if hasattr(temp_obj, "_obsolete_fxml_set_attrs"):
##                    temp_obj._obsolete_fxml_set_attrs(temp_obj_dict, arg_list)
##                self.devicetree._add_device(temp_obj)
##                in_master_list[list_index] = (temp_obj_str, temp_obj_dict, temp_obj)
##                self.completed_devices.append(temp_obj.name)
##
##################################################################################
################### BASIC LOOP FUNCIONS ##########################################
##    def _obsolete_fxml_loop_trough(self, in_master_list, in_master_elem, forced_obj):
##
##            This function does the hard work - decides upon forced_obj to get
##            specific object from in_master_list to set attributes on.
##
##        counter = 0
##        for inc in in_master_list:
##            ## "disassemble" object into simpler, get name in this instance
##            temp_name = inc[0]
##            temp_dict = inc[1]
##            if forced_obj in temp_name.split(".")[-1] or forced_obj == "Format":
##                list_index = in_master_list.index(inc)
##                self._obsolete_fxml_parse_attrs(in_master_list, in_master_elem[list_index], list_index)
##                self._obsolete_fxml_init_class(in_master_list, list_index, forced_obj)
##            else:
##                continue
##
##            counter += 1
##
##    def _obsolete_fxml_get_basenames(self, in_master_elem, in_master_list):
##
##            This function will get basic names of the elements. This name can be
##            parsed into modules.
##
##        for inc in in_master_elem:
##            in_master_list.append((inc[0].text, \{\}))
##            in_master_list[-1][1].update({"name": inc.attrib.get("name")})
##            in_master_list[-1][1].update({"xml_id": int(inc.attrib.get("id"))})
##################################################################################
##################################################################################
##"""
#
