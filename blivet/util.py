import copy
import errno
import functools
import glob
import itertools
import os
import shutil
import selinux
import subprocess
import re
import sys
import tempfile
import uuid
import hashlib
import warnings
from decimal import Decimal
from contextlib import contextmanager
from functools import wraps
from collections import namedtuple

import xml.etree.ElementTree as ET

import gi
gi.require_version("BlockDev", "1.0")

from gi.repository import BlockDev as blockdev

import six

import logging
log = logging.getLogger("blivet")
program_log = logging.getLogger("program")
testdata_log = logging.getLogger("testdata")

from threading import Lock
# this will get set to anaconda's program_log_lock in enable_installer_mode
program_log_lock = Lock()


class Path(str):

    """ Path(path, root=None) provides a filesystem path object, which
        automatically normalizes slashes, assumes appends are what you
        always hoped os.path.join() was (but with out the weird slash
        games), and can easily handle paths with a root directory other
        than /
    """
    _root = None
    _path = None

    def __new__(cls, path, root=None, *args, **kwds):
        obj = str.__new__(cls, path, *args, **kwds)
        obj._path = path
        obj._root = None
        if root is not None:
            obj.newroot(str(root))
        return obj

    @property
    def ondisk(self):
        """ Path.ondisk evaluates as the real filesystem path of the path,
            including the path's root in the data.
        """
        if self.root:
            return normalize_path_slashes(Path(self.root) + Path(self.path))
        else:
            return Path(self.path)

    @property
    def path(self):
        return self._path

    @property
    def normpath(self):
        return Path(os.path.normpath(str(self.path)), root=self.root)

    @property
    def realpath(self):
        rp = os.path.realpath(self.ondisk)
        return Path(rp, root=self.root)

    @property
    def root(self):
        return self._root

    def newroot(self, newroot=None):
        """ Change the root directory of this Path """
        if newroot is None:
            self._root = None
        else:
            self._root = normalize_path_slashes(newroot)
            if self.startswith(self._root):
                path = self._path[len(self._root):]
                self._path = normalize_path_slashes(path)
        return self

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return repr(str(self.path))

    def __getitem__(self, idx):
        ret = str(self)
        return ret.__getitem__(idx)

    def __add__(self, other):
        if isinstance(other, Path):
            if other.root is not None and other.root != "/":
                if self.root is None:
                    self._root = other.root
                elif other.root != self.root:
                    raise ValueError("roots <%s> and <%s> don't match." %
                                     (self.root, other.root))
            path = "%s/%s" % (self.path, other.path)
        else:
            path = "%s/%s" % (self.path, other)
        path = normalize_path_slashes(path)
        return Path(path, root=self.root)

    def __eq__(self, other):
        if isinstance(other, Path):
            return self.path == other.path
        else:
            return self.path == str(other)

    def __lt__(self, other):
        if isinstance(other, Path):
            return self.path < other.path
        else:
            return self.path < str(other)

    def __gt__(self, other):
        if isinstance(other, Path):
            return self.path > other.path
        else:
            return self.path > str(other)

    def startswith(self, other):
        return self._path.startswith(str(other))

    def glob(self):
        """ Similar to glob.glob(), except it takes the Path's root into
            account when globbing and returns path objects with the same
            root, so you don't have to think about that part.
        """

        testdata_log.debug("glob: %s", self.ondisk)
        if "None" in self.ondisk:
            log.error("glob: %s", self.ondisk)
            log.error("^^ Somehow \"None\" got logged and that's never right.")
        for g in glob.glob(self.ondisk):
            testdata_log.debug("glob match: %s", g)
            yield Path(g, self.root)

    def __hash__(self):
        return self._path.__hash__()


