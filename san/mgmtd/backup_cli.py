

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

import subprocess
import zerorpc

#from san.conf import config
from san.storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot

from .async_file_reader import AsynchronousFileLogger
from .backup import Dataset, DatasetSet


c = zerorpc.Client('tcp://localhost:4242')

source = Dataset.from_local('dpool/tmp/omg')
#ds = DatasetSet(source)


def main():
    log.info('Starting source dataset %s',
             repr(source.name))

    latest_snap_needed = c.find_latest_snap_needed(source.name, source.snaps)
    if not latest_snap_needed:
        log.info('No new snaps are needed, up to date. =)')
        return

    log.info('Latest snap needed by destination: %s',
             repr(latest_snap_needed))

    common_snaps = c.snaps_intersect(source.name, source.snaps)
    latest_common_snap = source.find_latest_snap_in(common_snaps)
    incremental = bool(latest_common_snap)

    if incremental:
        log.info('Incremental from %s to %s',
                 repr(latest_common_snap),
                 repr(latest_snap_needed))

        # Check if we're trying to send a snapshot that's actually previous to
        # the latest common snapshot.
        latest_snap_needed_idx = source.snaps.index(latest_snap_needed)
        latest_common_snap_idx = source.snaps.index(latest_common_snap)
        if latest_common_snap_idx > latest_snap_needed_idx:
            log.info('Source snapshot is previous to latest common snapshot')
            return
    else:
        log.info('Full to %s',
                 repr(latest_snap_needed))

    bufsize = pbufsize = 4096

    if incremental:
        cmd_send = ['/sbin/zfs', 'send', '-pPv', '-i',
                    latest_common_snap,
                    '%s@%s' % (source.name, latest_snap_needed),
                    ]
    else:
        cmd_send = ['/sbin/zfs', 'send', '-pPv',
                    '%s@%s' % (source.name, latest_snap_needed),
                    ]
    log.info('Spawning send: %s', cmd_send)
    psend = subprocess.Popen(cmd_send,
                             bufsize=pbufsize,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             )
    psend_stderr_reader = AsynchronousFileLogger(psend.stderr, log, 'send_stderr')
    psend_stderr_reader.start()

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
            # TODO write to receive
            #precv.stdin.write(buf)
            #precv.stdin.flush()
            pass
        except IOError:
            log.error('Broken pipe on recv')
            break

        #log.info('Sleeping')
        #time.sleep(1)

    log.info('Closing send stdout')
    psend.stdout.close()

    log.info('Waiting for async reader threads to join')
    psend_stderr_reader.join()

    #log.info('Closing async reader FDs')
    #psend.stderr.close()

    log.info('Waiting for procs to end')
    psend.wait()



if __name__ == '__main__':
    main()
