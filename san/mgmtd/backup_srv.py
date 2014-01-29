

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

#from san.conf import config
from san.storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot

#import zmq
import subprocess
import zerorpc
import zmq

from .async_file_reader import AsynchronousFileLogger
from .backup import Dataset, DatasetSet


class BackupRPC(object):
    def _get_source(self, name, snaps):
        return Dataset.from_remote(name, snaps)

    def _get_dest(self, name):
        # TODO Select dataset, secure this
        #dataset = 'dpool/dest/%s' % dataset
        #return ZDataset.open('dpool/dest')
        return Dataset.from_local('dpool/dest')

    def _get_ds(self, name, source_snaps):
        source = self._get_source(name, source_snaps)
        dest = self._get_dest(name)
        ds = DatasetSet(source, dest)
        return ds

    def find_latest_snap_needed(self, name, source_snaps):
        """ Returns the latest snap needed for @name in @source_snaps. """
        ds = self._get_ds(name, source_snaps)
        snaps = ds.snaps_needed_by_dest()
        latest_snap = ds.source.find_latest_snap_in(snaps)
        return latest_snap

    def receive(self, name, from_snap, to_snap):
        dest = self._get_dest(name)

        bufsize = pbufsize = 4096

        cmd_recv = ['/sbin/zfs', 'receive', '-vFu', dest.name]
        #cmd_recv = ['/sbin/zfs', 'receive', '-vFdu', self.dest.name]
        log.info('Spawning recv: %s', cmd_recv)
        precv = subprocess.Popen(cmd_recv,
                                 bufsize=pbufsize,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 )
        precv_stdout_reader = AsynchronousFileLogger(precv.stdout, log, 'recv_stdout')
        precv_stdout_reader.start()
        precv_stderr_reader = AsynchronousFileLogger(precv.stderr, log, 'recv_stderr')
        precv_stderr_reader.start()


    """ Development/Testing """

    def find_snaps_needed(self, name, source_snaps):
        log.info('Finding snaps needed for dataset %s',
                 repr(name))
        ds = self._get_ds(name, source_snaps)
        return list(ds.snaps_needed_by_dest())

    def test(self, *args, **kwargs):
        log.info('test: args=%s kwargs=%s', args, kwargs)

    def snaps_difference(self, name, source_snaps):
        """ Returns entries in @source_snaps that we do not have for @dataset. """
        log.info('Snaps difference for dataset %s',
                 repr(name))
        ds = self._get_ds(name, source_snaps)
        return list(ds.snaps_difference())

    def snaps_intersect(self, name, source_snaps):
        """ Returns entries in @source_snaps that we do have for @dataset. """
        log.info('Snaps difference for dataset %s',
                 repr(name))
        ds = self._get_ds(name, source_snaps)
        return list(ds.snaps_intersect())

    def ls_snapshots(self, name):
        log.info('Listing snaps for dataset %s',
                 repr(name))
        dest = self._get_dest(name)
        return dest.snaps


def main():
    s = zerorpc.Server(BackupRPC())
    s.bind('tcp://0.0.0.0:4242')
    s.run()


if __name__ == '__main__':
    main()