def _run_program(argv, root='/', stdin=None, env_prune=None, stderr_to_stdout=False, binary_output=False):
    if env_prune is None:
        env_prune = []

    def chroot():
        if root and root != '/':
            os.chroot(root)

    with program_log_lock:
        program_log.info("Running... %s", " ".join(argv))

        env = os.environ.copy()
        env.update({"LC_ALL": "C",
                    "INSTALL_PATH": root})
        for var in env_prune:
            env.pop(var, None)

        if stderr_to_stdout:
            stderr_dir = subprocess.STDOUT
        else:
            stderr_dir = subprocess.PIPE
        try:
            proc = subprocess.Popen(argv,
                                    stdin=stdin,
                                    stdout=subprocess.PIPE,
                                    stderr=stderr_dir,
                                    close_fds=True,
                                    preexec_fn=chroot, cwd=root, env=env)

            out, err = proc.communicate()
            if not binary_output and six.PY3:
                out = out.decode("utf-8")
            if out:
                if not stderr_to_stdout:
                    program_log.info("stdout:")
                for line in out.splitlines():
                    program_log.info("%s", line)

            if not stderr_to_stdout and err:
                program_log.info("stderr:")
                for line in err.splitlines():
                    program_log.info("%s", line)

        except OSError as e:
            program_log.error("Error running %s: %s", argv[0], e.strerror)
            raise

        program_log.debug("Return code: %d", proc.returncode)

    return (proc.returncode, out)


def run_program(*args, **kwargs):
    return _run_program(*args, **kwargs)[0]


def capture_output(*args, **kwargs):
    return _run_program(*args, **kwargs)[1]


def capture_output_binary(*args, **kwargs):
    kwargs["binary_output"] = True
    return _run_program(*args, **kwargs)[1]


def run_program_and_capture_output(*args, **kwargs):
    return _run_program(*args, **kwargs)


def run_program_and_capture_output_binary(*args, **kwargs):
    kwargs["binary_output"] = True
    return _run_program(*args, **kwargs)


def mount(device, mountpoint, fstype, options=None):
    if options is None:
        options = "defaults"

    mountpoint = os.path.normpath(mountpoint)
    if not os.path.isdir(mountpoint):
        makedirs(mountpoint)

    argv = ["mount", "-t", fstype, "-o", options, device, mountpoint]
    try:
        rc = run_program(argv)
    except OSError:
        raise

    return rc


def umount(mountpoint):
    try:
        rc = run_program(["umount", mountpoint])
    except OSError:
        raise

    return rc


def get_mount_paths(dev):
    """ Given a device node path, return a list of all active mountpoints.

        :param str dev: Device path
        :returns: A list of mountpoints or []
        :rtype: list
    """
    from .mounts import mounts_cache

    mount_paths = mounts_cache.get_mountpoints(dev)
    if mount_paths:
        log.debug("%s is mounted on %s", dev, ', '.join(mount_paths))
    return mount_paths


def get_mount_device(mountpoint):
    """ Given a mountpoint, return the device node path mounted there. """
    mounts = open("/proc/mounts").readlines()
    mount_device = None
    for mnt in mounts:
        try:
            (device, path, _rest) = mnt.split(None, 2)
        except ValueError:
            continue

        if path == mountpoint:
            mount_device = device
            break

    if mount_device and re.match(r'/dev/loop\d+$', mount_device):
        loop_name = os.path.basename(mount_device)
        mount_device = blockdev.loop.get_backing_file(loop_name)
        log.debug("found backing file %s for loop device %s", mount_device,
                  loop_name)

    if mount_device:
        log.debug("%s is mounted on %s", mount_device, mountpoint)

    return mount_device


def total_memory():
    """ Return the amount of system RAM.

        :rtype: :class:`~.size.Size`
    """
    # import locally to avoid a cycle with size importing util
    from .size import Size

    with open("/proc/meminfo") as lines:
        line = next(l for l in lines if l.startswith("MemTotal:"))
        mem = Size("%s KiB" % line.split()[1])

    # Because /proc/meminfo only gives us the MemTotal (total physical RAM
    # minus the kernel binary code), we need to round this up. Assuming
    # every machine has the total RAM MiB number divisible by 128. */
    bs = Size("128MiB")
    mem = (mem / bs + 1) * bs
    return mem

##
# sysfs functions
##


def notify_kernel(path, action="change"):
    """ Signal the kernel that the specified device has changed.

        Exceptions raised: ValueError, IOError
    """
    log.debug("notifying kernel of '%s' event on device %s", action, path)
    path = os.path.join(path, "uevent")
    if not path.startswith("/sys/") or not os.access(path, os.W_OK):
        log.debug("sysfs path '%s' invalid", path)
        raise ValueError("invalid sysfs path")

    f = open(path, "a")
    f.write("%s\n" % action)
    f.close()


