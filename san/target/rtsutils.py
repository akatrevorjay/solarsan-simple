
from solarsan.utils.files import fread
import re
import os
import stat
import uuid
import glob
import socket


"""
Gracefully lifted from rtslib.utils
"""


def is_dev_in_use(path):
    '''
    This function will check if the device or file referenced by path is
    already mounted or used as a storage object backend.  It works by trying to
    open the path with O_EXCL flag, which will fail if someone else already
    did.  Note that the file is closed before the function returns, so this
    does not guaranteed the device will still be available after the check.
    @param path: path to the file of device to check
    @type path: string
    @return: A boolean, True is we cannot get exclusive descriptor on the path,
             False if we can.
    '''
    path = os.path.realpath(str(path))
    try:
        file_fd = os.open(path, os.O_EXCL | os.O_NDELAY)
    except OSError:
        return True
    else:
        os.close(file_fd)
        return False


def is_disk_partition(path):
    '''
    Try to find out if path is a partition of a TYPE_DISK device.
    Handles both /dev/sdaX and /dev/disk/by-*/*-part? schemes.
    '''
    regex = re.match(r'([a-z/]+)([1-9]+)$', path)
    if not regex:
        regex = re.match(r'(/dev/disk/.+)(-part[1-9]+)$', path)
    if not regex:
        return False
    else:
        if get_block_type(regex.group(1)) == 0:
            return True


def get_disk_size(path):
    '''
    This function returns the size in bytes of a disk-type
    block device, or None if path does not point to a disk-
    type device.
    '''
    (major, minor) = get_block_numbers(path)
    if major is None:
        return None
    # list of [major, minor, #blocks (1K), name
    partitions = [x.split()[0:4]
                  for x in fread("/proc/partitions").split("\n")[2:] if x]
    size = None
    for partition in partitions:
        if partition[0:2] == [str(major), str(minor)]:
            size = int(partition[2]) * 1024
            break
    return size


def get_block_numbers(path):
    '''
    This function returns a (major,minor) tuple for the block
    device found at path, or (None, None) if path is
    not a block device.
    '''
    dev = os.path.realpath(path)
    try:
        mode = os.stat(dev)
    except OSError:
        return (None, None)

    if not stat.S_ISBLK(mode[stat.ST_MODE]):
        return (None, None)

    major = os.major(mode.st_rdev)
    minor = os.minor(mode.st_rdev)
    return (major, minor)


