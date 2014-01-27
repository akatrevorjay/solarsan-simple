

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
from .async_file_reader import AsynchronousFileReader, AsynchronousFileLogger


class AsynchronousFileReaderLogger(threading.Thread):
    def __init__(self, fd, log_prefix):
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._q = Queue.Queue()
        self._log_prefix = log_prefix
        self._reader = AsynchronousFileReader(self._fd, self._q)
        self._reader.start()

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        while not self._reader.eof():
            while not self._q.empty():
                line = self._q.get()
                line = line.rstrip("\n")
                log.info('%s: %s', self._log_prefix, repr(line))

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return self._reader.eof()


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
        psend_stderr_reader = AsynchronousFileLogger(psend.stderr, log, 'send_stderr')
        psend_stderr_reader.start()

        cmd_recv = ['/sbin/zfs', 'receive', '-nvFd', self.destination.name]
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