def normalize_path_slashes(path):
    """ Normalize the slashes in a filesystem path.
        Does not actually examine the filesystme in any way.
    """
    while "//" in path:
        path = path.replace("//", "/")
    return path


def join_paths(*paths):
    """ Joins filesystem paths without any consiration of slashes or
        whatnot and then normalizes repeated slashes.
    """
    if len(paths) == 1 and hasattr(paths[0], "__iter__"):
        return join_paths(*paths[0])
    return normalize_path_slashes('/'.join(paths))


def get_sysfs_attr(path, attr, root=None):
    if not attr:
        log.debug("get_sysfs_attr() called with attr=None")
        return None
    if not isinstance(path, Path):
        path = Path(path=path, root=root)
    elif root is not None:
        path.newroot(root)

    attribute = path + attr
    fullattr = os.path.realpath(attribute.ondisk)

    if not os.path.isfile(fullattr) and not os.path.islink(fullattr):
        log.warning("%s is not a valid attribute", attr)
        return None

    f = open(fullattr, "r")
    data = f.read()
    f.close()
    sdata = "".join(["%02x" % (ord(x),) for x in data])
    testdata_log.debug("sysfs attr %s: %s", attribute, sdata)
    return data.strip()


def sysfs_readlink(path, link, root=None):
    if not link:
        log.debug("sysfs_readlink() called with link=None")
    if isinstance(path, Path):
        linkpath = path + link
    else:
        linkpath = Path(path, root=root) + link

    linkpath = Path(os.path.normpath(linkpath), root=linkpath.root)
    fullpath = os.path.normpath(linkpath.ondisk)

    if not os.path.islink(fullpath):
        log.warning("%s is not a valid symlink", linkpath)
        return None

    output = os.readlink(fullpath)
    testdata_log.debug("new sysfs link: \"%s\" -> \"%s\"", linkpath, output)
    return output


def get_sysfs_path_by_name(dev_node, class_name="block"):
    """ Return sysfs path for a given device.

        For a device node (e.g. /dev/vda2) get the respective sysfs path
        (e.g. /sys/class/block/vda2). This also has to work for device nodes
        that are in a subdirectory of /dev like '/dev/cciss/c0d0p1'.
     """
    dev_name = os.path.basename(dev_node)
    if dev_node.startswith("/dev/"):
        dev_name = dev_node[5:].replace("/", "!")
    sysfs_class_dir = "/sys/class/%s" % class_name
    dev_path = os.path.join(sysfs_class_dir, dev_name)
    if os.path.exists(dev_path):
        return dev_path
    else:
        raise RuntimeError("get_sysfs_path_by_name: Could not find sysfs path "
                           "for '%s' (it is not at '%s')" % (dev_node, dev_path))


def get_cow_sysfs_path(dev_path, dev_sysfsPath):
    """ Return sysfs path of cow device for a given device.
    """

    cow_path = dev_path + "-cow"
    if not os.path.islink(cow_path):
        raise RuntimeError("get_cow_sysfs_path: Could not find cow device for" %
                           (dev_path))

    # dev path for cow devices is actually a link to a dm device (e.g. /dev/dm-X)
    # we need the 'dm-X' name for sysfs_path (e.g. /sys/devices/virtual/block/dm-X)
    # where first part is the same as in sysfs_path of the original device
    dm_name = os.path.basename(os.path.realpath(cow_path))
    cow_sysfsPath = os.path.join(os.path.split(dev_sysfsPath)[0], dm_name)

    return cow_sysfsPath

##
# SELinux functions
##


def match_path_context(path):
    """ Return the default SELinux context for the given path. """
    context = None
    try:
        context = selinux.matchpathcon(os.path.normpath(path), 0)[1]
    except OSError as e:
        log.info("failed to get default SELinux context for %s: %s", path, e)

    return context