def get_block_type(path):
    '''
    This function returns a block device's type.
    Example: 0 is TYPE_DISK
    If no match is found, None is returned.

    >>> from rtslib.utils import *
    >>> get_block_type("/dev/sda")
    0
    >>> get_block_type("/dev/sr0")
    5
    >>> get_block_type("/dev/scd0")
    5
    >>> get_block_type("/dev/nodevicehere") is None
    True

    @param path: path to the block device
    @type path: string
    @return: An int for the block device type, or None if not a block device.
    '''
    dev = os.path.realpath(path)
    # TODO: Make adding new majors on-the-fly possible, using some config file
    # for instance, maybe an additionnal list argument, or even a match all
    # mode for overrides ?

    # Make sure we are dealing with a block device
    (major, minor) = get_block_numbers(dev)
    if major is None:
        return None

    # Treat disk partitions as TYPE_DISK
    if is_disk_partition(path):
        return 0

    # These devices are disk type block devices, but might not report this
    # correctly in /sys/block/xxx/device/type, so use their major number.
    type_disk_known_majors = [1,    # RAM disk
                              8,    # SCSI disk devices
                              9,    # Metadisk RAID devices
                              13,   # 8-bit MFM/RLL/IDE controller
                              19,   # "Double" compressed disk
                              21,   # Acorn MFM hard drive interface
                              30,   # FIXME: Normally 'Philips LMS CM-205
                              # CD-ROM' in the Linux devices list but
                              # used by Cirtas devices.
                              35,   # Slow memory ramdisk
                              36,   # MCA ESDI hard disk
                              37,   # Zorro II ramdisk
                              43,   # Network block devices
                              44,   # Flash Translation Layer (FTL) filesystems
                              45,   # Parallel port IDE disk devices
                              47,   # Parallel port ATAPI disk devices
                              48,   # Mylex DAC960 PCI RAID controller
                              48,   # Mylex DAC960 PCI RAID controller
                              49,   # Mylex DAC960 PCI RAID controller
                              50,   # Mylex DAC960 PCI RAID controller
                              51,   # Mylex DAC960 PCI RAID controller
                              52,   # Mylex DAC960 PCI RAID controller
                              53,   # Mylex DAC960 PCI RAID controller
                              54,   # Mylex DAC960 PCI RAID controller
                              55,   # Mylex DAC960 PCI RAID controller
                              58,   # Reserved for logical volume manager
                              59,   # Generic PDA filesystem device
                              60,   # LOCAL/EXPERIMENTAL USE
                              61,   # LOCAL/EXPERIMENTAL USE
                              62,   # LOCAL/EXPERIMENTAL USE
                              63,   # LOCAL/EXPERIMENTAL USE
                              64,   # Scramdisk/DriveCrypt encrypted devices
                              65,   # SCSI disk devices (16-31)
                              66,   # SCSI disk devices (32-47)
                              67,   # SCSI disk devices (48-63)
                              68,   # SCSI disk devices (64-79)
                              69,   # SCSI disk devices (80-95)
                              70,   # SCSI disk devices (96-111)
                              71,   # SCSI disk devices (112-127)
                              72,   # Compaq Intelligent Drive Array
                              73,   # Compaq Intelligent Drive Array
                              74,   # Compaq Intelligent Drive Array
                              75,   # Compaq Intelligent Drive Array
                              76,   # Compaq Intelligent Drive Array
                              77,   # Compaq Intelligent Drive Array
                              78,   # Compaq Intelligent Drive Array
                              79,   # Compaq Intelligent Drive Array
                              80,   # I2O hard disk
                              80,   # I2O hard disk
                              81,   # I2O hard disk
                              82,   # I2O hard disk
                              83,   # I2O hard disk
                              84,   # I2O hard disk
                              85,   # I2O hard disk
                              86,   # I2O hard disk
                              87,   # I2O hard disk
                              93,   # NAND Flash Translation Layer filesystem
                              94,   # IBM S/390 DASD block storage
                              96,   # Inverse NAND Flash Translation Layer
                              98,   # User-mode virtual block device
                              99,   # JavaStation flash disk
                              101,  # AMI HyperDisk RAID controller
                              102,  # Compressed block device
                              104,  # Compaq Next Generation Drive Array
                              105,  # Compaq Next Generation Drive Array
                              106,  # Compaq Next Generation Drive Array
                              107,  # Compaq Next Generation Drive Array
                              108,  # Compaq Next Generation Drive Array
                              109,  # Compaq Next Generation Drive Array
                              110,  # Compaq Next Generation Drive Array
                              111,  # Compaq Next Generation Drive Array
                              112,  # IBM iSeries virtual disk
                              114,  # IDE BIOS powered software RAID interfaces
                              115,  # NetWare (NWFS) Devices (0-255)
                              117,  # Enterprise Volume Management System
                              120,  # LOCAL/EXPERIMENTAL USE
                              121,  # LOCAL/EXPERIMENTAL USE
                              122,  # LOCAL/EXPERIMENTAL USE
                              123,  # LOCAL/EXPERIMENTAL USE
                              124,  # LOCAL/EXPERIMENTAL USE
                              125,  # LOCAL/EXPERIMENTAL USE
                              126,  # LOCAL/EXPERIMENTAL USE
                              127,  # LOCAL/EXPERIMENTAL USE
                              128,  # SCSI disk devices (128-143)
                              129,  # SCSI disk devices (144-159)
                              130,  # SCSI disk devices (160-175)
                              131,  # SCSI disk devices (176-191)
                              132,  # SCSI disk devices (192-207)
                              133,  # SCSI disk devices (208-223)
                              134,  # SCSI disk devices (224-239)
                              135,  # SCSI disk devices (240-255)
                              136,  # Mylex DAC960 PCI RAID controller
                              137,  # Mylex DAC960 PCI RAID controller
                              138,  # Mylex DAC960 PCI RAID controller
                              139,  # Mylex DAC960 PCI RAID controller
                              140,  # Mylex DAC960 PCI RAID controller
                              141,  # Mylex DAC960 PCI RAID controller
                              142,  # Mylex DAC960 PCI RAID controller
                              143,  # Mylex DAC960 PCI RAID controller
                              144,  # Non-device (e.g. NFS) mounts
                              145,  # Non-device (e.g. NFS) mounts
                              146,  # Non-device (e.g. NFS) mounts
                              147,  # DRBD device
                              152,  # EtherDrive Block Devices
                              153,  # Enhanced Metadisk RAID storage units
                              160,  # Carmel 8-port SATA Disks
                              161,  # Carmel 8-port SATA Disks
                              199,  # Veritas volume manager (VxVM) volumes
                              201,  # Veritas VxVM dynamic multipathing driver
                              230,  # ZFS ZVols
                              240,  # LOCAL/EXPERIMENTAL USE
                              241,  # LOCAL/EXPERIMENTAL USE
                              242,  # LOCAL/EXPERIMENTAL USE
                              243,  # LOCAL/EXPERIMENTAL USE
                              244,  # LOCAL/EXPERIMENTAL USE
                              245,  # LOCAL/EXPERIMENTAL USE
                              246,  # LOCAL/EXPERIMENTAL USE
                              247,  # LOCAL/EXPERIMENTAL USE
                              248,  # LOCAL/EXPERIMENTAL USE
                              249,  # LOCAL/EXPERIMENTAL USE
                              250,  # LOCAL/EXPERIMENTAL USE
                              251,  # LOCAL/EXPERIMENTAL USE
                              252,  # LOCAL/EXPERIMENTAL USE
                              253,  # LOCAL/EXPERIMENTAL USE
                              254   # LOCAL/EXPERIMENTAL USE
                              ]
    if major in type_disk_known_majors:
        return 0

    # Same for LVM LVs, but as we cannot use major here
    # (it varies accross distros), use the realpath to check
    if os.path.dirname(dev) == "/dev/mapper":
        return 0

    # list of (major, minor, type) tuples
    blocks = [(fread("%s/dev" % fdev).strip().split(':')[0],
               fread("%s/dev" % fdev).strip().split(':')[1],
               fread("%s/device/type" % fdev).strip())
              for fdev in glob.glob("/sys/block/*")
              if os.path.isfile("%s/device/type" % fdev)]

    for block in blocks:
        if int(block[0]) == major and int(block[1]) == minor:
            return int(block[2])

    return None


