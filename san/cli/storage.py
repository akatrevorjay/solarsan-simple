
from .base import ConfigNode
from ..storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot


class Pools(ConfigNode):
    def __init__(self, parent):
        ConfigNode.__init__(self, parent)

        for pool in ZPool.list():
            Pool(self, pool)

    def ui_command_create_pool(self):
        raise NotImplementedError()


class _StorageChildBase(ConfigNode):
    def __init__(self, parent, obj):
        self.obj = obj
        # Pools don't have basename
        name = getattr(obj, 'basename', obj.name)
        ConfigNode.__init__(self, parent, name=name)

        for d in self.dataset.iter_datasets():
            Dataset.from_zdataset(self, d)

    _pool = None

    @property
    def pool(self):
        if not self._pool:
            if isinstance(self.obj, ZPool):
                self._pool = self.obj
            elif isinstance(self.obj, ZDataset):
                self._pool = self.obj.pool
        return self._pool

    _dataset = None

    @property
    def dataset(self):
        if not self._dataset:
            if isinstance(self.obj, ZPool):
                self._dataset = self.obj.filesystem
            elif isinstance(self.obj, ZDataset):
                self._dataset = self.obj
        return self._dataset


class Dataset(_StorageChildBase):
    _zfs_type_mask = ZDataset._zfs_type_mask

    def __init__(self, parent, obj):
        _StorageChildBase.__init__(self, parent, obj)

        # Dataset config group
        self.define_config_group_param('dataset', 'compression', 'string', 'Enable compression')
        self.define_config_group_param('dataset', 'dedup', 'string', 'Enable dedupe')

        self.define_config_group_param('dataset', 'compressratio', 'string', 'Compresstion ratio', writable=False)
        self.define_config_group_param('dataset', 'used', 'string', 'Used space', writable=False)
        self.define_config_group_param('dataset', 'usedbysnapshots', 'string', 'Used space by snapshots', writable=False)
        self.define_config_group_param('dataset', 'usedbydataset', 'string', 'Used space by dataset', writable=False)
        self.define_config_group_param('dataset', 'usedbychildren', 'string', 'Used space by children', writable=False)
        self.define_config_group_param('dataset', 'usedbyrefreservation', 'string', 'Used space by referenced reservation', writable=False)
        self.define_config_group_param('dataset', 'referenced', 'string', 'Referenced space', writable=False)
        self.define_config_group_param('dataset', 'available', 'string', 'Available space', writable=False)
        self.define_config_group_param('dataset', 'creation', 'string', 'Creation date', writable=False)

        self.define_config_group_param('dataset', 'reservation', 'string', 'Space reservation')
        self.define_config_group_param('dataset', 'refreservation', 'string', 'Referenced space reservation')

    def summary(self):
        desc = '%s used=%s' % (self.dataset.type_name, self.dataset.props['used'])
        health = True
        return desc, health

    @classmethod
    def _find_subclass_for_type_mask(cls, type_mask):
        for scls in cls.__subclasses__():
            if type_mask & scls._zfs_type_mask:
                return scls
        return cls

    @classmethod
    def from_zdataset(cls, parent, obj):
        """Creates a dataset object from an existing ZDataset.
        """
        # Find type on init of Dataset and use proper subclass
        obj_type = obj.type
        # TODO is there a way to trawl up mro to find the parent without
        # specifying the hard class name here?
        obj_cls = Dataset._find_subclass_for_type_mask(obj_type)

        self = obj_cls(parent, obj)
        return self

    def ui_command_destroy(self):
        """ Destroy Dataset. """
        raise NotImplementedError()

    """ Properties """

    def ui_getgroup_dataset(self, key):
        """ Get Dataset property. """
        return self.dataset.props[key]

    def ui_setgroup_dataset(self, key, value):
        """ Set Dataset property. """
        self.dataset.props[key] = value


class _SnapshottableDataset:
    def ui_command_create_snapshot(self, name, recursive=True):
        """ Creates a named snapshot. """
        self.dataset.snapshot(name, recursive=recursive)

    def ui_command_destroy_snapshot(self, name, recursive=True):
        """ Destroys a named snapshot. """
        self.dataset.destroy_snapshot(name, recursive=recursive)