def set_file_context(path, context, root=None):
    """ Set the SELinux file context of a file.

        Arguments:

            path        filename string
            context     context string

        Keyword Arguments:

            root        an optional chroot string

        Return Value:

            True if successful, False if not.
    """
    if root is None:
        root = '/'

    full_path = os.path.normpath("%s/%s" % (root, path))
    if context is None or not os.access(full_path, os.F_OK):
        return False

    try:
        rc = (selinux.lsetfilecon(full_path, context) == 0)
    except OSError as e:
        log.info("failed to set SELinux context for %s: %s", full_path, e)
        rc = False

    return rc


def reset_file_context(path, root=None):
    """ Restore the SELinux context of a file to its default value.

        Arguments:

            path        filename string

        Keyword Arguments:

            root        an optional chroot string

        Return Value:

            If successful, returns the file's new/default context.
    """
    context = match_path_context(path)
    if context:
        if set_file_context(path, context, root=root):
            return context

##
# Miscellaneous
##


def find_program_in_path(prog, raise_on_error=False):
    for d in os.environ["PATH"].split(os.pathsep):
        full = os.path.join(d, prog)
        if os.access(full, os.X_OK):
            return full

    if raise_on_error:
        raise RuntimeError("Unable to locate a needed executable: '%s'" % prog)


def makedirs(path):
    if not os.path.isdir(path):
        os.makedirs(path, 0o755)


def copy_to_system(source):
    # do the import now because enable_installer_mode() has finally been called.
    from . import get_sysroot

    if not os.access(source, os.R_OK):
        log.info("copy_to_system: source '%s' does not exist.", source)
        return False

    target = get_sysroot() + source
    target_dir = os.path.dirname(target)
    log.debug("copy_to_system: '%s' -> '%s'.", source, target)
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)
    shutil.copy(source, target)
    return True


def lsmod():
    """ Returns list of names of all loaded modules. """
    with open("/proc/modules") as f:
        lines = f.readlines()
    return [l.split()[0] for l in lines]


def get_option_value(opt_name, options):
    """ Return the value of a named option in the specified options string. """
    for opt in options.split(","):
        if "=" not in opt:
            continue

        name, val = opt.split("=")
        if name == opt_name:
            return val.strip()


def numeric_type(num):
    """ Verify that a value is given as a numeric data type.

        Return the number if the type is sensible or raise ValueError
        if not.
    """
    # import locally to avoid a cycle with size importing util
    from .size import Size

    if num is None:
        num = 0
    elif not isinstance(num, (six.integer_types, float, Size, Decimal)):
        raise ValueError("value (%s) must be either a number or None" % num)

    return num


def insert_colons(a_string):
    """ Insert colon between every second character.

        E.g. creates 'al:go:ri:th:ms' from 'algoritms'. Useful for formatting
        MAC addresses and wwids for output.
    """
    suffix = a_string[-2:]
    if len(a_string) > 2:
        return insert_colons(a_string[:-2]) + ':' + suffix
    else:
        return suffix


def md5_file(filename):

    md5 = hashlib.md5()
    with open(filename, "rb") as f:

        block = f.read(65536)
        while block:
            md5.update(block)
            block = f.read(65536)

    return md5.hexdigest()