def list_scsi_hbas():
    '''
    This function returns the list of HBA indexes for existing SCSI HBAs.
    '''
    return list(set([int(device.partition(":")[0])
                     for device in os.listdir("/sys/bus/scsi/devices")
                     if re.match("[0-9:]+", device)]))


def convert_scsi_path_to_hctl(path):
    '''
    This function returns the SCSI ID in H:C:T:L form for the block
    device being mapped to the udev path specified.
    If no match is found, None is returned.

    >>> import rtslib.utils as utils
    >>> utils.convert_scsi_path_to_hctl('/dev/scd0')
    (2, 0, 0, 0)
    >>> utils.convert_scsi_path_to_hctl('/dev/sr0')
    (2, 0, 0, 0)
    >>> utils.convert_scsi_path_to_hctl('/dev/sda')
    (3, 0, 0, 0)
    >>> utils.convert_scsi_path_to_hctl('/dev/sda1')
    >>> utils.convert_scsi_path_to_hctl('/dev/sdb')
    (3, 0, 1, 0)
    >>> utils.convert_scsi_path_to_hctl('/dev/sdc')
    (3, 0, 2, 0)

    @param path: The udev path to the SCSI block device.
    @type path: string
    @return: An (host, controller, target, lun) tuple of integer
    values representing the SCSI ID of the device, or None if no
    match is found.
    '''
    dev = os.path.realpath(path)
    scsi_devices = [os.path.basename(scsi_dev).split(':')
                    for scsi_dev in glob.glob("/sys/class/scsi_device/*")]
    for (host, controller, target, lun) in scsi_devices:
        scsi_dev = convert_scsi_hctl_to_path(host, controller, target, lun)
        if dev == scsi_dev:
            return (int(host), int(controller), int(target), int(lun))

    return None


