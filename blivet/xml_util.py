from .util import ObjectID
import xml.etree.ElementTree as ET
<<<<<<< HEAD
=======
from socket import gethostname

################################################################################
##### BASIC FUNCTIONS
def create_foundation():
    """
        This function creates root element and subelements that will be filled
        with Devices and Formats. Returns tuple: ET.Element and list
    """
    super_elems = []

    root_elem = ET.Element("Blivet-XML-Tools")
    super_elems.append(ET.SubElement(root_elem, "Devices"))
    super_elems.append(ET.SubElement(root_elem, "Formats"))
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

def select_device(dev_list, dump_device):
    """
        Docstring
    """
    selected_devs = []
    for dev in dev_list:
        if dump_device in dev:
            selected_devs.append(dev)
    return selected_devs

def export_iterate(device_list, super_elems, master_root_elem):
    """
        Docstring

        :param list super_elems: List of super elements (under the root element)

    """
    # Define basic types
    disk_elems = []
    format_elems = []

    for dev in device_list:
        if hasattr(dev, "to_xml"):
            dev_name = str(type(dev)).split("'")[1]
            disk_elems.append(ET.SubElement(super_elems[0], dev_name.split(".")[-1]))
            disk_elems[-1].set("fulltype", dev_name)
            disk_elems[-1].set("ObjectID", str(getattr(dev, "id")))
            dev._to_xml_init(master_root_elem)
            dev.to_xml()


################################################################################
##### BASIC DEFINITION
class XMLUtils(util.ObjectID):
    def _to_xml_init(self, root_elem, format_override=False, ids_done=set()):
        """
            :param ET.Element parent_elem:
        """
        self.root_elem = root_elem
        self.device_elems = self.root_elem[0]
        self.format_elems = self.root_elem[1]

        self.parent_elem = self.device_elems[-1]
        if format_override:
            self.parent_elem = self.format_elems[-1]

        self.elems_list = [] # Elements will be stored here
        self.attrs_done = set() # To prevent duplicates in elems_list
        self.ids_done = ids_done # As above, but for ids
        self.attr_list = dir(self) # List of attrs to gather
        self.ign_types = ["parted.", "method", "abc", "_ped.",
                          ".tasks.", "function", "functools.", "set"]
        self.ign_attrs = ["passphrase", "_abc", "dict", "sync", "mount",
                          "name", "_newid_gen", "_levels", "_newid_func",
                          "primary_partitions", "_plugin", "_info_class", "_resize",
                          "_writelabel", "_minsize", "_mkfs", "_readlabel",
                          "_size_info", "xml_dict", "_levels", "format_class", "id",
                          "elems_list", "fxml", "_to_xml", "parent_elem",
                          "device_elems", "format_elems", "attr_list", "ign_attrs",
                          "ign_types", "root_elem"]

################################################################################
##### Check ignored
    def _to_xml_check_igns(self, in_attr):
        if callable(getattr(self, in_attr)):
            return True
        if in_attr.startswith("__"):
            return True
        elif in_attr in self.attrs_done:
            return True
        else:
            return False

    # Check ignored in set
    def _to_xml_check_igns_iters(self, in_attr):
        ret_res = False
        for ig_attr in self.ign_attrs:
            if ig_attr in in_attr:
                ret_res = True

        for ig_type in self.ign_types:
            chck_type = str(type(getattr(self, in_attr))).split("'")[-2]
            if ig_type in chck_type:
                ret_res = True

        return ret_res

################################################################################
##### Set data
    def _to_xml_set_data(self, in_elem, in_data, full_bool=True):
        data_type = str(type(in_data)).split("'")[-2]
        # If the object has ObjectID (id)
        if hasattr(in_data, "id"):
            data_type = "ObjectID"
            final_value = getattr(in_data, "id")
        # Special condition for Size
        elif "Size" in data_type:
            final_value = in_data
            in_elem.set("Size", str(final_value))
            final_value = int(in_data)

        # Other types
        else:
            final_value = in_data

        in_elem.set("type", data_type)
        if full_bool:
            in_elem.text = str(final_value)