class ObjectID(object):

    """This class is meant to be extended by other classes which require
       an ID which is preserved when an object copy is made.
       The value returned by the builtin function id() is not adequate:
       that value represents object identity so it is not in general
       preserved when the object is copied.

       The name of the identifier property is id, its type is int.

       The id is set during creation of the class instance to a new value
       which is unique for the object type. Subclasses can use self.id during
       __init__.
    """
    _newid_gen = functools.partial(next, itertools.count())

    def __new__(cls, *args, **kwargs):
        # pylint: disable=unused-argument
        self = super(ObjectID, cls).__new__(cls)
        self.id = self._newid_gen()  # pylint: disable=attribute-defined-outside-init
        return self

    def to_xml(self, **kwargs):
        """
            Export data to XML format and then return them to the caller.

            :param bool full_dump: If to perform full dump, or not.
            :param ET.Element parent_elem: Parent element where others are added into it.
            :param ET.Element root_elem: Master root element, where are parent_elem-s.
            :param list root_list: List of elements, where are parent_elem-s.
            :param list format_list: A assist list to prevent duplicates in sub-objects.

            This function does not return anything at all, it just scans devices or formats
            and converts them to elements to be stored in a valid XML file,
            without namespaces.

            The method of parsing into XML follows:
            Firstly, a master to_xml() is executed in blivet.Blivet(). This
            creates root element and scans for devices (or device if dump_device is not None).
            Checks, if device or object has to_xml() (this function - nested to others) and
            performs to_xml() on each of them.

            Same technique is with formats, if device contains format that has to_xml(),
            parser switches itself to root, then reexecutes itself on format instance and
            parses its attributes to elements.

        """
        ## General
        full_dump = kwargs.get("full_dump")

        parent_elem = kwargs.get("parent_elem")
        root_elem = kwargs.get("root_elem")

        format_list = kwargs.get("format_list")
        device_ids = kwargs.get("device_ids")

        super_elems = kwargs.get("super_elems") # Not to be confused, this is a list of super elements!
        format_elems = kwargs.get("format_elems")

        xml_sublist = []
        xml_child_sublist = []

        if full_dump != None and hasattr(self, "_to_xml_set_attrs"):
            input_data = self._to_xml_set_attrs()
        else:
            input_data = dir(self)

        ignored_attrs = ["sync", "dict", "mount"]

        xml_sublist.append(ET.SubElement(parent_elem, "fulltype"))
        xml_sublist[-1].text = str(type(self)).split("'")[1]
        for inc in input_data:
            ## Basic fix - replace all underscore attrs with non-underscore
            if inc.startswith("_") and hasattr(self, inc[1:]):
                inc = inc[1:]

            if inc in ignored_attrs or callable(inc) or inc.startswith("__") or str(type(getattr(self, inc))).split("\'")[1] == "method":
                continue

            if inc == "id":
                device_ids.append(getattr(self, inc))

            if type(getattr(self, inc)) == list or str(type(getattr(self, inc))).split("'")[1].split(".")[-1] == "ParentList":
                xml_sublist.append(ET.SubElement(parent_elem, "list"))

                ## Determine if ParentList or just pure list.
                if str(type(getattr(self, inc))).split("'")[1].split(".")[-1] == "ParentList":
                    xml_list_parse = self._getdeepattr(self, str(inc) + ".items")
                else:
                    xml_list_parse = getattr(self, inc)

                ## Set data and parse the list
                self._to_xml_set_data(elem = xml_sublist[-1], tag = inc)
                self._to_xml_parse_list(xml_list_parse, xml_sublist[-1])

            elif hasattr(getattr(self, inc), "to_xml") and self._hasdeepattr(self, str(inc) + ".id"):
                ## A simple check - use stack data structure with tuple to check if the elem was set or not
                xml_parse_id = int(self._getdeepattr(self, str(inc) + ".id"))
                if xml_parse_id not in format_list and xml_parse_id not in device_ids:
                    format_list.append(xml_parse_id) ## MANDATORY! Adds value of ID if does not exist for check.

                    if len(super_elems) == 1:
                        super_elems.append(ET.SubElement(root_elem, "Formats"))

                    xml_sublist.append(ET.SubElement(parent_elem, "Child_ID", {"attr": str(inc)})) ## Adds a Child_ID Element to "link" to formats section
                    xml_sublist[-1].text = str(xml_parse_id)
                    format_elems.append(ET.SubElement(super_elems[1], str(type(getattr(self, inc))).split("'")[1].split(".")[-1], {"id": str(self._getdeepattr(self, str(inc) + ".id")), "name": str(self._getdeepattr(self, str(inc) + ".name"))})) # Adds a format root elem.
                    getattr(self, inc).to_xml(parent_elem = format_elems[-1], format_list = format_list, device_ids = device_ids)

            else:
                xml_sublist.append(ET.SubElement(parent_elem, "prop"))
                if str(type(getattr(self, inc))).split("'")[1] == "blivet.size.Size":
                    integer_override = True
                else:
                    integer_override = False
                self._to_xml_set_data(elem = xml_sublist[-1], tag = inc, full_bool = True, integer_override = integer_override)

        self._to_xml_indent(parent_elem)

    def _to_xml_parse_list(self, input_list, parent_index):
        """
            This function basically parses a list into indenpendent elements
        """
        xml_sublist_items = []

        if input_list == []:
            xml_sublist_items.append(ET.SubElement(parent_index, "item"))
            xml_sublist_items[-1].text = str(None)
        else:
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
            if hasattr(tag, "id"):
                elem.text = str(getattr(tag, "id"))
                elem.set("attr", "parent_id")
            else:
                elem.text = str(tag)
            elem.set("type", str(type(tag)).split("'")[1])
        else:
            elem.set("attr", str(tag))
            elem.set("type", str(type(getattr(self, tag))).split("\'")[1])

            ## Decide if to re-type integers or not, mainly for size
            if integer_override == True:
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