class Filesystem(Dataset, _SnapshottableDataset):
    _zfs_type_mask = ZFilesystem._zfs_type_mask

    def __init__(self, parent, obj):
        Dataset.__init__(self, parent, obj)

        # Filesystem config group
        self.define_config_group_param('filesystem', 'atime', 'string', 'Keep file access times up to date')
        self.define_config_group_param('filesystem', 'quota', 'string', 'Quota for filesystem')
        self.define_config_group_param('filesystem', 'mounted', 'bool', 'Currently mounted', writable=False)

    # Filesystem config group

    def ui_getgroup_filesystem(self, key):
        """ Get Filesystem property. """
        return Dataset.ui_getgroup_dataset(self, key)

    def ui_setgroup_filesystem(self, key, value):
        """ Set Filesystem property. """
        return Dataset.ui_setgroup_dataset(self, key, value)

    # Operations

    def ui_command_create_filesystem(self, name):
        """ Create Filesystem. """
        raise NotImplementedError()

    def ui_command_create_volume(self, name, size):
        """ Create Volume. """
        raise NotImplementedError()

    def ui_command_ls_snapshots(self):
        """ List snapshots. """
        for s in self.dataset.iter_snapshots_sorted():
            print s.snapshot_name


class Volume(Dataset, _SnapshottableDataset):
    _zfs_type_mask = ZVolume._zfs_type_mask

    def __init__(self, parent, obj):
        Dataset.__init__(self, parent, obj)

        # Volume config group
        self.define_config_group_param('volume', 'volblocksize', 'string', 'Volume Block size', writable=False)
        self.define_config_group_param('volume', 'volsize', 'string', 'Volume Size')

    def summary(self):
        desc = '%s used=%s size=%s' % (self.dataset.type_name,
                                       self.dataset.props['used'],
                                       self.dataset.props['volsize'])
        health = True
        return desc, health

    # Volume config group

    def ui_getgroup_volume(self, key):
        """ Get Volume property. """
        return Dataset.ui_getgroup_dataset(self, key)

    def ui_setgroup_volume(self, key, value):
        """ Set Volume property. """
        return Dataset.ui_setgroup_dataset(self, key, value)


class Pool(Filesystem):
    _zfs_type_mask = ZPool._zfs_type_mask

    def __init__(self, parent, obj):
        Filesystem.__init__(self, parent, obj)

        # Pool config group
        self.define_config_group_param('pool', 'comment', 'string', 'Comment')
        self.define_config_group_param('pool', 'dedupditto', 'string', 'Number of copies of each deduplicated block to save')
        self.define_config_group_param('pool', 'autoexpand', 'string', 'Automatically expand pool if drives increase in size')
        self.define_config_group_param('pool', 'autoreplace', 'string', 'Automatically replace failed drives with any specified hot spare(s)')

        self.define_config_group_param('pool', 'health', 'string', 'Health', writable=False)
        self.define_config_group_param('pool', 'dedupratio', 'string', 'Dedupe ratio', writable=False)

        self.define_config_group_param('pool', 'capacity', 'string', 'Percentage filled', writable=False)
        self.define_config_group_param('pool', 'allocated', 'string', 'Allocated space', writable=False)
        self.define_config_group_param('pool', 'free', 'string', 'Free space', writable=False)
        self.define_config_group_param('pool', 'size', 'string', 'Total space', writable=False)

    def summary(self):
        desc = '%s %s/%s %s' % (self.pool.type_name,
                             self.pool.props['free'],
                             self.pool.props['size'],
                             self.pool.props['capacity'])
        health = str(self.pool.props['health']) == 'ONLINE'
        return desc, health

    def ui_command_destroy(self):
        """ Destroy Pool. """
        # TODO Destroy pool
        raise NotImplementedError()

    def ui_command_attach(self):
        """ Attach drive to Pool. """
        # TODO List available disks, choose one
        # TODO List available pool disks, choose one
        # TODO Attach disk
        raise NotImplementedError()

    def ui_command_clear(self):
        """ Clear errors on Pool. """
        # TODO Clear Pool
        raise NotImplementedError()

    def ui_command_add(self):
        """ Add drive to Pool. """
        # TODO List available disks, choose one
        raise NotImplementedError()

    def ui_command_detach(self):
        """ Detach drive from Pool mirror vdev. """
        # TODO Detach drive
        raise NotImplementedError()

    def ui_command_iostat(self):
        """ Show IO Statistics. """
        # TODO IOstat
        raise NotImplementedError()

    """ Properties """

    def ui_getgroup_pool(self, key):
        """ Get Pool property. """
        return self.pool.props[key]

    def ui_setgroup_pool(self, key, value):
        """ Set Pool property. """
        self.pool.props[key] = value