################################################################################
##### List parsing

    def _to_xml_parse_list(self, attrib):
        """
            :param str attrib: attribute name to get
        """
        # Get data, we ran it for first time
        elem_data = getattr(self, attrib)
        elem_type = type(elem_data)
        elem_tagn = str(elem_type).split("'")[-2]

        if "ParentList" in elem_tagn:
            elem_data = self._getdeepattr(self, str(attrib) + ".items")

        self.elems_list.append(ET.SubElement(self.parent_elem, elem_tagn))
        self.elems_list[-1].set("attr", attrib)
        if elem_data == []:
            return
        else:
            if "." in elem_tagn:
                add_tag = elem_tagn.split(".")[-1]
            else:
                add_tag = elem_tagn
            add_tag = add_tag + "-"
            self._to_xml_parse_list_iter(elem_data, self.elems_list[-1], add_tag)

    def _to_xml_parse_list_iter(self, in_data, par_elem, add_tag=""):
        sublist = []
        for iterator in in_data:
            # Determine type and append element
            iter_type = str(type(iterator)).split("'")[-2]
            sublist.append(ET.SubElement(par_elem, add_tag + "item"))
            self._to_xml_set_data(sublist[-1], iterator, False)

            if "PVFreeInfo" in iter_type:
                self._to_xml_parse_dict_iter(iterator.__dict__,
                                             sublist[-1],
                                             ["pv", "free", "size"],
                                             "dict-")
            else:
                self._to_xml_set_data(sublist[-1], iterator)

    def _to_xml_parse_dict_iter(self, in_data, par_elem, custom_args=None, add_tag=""):
        sublist = []
        for keys in in_data:
            if custom_args != None and keys not in custom_args:
                continue
            sublist.append(ET.SubElement(par_elem, add_tag + "item"))
            self._to_xml_set_data(sublist[-1], in_data.get(keys))


################################################################################
##### RAW objects
    def _to_xml_parse_raw(self, in_attrib):
        self.elems_list.append(ET.SubElement(self.parent_elem, "prop"))
        self.elems_list[-1].set("attr", in_attrib)
        self._to_xml_set_data(self.elems_list[-1], getattr(self, in_attrib))

################################################################################
##### Parsing objects, that are under devices (mostly formats), that have to_xml
    def _to_xml_parse_to_xml(self, in_attrib):
        # Create element
        self.elems_list.append(ET.SubElement(self.parent_elem, "prop"))
        self.elems_list[-1].set("type", "ObjectID")

        # Create tempovary id to assign
        temp_id = self._getdeepattr(self, in_attrib + ".id")
        self.elems_list[-1].text = str(temp_id)

        # Determine if we want to parse or if it is duplicate
        if temp_id not in self.ids_done:
            self.ids_done.add(temp_id)

            fmt = getattr(self, in_attrib)
            fmt_full_name = str(type(fmt)).split("'")[1]
            self.elems_list.append(ET.SubElement(self.format_elems, fmt_full_name.split(".")[-1]))
            self.elems_list[-1].set("type", fmt_full_name)
            self.elems_list[-1].set("ObjectID", str(temp_id))

            # Get uninitialized objects
            exp_initer = self._getdeepattr(self, in_attrib + "._to_xml_init")

            # Init basic init
            exp_initer = exp_initer(self.root_elem, format_override=True, ids_done=self.ids_done)
            self._getdeepattr(self, in_attrib + ".to_xml")()
        else:
            pass

