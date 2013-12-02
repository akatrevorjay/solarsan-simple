#!/usr/bin/env python

import os
import configshell
from pyzfscore.zfs import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot


class ConfigNode(configshell.node.ConfigNode):
    def __init__(self, *args, **kwargs):
        # Figure out name
        name = kwargs.pop('name', None)
        if not name:
            name = getattr(self, 'name', None)
        if not name:
            name = self.__class__.__name__.lower()

        # Create args list
        cargs = [name]
        cargs.extend(args)

        configshell.node.ConfigNode.__init__(self, *cargs, **kwargs)


class MySystemRoot(ConfigNode):
    def __init__(self, shell):
        ConfigNode.__init__(self, shell=shell, name='/')

        System(self)
        Storage(self)


class Networking(ConfigNode):
    pass


class System(ConfigNode):
    def __init__(self, parent):
        ConfigNode.__init__(self, parent)

    def ui_command_uptime(self):
        """ uptime - Tell how long the system has been running. """
        os.system("uptime")


class Storage(ConfigNode):
    def __init__(self, parent):
        ConfigNode.__init__(self, parent)
        Pools(self)


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
        raise NotImplementedError()


class _SnapshottableDataset:
    def ui_command_create_snapshot(self, name, recursive=True):
        """ Creates a named snapshot. """
        self.dataset.snapshot(name, recursive=recursive)


class Filesystem(Dataset, _SnapshottableDataset):
    _zfs_type_mask = ZFilesystem._zfs_type_mask

    def ui_command_create_filesystem(self, name):
        raise NotImplementedError()

    def ui_command_create_volume(self, name, size):
        raise NotImplementedError()

    def ui_command_ls_snapshots(self):
        for s in self.dataset.iter_snapshots_sorted():
            print s.name


class Volume(Dataset, _SnapshottableDataset):
    _zfs_type_mask = ZVolume._zfs_type_mask

    def ui_command_resize(self, size):
        raise NotImplementedError()


class Pool(Filesystem):
    _zfs_type_mask = ZPool._zfs_type_mask

    def __init__(self, parent, obj):
        _StorageChildBase.__init__(self, parent, obj)

    def ui_command_destroy(self):
        raise NotImplementedError()


def main():
    shell = configshell.shell.ConfigShell('~/.myshell')
    root_node = MySystemRoot(shell)
    shell.run_interactive()

if __name__ == "__main__":
    main()