def canonicalize_UUID(a_uuid):
    """ Converts uuids to canonical form.

        :param str a_uuid: the UUID

        :returns: a canonicalized UUID
        :rtype: str

        mdadm's UUIDs are actual 128 bit uuids, but it formats them strangely.
        This converts the uuids to canonical form.
        Example:
            mdadm UUID: '3386ff85:f5012621:4a435f06:1eb47236'
        canonical UUID: '3386ff85-f501-2621-4a43-5f061eb47236'

        If the UUID is already in canonical form, the conversion
        is equivalent to the identity.
    """
    return str(uuid.UUID(a_uuid.replace(':', '')))

# Most Python 2/3 compatibility code equates python 2 str with python 3 bytes,
# but the equivalence that we actually need to avoid return type surprises is
# str/str.


def stringize(inputstr):
    """ Convert strings to a format compatible with Python 2's str.

        :param str inputstr: the string to convert

        :returns: a string with the correct type
        :rtype: str

        This method is for use in __str__ calls to ensure that they always
        return a str. In Python 3, this method simply inputstr as a string. In
        Python 2, it converts unicode into str. The returned str in python 2 is
        encoded using utf-8.
    """
    if six.PY2:
        # pylint: disable=undefined-variable
        if isinstance(inputstr, unicode):
            inputstr = inputstr.encode('utf-8')

    return str(inputstr)

# Like six.u, but without the part where it raises an exception on unicode
# objects


def unicodeize(inputstr):
    """ Convert strings to a format compatible with Python 2's unicode.

        :param str inputstr: the string to convert

        :returns: a string with the correct type
        :rtype: unicode

        This method is for use in __unicode__ calls to ensure that they always
        return a unicode. This method does not handle non-ASCII characters
        in str parameters, but non-ASCII characters in unicode parameters will
        be correctly passed through.
    """
    if six.PY2:
        # pylint: disable=undefined-variable
        return unicode(inputstr)
    else:
        return str(inputstr)


def compare(first, second):
    """ Compare two objects.

        :param first: first object to compare
        :param second: second object to compare
        :returns: 0 if first == second, 1 if first > second, -1 if first < second
        :rtype: int

        This method replaces Python 2 cmp() built-in-function.
    """

    if first is None and second is None:
        return 0

    elif first is None:
        return -1

    elif second is None:
        return 1

    else:
        return (first > second) - (first < second)

##
# Convenience functions for examples and tests
##


def set_up_logging(log_dir="/tmp", log_prefix="blivet"):
    """ Configure the blivet logger to write out a log file.

        :keyword str log_file: path to the log file (default: /tmp/blivet.log)
    """

    log.setLevel(logging.DEBUG)
    program_log.setLevel(logging.DEBUG)

    def make_handler(path, prefix, level):
        log_file = "%s/%s.log" % (path, prefix)
        log_file = os.path.realpath(log_file)
        handler = logging.FileHandler(log_file)
        handler.setLevel(level)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        return handler

    handler = make_handler(log_dir, log_prefix, logging.DEBUG)
    log.addHandler(handler)
    program_log.addHandler(handler)

    # capture python warnings in our logs
    warning_log = logging.getLogger("py.warnings")
    warning_log.addHandler(handler)

    log.info("sys.argv = %s", sys.argv)

    prefix = "%s-testdata" % (log_prefix,)
    handler = make_handler(log_dir, prefix, logging.DEBUG)
    testdata_log.setLevel(logging.DEBUG)
    testdata_log.addHandler(handler)


def create_sparse_tempfile(name, size):
    """ Create a temporary sparse file.

        :param str name: suffix for filename
        :param :class:`~.size.Size` size: the file size
        :returns: the path to the newly created file
    """
    (fd, path) = tempfile.mkstemp(prefix="blivet.", suffix="-%s" % name)
    eintr_ignore(os.close, fd)
    create_sparse_file(path, size)
    return path


