
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

#from san.conf import config
from san.storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot

#import zmq
import subprocess
import zerorpc
import zmq
import time

from .async_file_reader import AsynchronousFileLogger
from .backup import Dataset, DatasetSet


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


class Dispatcher(object):
    def __init__(self):
        self._socks = {}
        self._poller = zmq.Poller()

    def add_sock(self, sock, cb, flags=zmq.POLLIN):
        self._poller.register(sock, flags)
        self._socks[sock] = (cb, flags)

    def remove_sock(self, sock):
        self._poller.unregister(sock)
        self._socks.pop(sock, None)

    def run(self):
        self.running = True

        while self.running:
            socks = dict(self._poller.poll())
            if socks:
                log.info('socks=%s', socks)
                for s, sv in self._socks.iteritems():
                    cb, flags = sv
                    if s in socks and socks[s] == flags:
                        cb(s.recv_multipart())


def test(*args, **kwargs):
    log.info('test: args=%s kwargs=%s', args, kwargs)


def main():
    ctx = zmq.Context()
    rtr = ctx.socket(zmq.ROUTER)
    rtr.setsockopt(zmq.IDENTITY, 'srv')
    #rtr.setsockopt(zmq.PROBE_ROUTER, 1)
    rtr.bind('tcp://0.0.0.0:4243')

    #dispatch = Dispatcher()
    #dispatch.add_sock(rtr, test)
    #dispatch.run()

    while True:
        buf = rtr.recv_multipart()
        log.info('got %s', repr(buf))
        peer_id = buf[0]

        if peer_id != 'cli':
            continue

        if buf[1] == 'receive':
            name = buf[2]
            rtr.send_multipart([peer_id, 'ok'])

        if buf[1] == 'receive_data':
            data = buf[2]



if __name__ == '__main__':
    main()
