
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
        #log.info('got %s', repr(buf))
        peer_id = buf[0]

        log.info('Peer %s sent %s',
                 repr(peer_id),
                 repr(buf[1]))

        if peer_id != 'cli':
            continue

        if buf[1] == 'receive_open':
            #name = buf[2]
            name = 'dpool/dest'

            ## Spawn receive process

            bufsize = pbufsize = 4096

            cmd_recv = ['/sbin/zfs', 'receive', '-nvFu', name]
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

            rtr.send_multipart([peer_id, 'ok'])

        if buf[1] == 'receive_data':
            try:
                precv.stdin.write(buf[2])
                precv.stdin.flush()
            except IOError:
                log.error('Broken pipe on recv')



        if buf[1] == 'receive_close':
            try:
                precv.stdin.flush()
            except IOError:
                log.error('Broken pipe on recv')

            log.info('Closing recv stdin')
            precv.stdin.close()

            log.info('Waiting for async reader threads to join')
            precv_stdout_reader.join()
            precv_stderr_reader.join()

            #log.info('Closing async reader FDs')
            #precv.stdout.close()
            #precv.stderr.close()

            log.info('Waiting for procs to end')
            precv.wait()

            rtr.send_multipart([peer_id, 'ok'])


if __name__ == '__main__':
    main()