################################################################################
##### EXPORT FUNCTION
    def to_xml(self):
        """
            docstring
        """

        for attr in self.attr_list:
            try:
                # For non-normal types, do a string check
                attr_type = type(getattr(self, attr))
                str_attr_type = str(type(getattr(self, attr)))
                if self._to_xml_check_igns(attr) or self._to_xml_check_igns_iters(attr):
                    continue

                # Basic fix - replace all underscore attrs with non-underscore
                if attr.startswith("_") and hasattr(self, attr[1:]):
                    attr = attr[1:]

                # Add attribute to completed so we can skip already completed
                self.attrs_done.add(attr)

                # List parsing
                if attr_type == list or attr_type == tuple or\
                    "ParentList" in str_attr_type:
                    self._to_xml_parse_list(attr)

                # TO_XML parsing
                elif hasattr(getattr(self, attr), "to_xml") and "format" in attr:
                    self._to_xml_parse_to_xml(attr)

                # For simple typed attribss
                else:
                    self._to_xml_parse_raw(attr)

            except Exception as e:
                print (e, attr)
                continue

>>>>>>> Release canditate: implemented:

class XMLUtils(ObjectID):
    def __init__(self):
        super(XMLUtils, self).__init__()

    def to_xml(self, parent_elem=None, root_elem=None, format_list=None,
               device_ids=None, super_elems=None, format_elems=None, disk_elems=None,
               in_object=None):
        """
            Export data to XML format and then return them to the caller.

            :param bool full_dump: If to perform full dump, or not.
            :param ET.Element parent_elem: Parent element where others are added
             into it.
            :param ET.Element root_elem: Master root element, where are
             parent_elem-s.
            :param list root_list: List of elements, where are parent_elem-s.
            :param list format_list: A assist list to prevent duplicates in
             sub-objects.

            This function does not return anything at all, it just scans
             devices or formats
            and converts them to elements to be stored in a valid XML file,
            without namespaces.

            The method of parsing into XML follows:
            Firstly, a master to_xml() is executed in blivet.Blivet(). This
            creates root element and scans for devices (or device if dump_device
             is not None).
            Checks, if device or object has to_xml() (this function - nested to
             others) and
            performs to_xml() on each of them.

            Same technique is with formats, if device contains format that has to_xml(),
            parser switches itself to root, then reexecutes itself on format instance and
            parses its attributes to elements.

        """
        elems_done = [] # Elements, that are done. Prevents duplicates.

        xml_sublist = []
        xml_child_sublist = []

        if in_object == None:
            input_data = dir(self)
            fulltype = str(type(self)).split("'")[1]
        else:
            input_data = dir(in_object)
            fulltype = str(type(in_object)).split("'")[1]

        xml_sublist.append(ET.SubElement(parent_elem, "fulltype"))
        xml_sublist[-1].text = fulltype

        for inc in input_data:
            ## Basic fix - replace all underscore attrs with non-underscore
            if inc.startswith("_") and hasattr(self, inc[1:]):
                inc = inc[1:]

            if self._to_xml_check_ignored(inc):
                continue

            elif inc == "id":
                device_ids.append(getattr(self, inc))
                continue

            elif type(getattr(self, inc)) == list or \
                 "ParentList" in str(type(getattr(self, inc))):
                xml_sublist.append(ET.SubElement(parent_elem, "list"))

                ## Determine if ParentList or just pure list.
                if "ParentList" in str(type(getattr(self, inc))):
                    xml_list_parse = self._getdeepattr(self, str(inc) + ".items")
                else:
                    xml_list_parse = getattr(self, inc)

                ## Set data and parse the list
                self._to_xml_set_data(elem = xml_sublist[-1], tag = inc)
                self._to_xml_parse_list(xml_list_parse, xml_sublist[-1])

            # Mostly for Parted, but kept for posible tuples in object
            elif type(getattr(self, inc)) == tuple:
                xml_sublist.append(ET.SubElement(parent_elem, "tuple",
                                                 {"attr": str(inc),
                                                  "type": str(tuple).split("'")[1]}))
                self._to_xml_parse_tuple(getattr(self, inc), xml_sublist[-1])

            elif inc == "cache" and getattr(self, inc) is not None: # in str(type(getattr(self, inc))):
                xml_sublist.append(ET.SubElement(parent_elem, "LVMCache", {"type": "object"}))
                cache_obj_id = str(getattr(self, inc)).split(">")[0].split(" ")[-1]
                xml_sublist[-1].text = cache_obj_id
                if cache_obj_id not in device_ids:
                    device_ids.append(cache_obj_id)
                    disk_elems.append(ET.SubElement(super_elems[0], "LVMCache", attrib={"object": cache_obj_id}))
                    self.to_xml(parent_elem = disk_elems[-1],
                                in_object = getattr(self, inc),
                                device_ids=device_ids)
                else:
                    pass

            # Check if subobject has to_xml() method to dump from it too
            elif hasattr(getattr(self, inc), "to_xml") and \
                 self._hasdeepattr(self, str(inc) + ".id"):
                # A simple check - use stack data structure with tuple to check
                # if the elem was set or not
                xml_parse_id = int(self._getdeepattr(self, str(inc) + ".id"))
                if xml_parse_id not in format_list and xml_parse_id not in device_ids:
                    format_list.append(xml_parse_id) ## MANDATORY! Adds value of ID if does not exist for check.

                    # Adds a Child_ID Element to "link" to formats section
                    xml_sublist.append(ET.SubElement(parent_elem, "Child_ID",
                                                     {"attr": str(inc)}))
                    xml_sublist[-1].text = str(xml_parse_id)
                    format_elems.append(ET.SubElement(super_elems[1],
                                                      str(type(getattr(self, inc))).split("'")[1].split(".")[-1],
                                                      {"id": str(self._getdeepattr(self, str(inc) + ".id")),
                                                       "name": str(self._getdeepattr(self, str(inc) + ".name"))})) # Adds a format root elem.
                    getattr(self, inc).to_xml(parent_elem = format_elems[-1],
                                              format_list = format_list,
                                              device_ids = device_ids,
                                              super_elems = super_elems)

            else:
                xml_sublist.append(ET.SubElement(parent_elem, "prop"))
                if "blivet.size.Size" in str(type(getattr(self, inc))):
                    integer_override = True
                else:
                    integer_override = False
                self._to_xml_set_data(elem = xml_sublist[-1],
                                      tag = inc,
                                      full_bool = True,
                                      integer_override = integer_override)
                if integer_override:
                    xml_sublist.append((parent_elem,
                                        ET.Comment({"Size": getattr(self, inc)})))
            elems_done.append(inc)

    def _to_xml_check_ignored(self, in_attr):
        ign_attrs = ["passphrase", "_abc", "dict", "sync", "mount",
                     "name", "_newid_gen", "_levels", "_newid_func",
                     "primary_partitions", "_plugin", "_info_class", "_resize",
                     "_writelabel", "_minsize", "_mkfs", "_readlabel", "_size_info",
                     "xml_dict", "_levels", "format_class"]
        ign_types = ["parted.", "method", "abc", "_ped.", ".tasks.", "function",
                     "functools.", "set"]

        if in_attr.startswith("__"):
            return True

        elif callable(in_attr):
            return True

        for attr in ign_attrs:
            if attr in in_attr:
                return True

        try:
            type_in_str = str(type(getattr(self, in_attr))).split("'")[1]
        except Exception as e:
            return True

        for attr_type in ign_types:
            if attr_type in type_in_str:
                return True

        return False


    def _to_xml_parse_tuple(self, in_tuple, in_elem):
        """
            Parses tuple like a list
        """
        tuple_list = []
        for inc in in_tuple:
            tuple_list.append(ET.SubElement(in_elem, "item"))
            #tuple_list[-1].set("type", str(type(getattr(self, inc))).split("\'")[1])
            tuple_list[-1].text = str(inc)
            tuple_list[-1].set("type", str(type(inc)).split("\'")[1])

    def _to_xml_parse_list(self, input_list, parent_index):
        """
            This function basically parses a list into indenpendent elements
        """
        xml_sublist_items = []

        for inc in input_list:
            xml_sublist_items.append(ET.SubElement(parent_index, "item"))
            self._to_xml_set_data(elem = xml_sublist_items[-1], tag = inc, input_type = "list")


    def _to_xml_set_data(self, **kwargs):
        """
            Sets element attribute at one place

            :param ET.Element elem: A ET.Element item (capable to perform ET.Element operations)
            :param str tag: a string name of a attribute (eg name, path...)
        """
        elem = kwargs.get("elem")
        tag = kwargs.get("tag")
        full_bool = kwargs.get("full_bool")
        input_type = kwargs.get("input_type")
        integer_override = kwargs.get("integer_override")

        if input_type == "list":
            attr_type = str(type(tag)).split("'")[1]
            if hasattr(tag, "id"):
                elem.text = str(getattr(tag, "id"))
                elem.set("attr", "id")
            elif "parted." in attr_type:
                attr_type = "Child_Path"
                elem.text = str(getattr(tag, "path")).split("/")[-1]
            else:
                elem.text = str(tag)
            elem.set("type", attr_type)
        else:
            elem.set("attr", str(tag))
            elem.set("type", str(type(getattr(self, tag))).split("\'")[1])

            ## Decide if to re-type integers or not, mainly for size
            if integer_override == True:
                elem.set("Size", str(getattr(self, tag)))
                elem_text = str(int(getattr(self, tag)))
            else:
                elem_text = str(getattr(self, tag))
            if full_bool == True:
                elem.text = elem_text

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


    def _to_xml_indent(self, elem, level=0):
        i = "\n" + level*"\t"
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "\t"
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self._to_xml_indent(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i

################################################################################
###################### BASIC FUNCTIONS #########################################
    def from_xml(self):
        """
            Populates a list with tuple containing class name and populated
            dictionary.
        """
        self.populated = False
        xml_root = self._fxml_get_root(self.xml_file)

        self.device_stack = []
        self.completed_devices = []

        ## Define basic shared lists
        self.device_list = []
        self.format_list = []

        self._fxml_get_basenames(xml_root[0], self.device_list)
        self._fxml_get_basenames(xml_root[1], self.format_list)

        self.name_list = []
        self._basename_iterator()
        self._fxml_loop_trough(self.format_list, xml_root[1], "Format")

        for inc in range(len(self.name_list)):
            self._fxml_loop_trough(self.device_list, xml_root[0], self.name_list[inc])



    def _basename_iterator(self):
        for inc in self.device_list:
            if inc[0].split(".")[-1] not in self.name_list:
                self.name_list.append(inc[0].split(".")[-1])

    def _fxml_get_root(self, in_file):
        """
            This returns basic XML elements: Devices and Formats.
            Returns: list of ET.Element
        """
        xml_root = ET.parse(in_file).getroot()
        return [xml_root[0], xml_root[1]]

################################################################################
################# TOOL FUNCIONS ################################################
    def _fxml_parse_module(self, in_elem = None, in_text = None):
        """
            This function basically parses a name from fulltype element or any
            other input element.
        """
        ## This decides if to parse from text or element
        imp_path = ""

        if in_elem == None:
            str_parse_mod = in_text
        else:
            str_parse_mod = in_elem.text

        for inc in range(len(str_parse_mod.split(".")) - 1):
            imp_path = imp_path + "." + str_parse_mod.split(".")[inc]
        mod_name = str_parse_mod.split(".")[-1]
        return (imp_path[1:], mod_name)

################################################################################
################# GET FUNCIONS #################################################
    def _fxml_get_parent_obj(self, in_par_list, in_list):

        res_par_list = []

        for inc in in_par_list:
            temp_obj = inc[-1]
            temp_dict = inc[1]
            if temp_dict.get("xml_id") in in_list:
                res_par_list.append(temp_obj)
        return res_par_list

################################################################################
################# PARSING FUNCIONS #############################################
    def _fxml_parse_basic_list(self, in_elem_list):
        """
            This function gets an element that is a list. It loops trough it and
            returns just list filled (or empty) with values that are subelements
        """
        temp_list = []

        for inc in in_elem_list:
            if inc == None:
                return temp_list
            else:
                tmp_val = in_elem_list.attrib.get("attr")
                if tmp_val == "parents" or tmp_val == "members":
                    temp_list.append(int(inc.text))
                else:
                    temp_list.append(self._fxml_parse_value(inc))
        return temp_list

    def _fxml_parse_value(self, in_elem, in_list = None, index = None):
        """
            Gets the data out of attr="" and <tag>VALUE</tag>. It basically determines
            if its a basic typed value or complex value.
        """
        ## Define basic types
        basic_types = {"int": int, "float": float} ## Note: str missing intentionally, parsed by default.
        basic_values = {"True": True, "False": False, "None": None}

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
                res_value = self._fxml_parse_basic_list(in_elem)

            ## RAID levels. We want them as strings.
            elif in_elem.attrib.get("attr") == "level":
                res_value = in_elem.text

            ## Complicated types, Size first
            elif "." in tmp_attr_type and "Size" in tmp_attr_type:
                mod_path, mod_name = self._fxml_parse_module(None, tmp_attr_type)
                res_value = getattr(importlib.import_module(mod_path), mod_name)(value = int(in_elem.text))

            ## ParentList
            elif "." in tmp_attr_type and "ParentList" in tmp_attr_type or in_elem.attrib.get("attr") in par_typed_attrs[1:]:
                mod_path, mod_name = self._fxml_parse_module(None, tmp_attr_type)
                res_value = self._fxml_parse_basic_list(in_elem)
                res_value = self._fxml_get_parent_obj(in_list, res_value)

            else:
                res_value = None

        return res_value

    def _fxml_parse_attrs(self, in_master_list, in_elem, index):
        """
            This basically walks trough element tree and updates dictionary with
            attributes.
        """
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
                attr_value = self._fxml_get_child_id(int(inc.text))
                #attr_value = self.format_list[index][-1]
            else:
                attr_value = self._fxml_parse_value(inc, in_master_list, index)
            temp_dict.update({inc.attrib.get("attr"): attr_value})

            ## Reassemble afterwards
            in_master_list[index] = (temp_obj_str, temp_dict)

    def _fxml_get_child_id(self, in_id):
        for inc in self.format_list:
            if in_id == inc[1].get("xml_id"):
                return inc[2]

################################################################################
################# INIT FUNCIONS ################################################
    def _fxml_init_class(self, in_master_list, list_index, forced_obj):
        """
            This finally intializes class object
        """
        temp_obj_str = in_master_list[list_index][0]
        temp_obj_dict = in_master_list[list_index][1]
        mod_path, mod_name = self._fxml_parse_module(None, temp_obj_str)

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
                if hasattr(temp_obj, "_fxml_set_attrs"):
                    temp_obj._fxml_set_attrs(temp_obj_dict, arg_list)
                self.devicetree._add_device(temp_obj)
                in_master_list[list_index] = (temp_obj_str, temp_obj_dict, temp_obj)
                self.completed_devices.append(temp_obj.name)

################################################################################
################# BASIC LOOP FUNCIONS ##########################################
    def _fxml_loop_trough(self, in_master_list, in_master_elem, forced_obj):
        """
            This function does the hard work - decides upon forced_obj to get
            specific object from in_master_list to set attributes on.
        """
        counter = 0
        for inc in in_master_list:
            ## "disassemble" object into simpler, get name in this instance
            temp_name = inc[0]
            temp_dict = inc[1]
            if forced_obj in temp_name.split(".")[-1] or forced_obj == "Format":
                list_index = in_master_list.index(inc)
                self._fxml_parse_attrs(in_master_list, in_master_elem[list_index], list_index)
                self._fxml_init_class(in_master_list, list_index, forced_obj)
            else:
                continue

            counter += 1

    def _fxml_get_basenames(self, in_master_elem, in_master_list):
        """
            This function will get basic names of the elements. This name can be
            parsed into modules.
        """
        for inc in in_master_elem:
            in_master_list.append((inc[0].text, {}))
            in_master_list[-1][1].update({"name": inc.attrib.get("name")})
            in_master_list[-1][1].update({"xml_id": int(inc.attrib.get("id"))})
################################################################################
################################################################################
