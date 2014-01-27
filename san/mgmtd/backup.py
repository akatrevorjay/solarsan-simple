

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

#from san.conf import config
from san.storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot

#from datetime import datetime, timedelta
#import time
import re
import collections
import subprocess
#import zmq

from .async_file_reader import AsynchronousFileLogger


class Dataset(object):

    def __init__(self, name):
        self.name = name
        self.zdataset = ZDataset.open(name)
        self.exists = self.zdataset is not None
        if self.exists:
            self.snaps = self.zdataset.iter_snapshots_sorted()
            self.snaps_names = [x.snapshot_name for x in self.snaps]
        else:
            self.snaps = list()
            self.snaps_names = list()

    def index_snaps_names(self, snaps_names):
        return collections.Counter(
            {k: self.snaps_names.index(k) for k in snaps_names}
        )

    def order_snaps_names(self, snaps_names):
        indexes = self.index_snaps_names(snaps_names)
        return sorted(indexes, key=lambda x: indexes[x])

    def find_latest_snap_in(self, snaps_names):
        indexes = self.index_snaps_names(snaps_names)
        top = indexes.most_common(1)
        if top:
            return top[0][0]


class DatasetSet(object):
    def __init__(self, source, destination):
        self.source = Dataset(source)
        self.destination = Dataset(destination)

    def snaps_intersect(self):
        return set(self.source.snaps_names) & set(self.destination.snaps_names)

    def snaps_difference(self):
        return set(self.source.snaps_names) - set(self.destination.snaps_names)

    destination_snaps_needed_filter = re.compile('^auto-(daily|weekly|monthly|insane|insanest|trevorj)-')

    def snaps_needed_by_destination(self, filter=True):
        snaps = self.snaps_difference()
        if filter:
            #log.info('Snaps needed by destination before culling: %s', snaps)
            # Filter snaps according to above filter, this way we don't end up
            # relying on snaps that aren't kept very long
            snaps = [x for x in snaps if self.destination_snaps_needed_filter.match(x)]
            # TODO WTF Why does a RE match automatically anchor itself and
            # require .* prefix??
            #snaps = [x for x in snaps if re.match('.*trevor', x)]
            #log.info('Snaps needed by destination before culling after filter: %s', snaps)

        common_snaps = self.snaps_intersect()
        latest_common_snap = self.source.find_latest_snap_in(common_snaps)
        latest_common_snap_idx = self.source.snaps_names.index(latest_common_snap)

        indexes = self.source.index_snaps_names(snaps)
        for k, v in indexes.iteritems():
            if v < latest_common_snap_idx:
                snaps.remove(k)

        return snaps

    def send_latest_snap_needed_by_destination(self):
        snaps = self.snaps_needed_by_destination()
        latest_snap = self.source.find_latest_snap_in(snaps)
        if latest_snap:
            return self.send(latest_snap)
        else:
            log.info('Up to date! =)')

    def send(self, snapshot_name):
        log.info('Preparing for send of snapshot %s', snapshot_name)
        source_snapshot = self.source.zdataset.open_child_snapshot(snapshot_name)
        source_snapshot_index = self.source.snaps_names.index(snapshot_name)

        common_snaps = self.snaps_intersect()
        latest_common_snapshot_name = self.source.find_latest_snap_in(common_snaps)
        incremental = bool(latest_common_snapshot_name)
        log.info('Incremental: %s', incremental)

        if incremental:
            latest_common_snapshot_index = self.source.snaps_names.index(latest_common_snapshot_name)
            log.info('Latest common snapshot: %s', latest_common_snapshot_name)

            # Check if we're trying to send a snapshot that's actually previous to
            # the latest common snapshot.
            if latest_common_snapshot_index > source_snapshot_index:
                log.info('Source snapshot is previous to latest common snapshot')
                return

        bufsize = pbufsize = 4096

        if incremental:
            cmd_send = ['/sbin/zfs', 'send', '-pPv', '-i', latest_common_snapshot_name, source_snapshot.name]
        else:
            cmd_send = ['/sbin/zfs', 'send', '-pPv', source_snapshot.name]
        log.info('Spawning send: %s', cmd_send)
        psend = subprocess.Popen(cmd_send,
                                 bufsize=pbufsize,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 )
        psend_stderr_reader = AsynchronousFileLogger(psend.stderr, log, 'send_stderr')
        psend_stderr_reader.start()

        cmd_recv = ['/sbin/zfs', 'receive', '-vFu', self.destination.name]
        #cmd_recv = ['/sbin/zfs', 'receive', '-vFdu', self.destination.name]
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

        while True:
            try:
                buf = psend.stdout.read(bufsize)
            except IOError:
                log.error('Broken pipe on send')
                break

            if not buf:
                log.info('Got NULL buf, breaking')
                break

            try:
                precv.stdin.write(buf)
                precv.stdin.flush()
            except IOError:
                log.error('Broken pipe on recv')
                break

            #log.info('Sleeping')
            #time.sleep(1)

        log.info('Closing send stdout')
        psend.stdout.close()

        log.info('Closing recv stdin')
        precv.stdin.close()

        log.info('Waiting for async reader threads to join')
        psend_stderr_reader.join()
        precv_stdout_reader.join()
        precv_stderr_reader.join()

        #log.info('Closing async reader FDs')
        #psend.stderr.close()
        #precv.stdout.close()
        #precv.stderr.close()

        log.info('Waiting for procs to end')
        precv.wait()
        psend.wait()


ds = DatasetSet('dpool/tmp/omg', 'dpool/dest')
source = ds.source
destination = ds.destination


def main():
    pass


if __name__ == '__main__':
    main()
