
import logging
log = logging.getLogger(__name__)

import os
from uuid import uuid4

from ..utils.exceptions import FormattedException, ignored
from ..storage import ZVolume

from .rtsutils import generate_wwn, is_valid_wwn
from .scst import scstsys


class TargetBaseException(FormattedException):
    pass


def dictattrs(**attrs):
    return '; '.join(['%s=%s' % (k, v) for k, v in attrs.iteritems()])


def get_handler(handler):
    return getattr(scstsys.handlers, handler, None)


def get_driver(driver):
    return getattr(scstsys.targets, driver, None)


def get_target(driver, target):
    driver = get_driver(driver)
    if not driver:
        return
    return getattr(driver, target, None)


def get_ini_group(driver, target, group):
    tgt = get_target(driver, target)
    if not tgt:
        return
    return getattr(tgt.ini_groups, group, None)


class BackStoreError(TargetBaseException):
    pass


class BackStoreActiveError(BackStoreError):
    pass


class BackStoreNotActiveError(BackStoreError):
    pass


class BackStore(object):
    # Name
    name = None
    # Handler
    handler = None

    class handlers:
        """ SCST BackStore Handler Choices """
        BLOCKIO = 'vdisk_blockio'
        FILEIO = 'vdisk_fileio'

    # Checks/Helpers

    @property
    def active(self):
        return bool(str(self.name) in scstsys.devices)

    # SCST helpers

    @property
    def _scsthnd(self):
        return get_handler(self.handler)

    @property
    def _scstdev(self):
        return getattr(scstsys.devices, self.name, None)

    # attributes

    attributes = None

    @property
    def _scstattrs(self):
        if self.attributes:
            return dictattrs(**self.attributes)
        else:
            return ''

    # Config

    def load(self):
        #TODO load target from config
        raise NotImplementedError()

    def save(self):
        #TODO save target to config
        raise NotImplementedError()

    # Operations

    def start(self, target, group):
        log.debug('Starting backstore %s for Group %s Target %s', self, group, target)
        with ignored(BackStoreActiveError):
            self.open()
        return True

    def stop(self, target, group):
        log.debug('Stopping backstore %s for Group %s Target %s', self, group, target)
        # TODO What about a backstore that's used in multiple groups or targets?
        with ignored(BackStoreNotActiveError):
            self.close()
        return True

    def open(self):
        if self.active:
            raise BackStoreActiveError(self)
        log.debug('Opening backstore device %s', self)
        self._scsthnd.mgmt = 'add_device {0.name} {0._scstattrs}'.format(self)
        return True

    def close(self):
        if not self.active:
            raise BackStoreNotActiveError(self)
        log.debug('Closing backstore device %s', self)
        self._scsthnd.mgmt = 'del_device {0.name}'.format(self)
        return True

    def resync_size(self):
        if not self.active:
            raise BackStoreNotActiveError(self)
        log.debug('Resyncing backstore device %s', self)
        self._scstdev.resync_size = 0
        return True


class BlockDeviceBackStore(BackStore):
    # Device path
    path = None
    # Handler
    handler = BackStore.handlers.BLOCKIO

    @property
    def attributes(self):
        return dict(filename=self.path)

    @property
    def available(self):
        # TODO Should really check if it's RW if not self.is_active I suppose
        return os.path.exists(self.path)


class ZVolumeBackStore(BlockDeviceBackStore):
    # ZVolume name
    volume_name = None

    @classmethod
    def from_zvolume(cls, volume):
        self = cls()
        self.volume = volume
        return self

    # ZVolume helper, it's possible that the zvolume could no longer exist, so
    # be wary of such.

    _volume = None

    @property
    def volume(self):
        """ Returns ZVolume object. """
        if not self._volume:
            self._volume = ZVolume.open(self.volume_name)
        return self._volume

    @volume.setter
    def volume(self, zvol):
        if not zvol.exists():
            raise ValueError('ZVolume "%s" does not exist.' % zvol)
        self._volume = zvol
        self.volume_name = zvol.name
        # TODO Maybe this should be done only if we don't have one or are
        # closed? This could leave opened zombie backstores.
        self.name = self.volume_name.replace('/', '__')

    @property
    def path(self):
        """ Returns path of ZVolume block device. """
        return '/dev/zvol/%s' % self.volume_name


class AclError(FormattedException):
    pass