def create_sparse_file(path, size):
    """ Create a sparse file.

        :param str path: the full path to the file
        :param :class:`~.size.Size` size: the size of the file
        :returns: None
    """
    fd = eintr_retry_call(os.open, path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    eintr_retry_call(os.ftruncate, fd, size)
    eintr_ignore(os.close, fd)


@contextmanager
def sparsetmpfile(name, size):
    """ Context manager that creates a sparse tempfile and then unlinks it.

        :param str name: suffix for filename
        :param :class:`~.size.Size` size: the file size

        Yields the path to the newly created file on __enter__.
    """
    path = create_sparse_tempfile(name, size)
    try:
        yield path
    finally:
        os.unlink(path)


def variable_copy(obj, memo, omit=None, shallow=None, duplicate=None):
    """ A configurable copy function. Any attributes not specified in omit,
        shallow, or duplicate are copied using copy.deepcopy().

        :param object obj: a python object to be copied.
        :param dict memo: a dictionary of already copied items
        :param omit: a list of names of attributes not to copy
        :type omit: iterable of str
        :param shallow: a list of names of attributes to shallow copy
        :type shallow: iterable of str
        :param duplicate: a list of names of attributes to duplicate
        :type duplicate: iterable of str

        Note that all atrributes in duplicate must implement a duplicate()
        method that does what is expected of it. Attributes with type
        pyparted.Disk are known to do so.

        A shallow copy is implemented by calling copy.copy().
    """
    omit = omit or []
    shallow = shallow or []
    duplicate = duplicate or []

    new = obj.__class__.__new__(obj.__class__)
    memo[id(obj)] = new
    for (attr, value) in obj.__dict__.items():
        if attr in omit or value is None:
            setattr(new, attr, value)
        elif attr in shallow:
            setattr(new, attr, copy.copy(value))
        elif attr in duplicate:
            setattr(new, attr, value.duplicate())
        else:
            setattr(new, attr, copy.deepcopy(value, memo))

    return new


def get_current_entropy():
    with open("/proc/sys/kernel/random/entropy_avail", "r") as fobj:
        return int(fobj.readline())


def power_of_two(value):
    """ Checks whether value is a power of 2 greater than 1.

        :param any value: a value
        :returns: True if the value is a power of 2
        :rtype: bool
    """
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        return False

    if int_value != value:
        return False

    value = int_value

    if value < 2:
        return False

    (q, r) = (value, 0)
    while q != 0:
        if r != 0:
            return False
        (q, r) = divmod(q, 2)

    return True

# Copied from python's subprocess.py


def eintr_retry_call(func, *args, **kwargs):
    """Retry an interruptible system call if interrupted."""
    while True:
        try:
            return func(*args, **kwargs)
        except (OSError, IOError) as e:
            if e.errno == errno.EINTR:
                continue
            raise


def eintr_ignore(func, *args, **kwargs):
    """Call a function and ignore EINTR.

       This is useful for calls to close() and dup2(), which can return EINTR
       but which should *not* be retried, since by the time they return the
       file descriptor is already closed.
    """
    try:
        return func(*args, **kwargs)
    except (OSError, IOError) as e:
        if e.errno == errno.EINTR:
            pass
        raise

_open = open


def open(*args, **kwargs):  # pylint: disable=redefined-builtin
    """Open a file, and retry on EINTR."""
    return eintr_retry_call(_open, *args, **kwargs)


def indent(text, spaces=4):
    """ Indent text by a specified number of spaces.

        :param str text: the text to indent
        :keyword int spaces: the number of spaces to indent text

        It would be nice if we could use textwrap.indent for this but, since it
        does not exist in python2, I prefer to just use this.
    """
    if not text or not text.strip():
        return text

    indentation = " " * spaces
    indented = []
    for line in text.splitlines():
        indented.append("%s%s" % (indentation, line))

    return "\n".join(indented)


def _add_extra_doc_text(func, field=None, desc=None, field_unique=False):
    """ Add extra doc text to a function's docstring.

        :param :class:`function` func: the function
        :param str field: (sphinx) field to add to the doc text
        :param str desc: description to add in the given :param:`field`
        :param bool field_unique: whether the given :param:`field` should only
                                  appear in the doc text once (a new one won't
                                  be added if there already is an existing one)

        If your doctext is indented with something other than spaces the added
        doctext's indentation will probably not match. That'd be your fault.
    """

    base_text = func.__doc__
    if base_text is None:
        base_text = " "  # They contain leading and trailing spaces. *shrug*
    else:
        base_text = base_text[:-1]  # Trim the trailing space.

    if field_unique and field in base_text:
        # Don't add multiple fields
        return

    # Figure out the number of spaces to indent docstring text. We are looking
    # for the minimum indentation, not including the first line or empty lines.
    indent_spaces = None
    for l in base_text.splitlines()[1:]:
        if not l.strip():
            continue

        spaces = 0
        _l = l[:]
        while _l and _l.startswith(" "):
            spaces += 1
            _l = _l[1:]

        if indent_spaces is None or indent_spaces > spaces:
            indent_spaces = spaces

    if indent_spaces is None:
        indent_spaces = 0

    text = ""
    if not re.search(r'\n\s*$', base_text):
        # Make sure there's a newline after the last text.
        text = "\n"

    desc = desc or ""
    text += field + " " + desc
    func.__doc__ = base_text + "\n" + indent(text, indent_spaces)

#
# Deprecation decorator.
#
_DEPRECATION_MESSAGE = "will be removed in a future version."


def _default_deprecation_msg(func):
    return "%s %s" % (func.__name__, _DEPRECATION_MESSAGE)

_SPHINX_DEPRECATE = ".. deprecated::"
_DEPRECATION_INFO = """%(version)s
    %(message)s
"""


def _add_deprecation_doc_text(func, version=None, message=None):
    desc = _DEPRECATION_INFO % {"version": version, "message": message}
    _add_extra_doc_text(func, _SPHINX_DEPRECATE, desc, field_unique=True)


def deprecated(version, message):
    """ Decorator to deprecate a function or method via warning and docstring.

        :param str version: version in which the deprecation is effective
        :param str message: message suggesting a preferred alternative

        .. note::
            At the point this decorator gets applied to a method in a class the
            method is just a function. It becomes a method later.

        The docstring manipulation is performed only once for each decorated
        function/method, but the warning is issued every time the decorated
        function is called.
    """
    def deprecate_func(func):
        @wraps(func)
        def the_func(*args, **kwargs):
            """ Issue a deprecation warning for, then call, a function. """
            # Warnings look much better with default warning text than with
            # no text. The sphinx doesn't benefit from it, so don't use it
            # there.
            warn_msg = _default_deprecation_msg(func)
            if message:
                warn_msg += " %s" % message

            warnings.warn(warn_msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        _add_deprecation_doc_text(the_func, message=message, version=version)
        return the_func

    return deprecate_func


def default_namedtuple(name, fields, doc=""):
    """Create a namedtuple class

    The difference between a namedtuple class and this class is that default
    values may be specified for fields and fields with missing values on
    initialization being initialized to None.

    :param str name: name of the new class
    :param fields: field descriptions - an iterable of either "name" or ("name", default_value)
    :type fields: list of str or (str, object) objects
    :param str doc: the docstring for the new class (should at least describe the meanings and
                    types of fields)
    :returns: a new default namedtuple class
    :rtype: type

    """
    field_names = list()
    for field in fields:
        if isinstance(field, tuple):
            field_names.append(field[0])
        else:
            field_names.append(field)
    nt = namedtuple(name, field_names)

    # pylint: disable=no-init
    class TheDefaultNamedTuple(nt):
        if doc:
            __doc__ = doc

        def __new__(cls, *args, **kwargs):
            args_list = list(args)
            sorted_kwargs = sorted(kwargs.keys(), key=field_names.index)
            for i in range(len(args), len(field_names)):
                if field_names[i] in sorted_kwargs:
                    args_list.append(kwargs[field_names[i]])
                elif isinstance(fields[i], tuple):
                    args_list.append(fields[i][1])
                else:
                    args_list.append(None)

            return nt.__new__(cls, *args_list)

    return TheDefaultNamedTuple
