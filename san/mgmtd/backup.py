

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

from san.conf import config
from san.storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot

from datetime import datetime, timedelta
import time
import threading
import subprocess
import Queue
import zmq

from .ordered_set import OrderedSet
#from .ordered_set_queue import OrderedSetQueue
from .async_file_reader import AsynchronousFileReader


class Dataset(object):
    def __init__(self, name):
        self.name = name
        self.zdataset = ZDataset.open(name)
        self.exists = self.zdataset is not None
        if self.exists:
            #self.snaps = OrderedSet(self.zdataset.iter_snapshots_sorted())
            #self.snaps = self.zdataset.iter_snapshots_sorted(objectify=False)
            self.snaps_list = set(self.zdataset.iter_snapshots_sorted())
            self.snaps = set(self.snaps_list)
            self.snaps_names = set([x.snapshot_name for x in self.snaps])
        else:
            self.snaps_list = set()
            self.snaps = set()
            self.snaps_names = set()


class DatasetSet(object):
    def __init__(self, source, destination):
        self.source = Dataset(source)
        self.destination = Dataset(destination)

    def common_snaps(self):
        return self.source.snaps_names & self.destination.snaps_names

    def snaps_not_in_destination(self):
        return self.source.snaps_names - self.destination.snaps_names

    def send(self, snapshot_name):
        source_snapshot = self.source.zdataset.open_child_snapshot(snapshot_name)

        bufsize = pbufsize = 4096

        cmd_send = ['/sbin/zfs', 'send', '-RpPv', source_snapshot.name]
        log.info('Spawning send: %s', cmd_send)
        psend = subprocess.Popen(cmd_send,
                                 bufsize=pbufsize,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 )
        psend_stderr_q = Queue.Queue()
        psend_stderr_reader = AsynchronousFileReader(psend.stderr, psend_stderr_q)
        psend_stderr_reader.start()

        cmd_recv = ['/sbin/zfs', 'receive', '-nvF', self.destination.name]
        log.info('Spawning recv: %s', cmd_recv)
        precv = subprocess.Popen(cmd_recv,
                                 bufsize=pbufsize,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 )
        precv_stdout_q = Queue.Queue()
        precv_stdout_reader = AsynchronousFileReader(precv.stdout, precv_stdout_q)
        precv_stdout_reader.start()
        precv_stderr_q = Queue.Queue()
        precv_stderr_reader = AsynchronousFileReader(precv.stderr, precv_stderr_q)
        precv_stderr_reader.start()

        def check_async_readers():
            while not psend_stderr_q.empty():
                line = psend_stderr_q.get()
                line = line.rstrip("\n")
                log.info('psend_stderr: %s', repr(line))
            while not precv_stdout_q.empty():
                line = precv_stdout_q.get()
                line = line.rstrip("\n")
                log.info('precv_stdout: %s', repr(line))
            while not precv_stderr_q.empty():
                line = precv_stderr_q.get()
                line = line.rstrip("\n")
                log.info('precv_stderr: %s', repr(line))

        while True:
            check_async_readers()

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

        # Give async readers a second to catch up, matters on say broken pipes
        log.info('Sleeping for async readers')
        time.sleep(0.1)
        check_async_readers()

        log.info('Closing send stdout')
        psend.stdout.close()

        log.info('Closing recv stdin')
        precv.stdin.close()

        log.info('Waiting for async reader threads to join')
        psend_stderr_reader.join()
        precv_stdout_reader.join()
        precv_stderr_reader.join()

        log.info('Closing async reader FDs')
        psend.stderr.close()
        precv.stdout.close()
        precv.stderr.close()

        log.info('Checking async readers one last time')
        time.sleep(0.1)
        check_async_readers()

        log.info('Waiting for procs to end')
        precv.wait()
        psend.wait()


ds = DatasetSet('dpool/tmp/omg', 'dpool/tmp/omg_dest')
source = ds.source
destination = ds.destination


def main():
    pass


if __name__ == '__main__':
    main()