class Acl(object):
    # List of allowed initiators
    initiators = None

    # TODO insecure option
    #insecure = m.BooleanField()

    # TODO chap auth
    #chap = m.BooleanField()
    #chap_user = m.StringField()
    #chap_pass = m.StringField()

    def start(self, target, group):
        log.debug('Starting %s for %s for %s', self, group, target)
        return self.add_to_target_portal_group(target, group)

    def stop(self, target, group):
        log.debug('Stopping %s for %s for %s', self, group, target)
        return self.remove_from_target_portal_group(target, group)

    def add_to_target_portal_group(self, target, group):
        ini_group = get_ini_group(target.driver, target.name, group.name)
        if not ini_group:
            log.warn('Cannot get target %s portal group %s initiator group.', target, group)
            return

        for initiator in self.initiators:
            if initiator in ini_group.initiators:
                continue
            log.debug('Adding intiator %s for %s for %s for %s',
                      initiator, self, group, target)
            ini_group.initiators.mgmt = 'add %s' % initiator

    def remove_from_target_portal_group(self, target, group):
        ini_group = get_ini_group(target.driver, target.name, group.name)
        if not ini_group:
            log.warn('Cannot get target %s portal group %s initiator group.', target, group)
            return

        for initiator in self.initiators:
            if initiator not in ini_group.initiators:
                continue
            log.debug('Removing initiator %s for %s for %s for %s',
                      initiator, self, group, target)
            ini_group.initiators.mgmt = 'del %s' % initiator

        # TODO This should not happen. We want to be able to append
        # multiple Acls
        self.remove_all_from_target_portal_group(target, group)

    def remove_all_from_target_portal_group(self, target, group):
        ini_group = get_ini_group(target.driver, target.name, group.name)
        if not ini_group:
            log.warn('Cannot get target %s portal group %s initiator group.', target, group)
            return

        log.debug('Clearing all initiators for %s for %s for %s',
                  self, group, target)
        ini_group.initiators.mgmt = 'clear'


class PortalGroupError(TargetBaseException):
    pass


class PortalGroup(object):
    # Name
    name = None
    # List of BackStores
    luns = None
    # Acl
    acl = None

    def __init__(self):
        self.acl = Acl()
        self.luns = list()

    def is_active_on_target(self, target):
        tgt = get_target(target.driver, target.name)
        return tgt and self.name in tgt.ini_groups

    def start(self, target):
        log.debug('Starting PortalGroup %s for Target %s', self, target)

        self._add_portal_group(target)
        self._add_acl(target)
        self._add_luns(target)

        return True

    def stop(self, target):
        log.debug('Stopping Group %s for Target %s', self, target)

        self._remove_luns(target)
        self._remove_acl(target)
        self._remove_portal_group(target)

        return True

    def _add_portal_group(self, target):
        if not self.is_active_on_target(target):
            log.debug('Adding PortalGroup %s for Target %s', self, target)
            tgt = get_target(target.driver, target.name)
            if not tgt:
                raise PortalGroupError('Could not get target {0.name}'.format(target))
            tgt.ini_groups.mgmt = 'create %s' % self.name
        return True

    def _remove_portal_group(self, target):
        if self.is_active_on_target(target):
            log.debug('Removing Group %s for Target %s', self, target)
            tgt = get_target(target.driver, target.name)
            if not tgt:
                raise PortalGroupError('Could not get target {0.name}'.format(target))
            tgt.ini_groups.mgmt = 'del %s' % self.name

    def _add_acl(self, target):
        log.debug('Adding Acl %s for Group %s for Target %s', self.acl, self, target)
        return self.acl.start(target, self)

    def _remove_acl(self, target):
        log.debug('Removing Acl %s for Group %s for Target %s', self.acl, self, target)
        return self.acl.stop(target, self)

    def _add_luns(self, target):
        ini_group = get_ini_group(target.driver, target.name, self.name)

        for lun, backstore in enumerate(self.luns):
            lun += 1

            if not backstore.active:
                log.debug('Starting backstore %s for %s for %s', backstore, self, target)
                backstore.start(target, self)

            if not str(lun) in ini_group.luns:
                log.debug('Adding lun %d with backstore %s for %s for %s', lun, backstore, self, target)
                """parameters: read_only"""
                ini_group.luns.mgmt = 'add {0.name} {1}'.format(backstore, lun)

    def _remove_luns(self, target):
        ini_group = get_ini_group(target.driver, target.name, self.name)

        for lun, backstore in enumerate(self.luns):
            lun += 1

            if ini_group and str(lun) in ini_group.luns:
                log.debug('Removing lun %d with backstore %s for %s for %s', lun, backstore, self, target)
                ini_group.luns.mgmt = 'del {0}'.format(lun)

            if backstore.active:
                # TODO What about backstores that are being used by other
                # target/pgs?
                log.debug('Stopping backstore %s for Group %s Target %s', backstore, self, target)
                backstore.stop(target, self)

        # TODO We shoudn't have to do this.
        # Clear out luns for group, to be safe
        self._remove_all_luns(target)

    def _remove_all_luns(self, target):
        if self.is_active_on_target(target):
            ini_group = get_ini_group(target.driver, target.name, self.name)
            ini_group.luns.mgmt = 'clear'

    #@property
    #def attributes(self):
    #    """The following target driver attributes available: IncomingUser, OutgoingUser
    #    The following target attributes available: IncomingUser, OutgoingUser, allowed_portal
    #    """
    #    # How to require chap auth for discovery:
    #    #422 echo "192.168.1.16 AccessControl" >/sys/kernel/scst_tgt/targets/iscsi/iSNSServer
    #    #423 echo "add_attribute IncomingUser joeD 12charsecret" >/sys/kernel/scst_tgt/targets/iscsi/mgmt
    #    #424 echo "add_attribute OutgoingUser jackD 12charsecret1" >/sys/kernel/scst_tgt/targets/iscsi/mgmt
    #    return dict(
    #        #IncomingUser='test testtesttesttest',
    #        #IncomingUser1='test1 testtesttesttest1',
    #        #OutgoingUser='test testtesttesttest',
    #    )
    #
    #def _add_group_attrs(self):
    #    ini_group = get_ini_group(target.driver, target.name, self.name)
    #
    #    #log.debug('Adding %s attributes.', self)
    #    attributes = self.attributes
    #    if attributes:
    #        log.debug('Adding attribute to %s: %s', self, attributes)
    #        for k, v in self.attributes.iteritems():
    #            ini_group.mgmt = 'add_target_attribute {0.name} {1} {2}'.format(self, k, v)


