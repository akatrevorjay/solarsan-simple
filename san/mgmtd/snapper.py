

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

from san.conf import config
from san.storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot

from datetime import datetime, timedelta
import time
import threading

from .ordered_set_queue import OrderedSetQueue


# Periodic snapshot of datasets
# Manage created snapshots to specified number
# Implement a runner queue of snapshot deletions


snapshot_conf = dict(
    default=dict(
        dataset='dpool/tmp/omg',
        keep=2,
    ),
    insane=dict(
        every=timedelta(seconds=5),
    ),
    insanest=dict(
        every=timedelta(seconds=30),
    ),

    #frequent=dict(
    #    snapshot_name='15m',
    #    every=timedelta(minutes=15),
    #),
    #hourly=dict(
    #    every=timedelta(hours=1),
    #),
    #daily=dict(
    #    every=timedelta(days=1),
    #),
    #monthly=dict(
    #    every=timedelta(months=1),
    #),
)


class DeletionHandler(threading.Thread):
    delay = 1

    def __init__(self):
        threading.Thread.__init__(self)
        #self._q = Queue()
        self._q = OrderedSetQueue()

    def mark_for_deletion(self, dataset_name, snapshot_name, recursive=False):
        # TODO What if an item is added to the queue during deletion?
        log.debug('Adding to deletion queue: %s@%s recursive=%s',
                  dataset_name,
                  snapshot_name,
                  recursive)
        self._q.put((dataset_name, snapshot_name, recursive))

    def run(self):
        log.debug('Deletion queue running delay=%s.', self.delay)
        while True:
            dataset_name, snapshot_name, recursive = self._q.get()
            name = '%s@%s' % (dataset_name, snapshot_name)

            log.info('Destroying snapshot in deletion queue %s recursive=%s',
                     name,
                     recursive)

            # TODO Exception handling (ie check if it exists first)
            # TODO Retry later if exists (ie if locked)
            dataset = ZDataset.open(dataset_name)
            dataset.destroy_snapshot(snapshot_name, recursive=recursive)

            self._q.task_done()
            time.sleep(self.delay)


class Schedule(object):
    name = None
    snapshot_name = None
    every = None
    dataset_name = None
    recursive = True

    prefix = 'auto-{snapshot_name}-'
    suffix = '%Y-%m-%d-%Y-%H%M%S'

    strftime = True
    priority = 10

    def __init__(self):
        pass

    def __repr__(self):
        return '<%s %s every=%ss>' % (
            self.__class__.__name__,
            self.name,
            self.every_secs)

    @classmethod
    def from_conf(cls, name, conf, deletion_handler):
        self = cls()
        self.name = name
        self.snapshot_name = conf.get('snapshot_name', name)
        self.every = conf['every']
        self.dataset_name = conf['dataset']
        self.keep = conf['keep']

        self.deletion_handler = deletion_handler
        return self

    @property
    def every_secs(self):
        return self.every.total_seconds()

    @property
    def snapshot_format(self):
        return '%s%s' % (self.prefix, self.suffix)

    @property
    def _format_snapshot_name_kw(self):
        return dict(name=self.name,
                    snapshot_name=self.snapshot_name)

    def _format_snapshot_name(self):
        fmt = self._format_snapshot_name_kw
        format_strs = [self.prefix, self.suffix]
        ret = []
        for v in format_strs:
            v = v.format(**fmt)
            if self.strftime:
                v = time.strftime(v)
            ret.append(v)
        return ret

    def get_dataset(self):
        return ZDataset.open(self.dataset_name)

    def run(self):
        log.info('Running %s', self)

        dataset = self.get_dataset()
        prefix, suffix = self._format_snapshot_name()
        snapshot_name = '%s%s' % (prefix, suffix)

        log.info('dataset=%s, snapshot_name=%s', dataset, snapshot_name)

        # Create snap
        log.info('Creating snapshot %s@%s', self.dataset_name, snapshot_name)
        # TODO Exception handling
        dataset.snapshot(snapshot_name, recursive=self.recursive)

        # Get dataset again so it shows the created snapshot
        dataset = self.get_dataset()

        all_snaps = dataset.iter_snapshots_sorted()
        matched_snaps = [x for x in all_snaps
                         if x.snapshot_name.startswith(prefix)]
        # Reverse so newest are first
        matched_snaps.reverse()
        #log.debug('matched_snaps=%s', matched_snaps)
        #unmatched_snaps = set(all_snaps) - set(matched_snaps)
        #log.info('unmatched_snaps=%s', unmatched_snaps)

        # TODO Keep snapshots to be deleted in a queue backed by persistent
        # storage, if snapshot deletion fails, try again later, unless it does
        # not exist.
        delete_snaps = matched_snaps[self.keep:]
        delete_snaps.reverse()
        for snap in delete_snaps:
            log.info('Marking snapshot for deletion: %s', snap.name)
            self.deletion_handler.mark_for_deletion(dataset_name=snap.parent_name,
                                                    snapshot_name=snap.snapshot_name,
                                                    recursive=self.recursive)

        self.schedule_next()

    def schedule_next(self):
        secs = self.every_secs
        log.debug('Scheduling next run for %s in %ss', self, secs)
        self._timer = threading.Timer(secs, self.run)
        self._timer.daemon = True
        self._timer.start()


def main():
    deletion_handler = DeletionHandler()

    default = snapshot_conf['default']

    for name in snapshot_conf:
        if name == 'default':
            continue
        log.info('Schedule %s=%s', name, snapshot_conf[name])

        conf = default.copy()
        conf.update(snapshot_conf[name])

        log.debug('Schedule %s full_conf=%s', name, conf)

        sched = Schedule.from_conf(name, conf, deletion_handler)
        sched.schedule_next()

    deletion_handler.daemon = True
    deletion_handler.start()
    deletion_handler.join()
    #deletion_handler._q.join()

if __name__ == '__main__':
    main()