def convert_scsi_hctl_to_path(host, controller, target, lun):
    '''
    This function returns a udev path pointing to the block device being
    mapped to the SCSI device that has the provided H:C:T:L.

    >>> import rtslib.utils as utils
    >>> utils.convert_scsi_hctl_to_path(0,0,0,0)
    ''
    >>> utils.convert_scsi_hctl_to_path(2,0,0,0) # doctest: +ELLIPSIS
    '/dev/s...0'
    >>> utils.convert_scsi_hctl_to_path(3,0,2,0)
    '/dev/sdc'

    @param host: The SCSI host id.
    @type host: int
    @param controller: The SCSI controller id.
    @type controller: int
    @param target: The SCSI target id.
    @type target: int
    @param lun: The SCSI Logical Unit Number.
    @type lun: int
    @return: A string for the canonical path to the device, or empty string.
    '''
    try:
        host = int(host)
        controller = int(controller)
        target = int(target)
        lun = int(lun)
    except ValueError:
        raise Exception(
            "The host, controller, target and lun parameter must be integers.")

    scsi_dev_path = "/sys/class/scsi_device"
    sysfs_names = [os.path.basename(name) for name
                   in glob.glob("%s/%d:%d:%d:%d/device/block:*"
                   % (scsi_dev_path, host, controller, target, lun))]
    if len(sysfs_names) == 0:
        sysfs_names = [os.path.basename(name) for name
                       in glob.glob("%s/%d:%d:%d:%d/device/block/*"
                       % (scsi_dev_path, host, controller, target, lun))]
    if len(sysfs_names) > 0:
        for name in sysfs_names:
            name1 = name.partition(":")[2].strip()
            if name1:
                name = name1
            dev = os.path.realpath("/dev/%s" % name)
            try:
                mode = os.stat(dev)[stat.ST_MODE]
            except OSError:
                pass
            if stat.S_ISBLK(mode):
                return dev
    else:
        return ''


def generate_wwn(wwn_type, prefix=None, serial=None):
    '''
    Generates a random WWN of the specified type:
        - unit_serial: T10 WWN Unit Serial.
        - iqn: iSCSI IQN
        - naa: SAS NAA address
    @param wwn_type: The WWN address type.
    @type wwn_type: str
    @returns: A string containing the WWN.
    '''
    wwn_type = wwn_type.lower()
    if wwn_type == 'free':
        return str(uuid.uuid4())
    if wwn_type == 'unit_serial':
        return str(uuid.uuid4())
    elif wwn_type == 'iqn':
        ctx = dict(localname=socket.gethostname().split(".")[0],
                   localarch=os.uname()[4].replace("_", ""))
        if not prefix:
            prefix = 'iqn.2012-01.net.locsol.solarsan.%(localname)s.%(localarch)s'
        prefix = prefix % ctx
        prefix = prefix.strip().lower()
        if not serial:
            serial = "sn.%s" % str(uuid.uuid4())[24:]
        return "%s:%s" % (prefix, serial)
    elif wwn_type == 'naa':
        sas_address = "naa.6001405%s" % str(uuid.uuid4())[:10]
        return sas_address.replace('-', '')
    else:
        raise ValueError("Unknown WWN type: %s." % wwn_type)


def is_valid_wwn(wwn_type, wwn, wwn_list=None):
    '''
    Returns True if the wwn is a valid wwn of type wwn_type.
    @param wwn_type: The WWN address type.
    @type wwn_type: str
    @param wwn: The WWN address to check.
    @type wwn: str
    @param wwn_list: An optional list of wwns to check the wwn parameter from.
    @type wwn_list: list of str
    @returns: bool.
    '''
    wwn_type = wwn_type.lower()

    if wwn_list is not None and wwn not in wwn_list:
        return False
    elif wwn_type == 'free':
        return True
    elif wwn_type == 'iqn' \
            and re.match("iqn\.[0-9]{4}-[0-1][0-9]\..*\..*", wwn) \
            and not re.search(' ', wwn) \
            and not re.search('_', wwn):
        return True
    elif wwn_type == 'naa' \
            and re.match("naa\.[0-9A-Fa-f]{16}$", wwn):
        return True
    elif wwn_type == 'unit_serial' \
            and re.match(
                "[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$", wwn):
        return True
    else:
        return False