class Target(object):
    name = None
    uuid = None
    # Initiator groups
    groups = None

    def __init__(self, name=None, uuid=None, groups=None):
        #if not name:
        #    pass
        self.name = name

        if not uuid:
            uuid = uuid4()
        self.uuid = uuid

        if not groups:
            groups = list()
        self.groups = groups

    def save(self, *args, **kwargs):
        raise NotImplementedError()

    def start(self):
        log.info('Starting %s', self)

        self._add_target()

        for group in self.groups:
            group.start(target=self)

        self.enabled = True
        self.driver_enabled = True

    def stop(self):
        log.info('Stopping %s', self)

        if self.added:
            for group in self.groups:
                group.stop(target=self)

            self.enabled = False
            self._del_target()
            self.driver_enabled = False

    def get_all_luns(self):
        for group in self.groups:
            for lun in group.luns:
                yield lun

    def get_all_lun_devices(self):
        devices = []
        for lun in self.get_all_luns():
            dev = lun.device
            if dev not in devices:
                devices.append(dev)
                yield dev

    def get_all_unavailable_luns(self):
        for lun in self.get_all_luns():
            if not lun.is_available():
                yield lun

    # TODO Temp hack
    @property
    def devices(self):
        for lun in self.get_all_luns():
            # TODO what about volume backstores?
            dev = lun.resource
            yield dev

    @property
    def _scstdrv(self):
        return get_driver(self.driver)

    @property
    def added(self):
        return self.name in self._scstdrv

    @added.setter
    def added(self, value):
        if value is True:
            if not self.added:
                self._add_target()
        else:
            if self.added:
                self._del_target()

    is_added = added

    @property
    def parameters(self):
        return dictattrs(
            #rel_tgt_id=randrange(1000, 3000),
            #read_only=int(False),
        )

    def _add_target(self):
        log.debug('Adding %s', self)
        if not self.is_added:
            drv = self._scstdrv

            parameters = self.parameters
            if parameters:
                log.debug('Parameters for %s: %s', self, parameters)
            drv.mgmt = 'add_target {0.name} {1}'.format(self, parameters)

            self._add_target_attrs()

    @property
    def attributes(self):
        """The following target driver attributes available: IncomingUser, OutgoingUser
        The following target attributes available: IncomingUser, OutgoingUser, allowed_portal
        """
        # How to require chap auth for discovery:
        #422 echo "192.168.1.16 AccessControl" >/sys/kernel/scst_tgt/targets/iscsi/iSNSServer
        #423 echo "add_attribute IncomingUser joeD 12charsecret" >/sys/kernel/scst_tgt/targets/iscsi/mgmt
        #424 echo "add_attribute OutgoingUser jackD 12charsecret1" >/sys/kernel/scst_tgt/targets/iscsi/mgmt
        return dict(
            #IncomingUser='test testtesttesttest',
            #IncomingUser1='test1 testtesttesttest1',
            #OutgoingUser='test testtesttesttest',
        )

    def _add_target_attrs(self):
        #log.debug('Adding %s attributes.', self)
        attributes = self.attributes
        if attributes:
            log.debug('Adding attribute to %s: %s', self, attributes)
            for k, v in self.attributes.iteritems():
                self._scstdrv.mgmt = 'add_target_attribute {0.name} {1} {2}'.format(self, k, v)

    def _del_target(self):
        log.debug('Removing Target %s', self)
        if self.is_added:
            self._del_target_attrs()
            drv = self._scstdrv
            drv.mgmt = 'del_target {0.name}'.format(self)

    def _del_target_attrs(self):
        log.debug('Removing %s attributes.', self)
        attributes = self.attributes
        if attributes:
            drv = self._scstdrv
            log.debug('Removing attribute to %s: %s', self, attributes)
            for k, v in self.attributes.iteritems():
                try:
                    drv.mgmt = 'del_target_attribute {0.name} {1} {2}'.format(self, k, v)
                except IOError:
                    pass

    @property
    def enabled(self):
        tgt = get_target(self.driver, self.name)
        if not tgt:
            return False
        return bool(tgt.enabled)

    @enabled.setter
    def enabled(self, value):
        if not self.added:
            return
        if value == self.enabled:
            return
        tgt = get_target(self.driver, self.name)
        if value:
            log.debug('Enabling Target %s', self)
        else:
            log.debug('Disabling Target %s', self)
        value = int(bool(value))
        if tgt.enabled != value:
            tgt.enabled = value

    is_enabled = enabled

    # TODO This does not belong here, it belongs in a Driver class.
    @property
    def driver_enabled(self):
        drv = get_driver(self.driver)
        if not drv:
            return False
        return bool(int(drv.enabled))

    # TODO This does not belong here, it belongs in a Driver class.
    @driver_enabled.setter
    def driver_enabled(self, value):
        drv = get_driver(self.driver)
        if not drv:
            return False

        value = int(bool(value))
        if value == self.driver_enabled:
            return

        for root, dirs, files in os.walk(drv._path_):
            break
        drv_subdir_count = len(dirs)

        # TODO Driver class that handles it's own parameters and shit
        if value:
            log.info('Enabling iSNS server with access control.')
            drv.iSNSServer = 'localhost AccessControl'

        if not value and drv_subdir_count:
            log.info('Not disabling driver %s as it is currently in use.', self.driver)
            return
        elif not value:
            log.info('Disabling driver %s as it is no longer in use.', self.driver)
        else:
            log.info('Enabling driver %s.', self.driver)

        drv.enabled = value

    def __unicode__(self):
        return self.__repr__()

    @classmethod
    def search_hard(cls, **kwargs):
        if not kwargs:
            return
        for subcls in cls.__subclasses__():
            try:
                qs = subcls.objects.get(**kwargs)
                return qs
            except subcls.DoesNotExist:
                pass



class iSCSITarget(Target):
    driver = 'iscsi'
    #portal_port = m.IntField()

    def generate_wwn(self, serial=None):
        self.name = generate_wwn('iqn')
        return True

    def save(self, *args, **kwargs):
        """Overrides save to ensure name is a valid iqn; generates one if None"""
        if self.name:
            if not is_valid_wwn('iqn', self.name):
                raise ValueError("The name '%s' is not a valid iqn" % self.name)
        else:
            self.generate_wwn()
        super(iSCSITarget, self).save(*args, **kwargs)


class SRPTarget(Target):
    #driver = 'srpt'
    driver = 'iscsi'

    @property
    def _scstdrv(self):
        #if not hasattr(self, '_scstdrv_cache') or self._scstdrv_cache_verify != self.driver:
        #    self._scstdrv_cache = get_driver(self.driver)
        #    self._scstdrv_cache_verify = self.driver
        #return self._scstdrv_cache
        return get_driver(self.driver)
