

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

from san.conf import config
from san.storage import ZPool, ZDataset, ZFilesystem, ZVolume, ZSnapshot

from datetime import datetime, timedelta


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
        every=timedelta(seconds=1),
    ),
    frequent=dict(
        snapshot_name='15m',
        every=timedelta(minutes=15),
    ),
    hourly=dict(
        every=timedelta(hours=1),
    ),
    daily=dict(
        every=timedelta(days=1),
    ),
    #monthly=dict(
    #    every=timedelta(months=1),
    #),
)


#from queue import Queue
#deletion_queue = Queue()


import time
import sched


class SnapperSchedule(object):
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

    @classmethod
    def from_conf(cls, s, name, conf):
        self = cls()
        self._scheduler = s
        self.name = name
        self.snapshot_name = conf.get('snapshot_name', name)
        self.every = conf['every']
        self.dataset_name = conf['dataset']
        self.keep = conf['keep']
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
        dataset.snapshot(snapshot_name, recursive=self.recursive)

        # Get dataset again so it shows the created snapshot
        dataset = self.get_dataset()

        all_snaps = dataset.iter_snapshots_sorted()
        matched_snaps = [x for x in all_snaps
                         if x.snapshot_name.startswith(prefix)]
        # Reverse so newest are first
        matched_snaps.reverse()
        log.debug('matched_snaps=%s', matched_snaps)
        #unmatched_snaps = set(all_snaps) - set(matched_snaps)
        #log.info('unmatched_snaps=%s', unmatched_snaps)

        for snap in matched_snaps[self.keep:]:
            log.info('Destroying obsolete snapshot %s', snap)
            dataset.destroy_snapshot(snap.snapshot_name, recursive=self.recursive)

        self.schedule_next()

    def schedule_next(self):
        secs = self.every_secs
        pri = self.priority
        log.debug('Scheduling next run for %s in %ss with pri=%s', self, secs, pri)
        self._scheduler.enter(secs, pri, self.run, ())


def main():
    s = sched.scheduler(time.time, time.sleep)

    default = snapshot_conf['default']

    for name in snapshot_conf:
        if name == 'default':
            continue
        log.info('Schedule %s=%s', name, snapshot_conf[name])

        conf = default.copy()
        conf.update(snapshot_conf[name])

        log.debug('Schedule %s full_conf=%s', name, conf)

        snapshot_sched = SnapperSchedule.from_conf(s, name, conf)
        snapshot_sched.schedule_next()

    s.run()


if __name__ == '__main__':
    main()
