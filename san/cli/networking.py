

from .base import ConfigNode
from ..networking.config import Nic, list_ifaces
import re


class Networking(ConfigNode):
    def __init__(self, parent):
        ConfigNode.__init__(self, parent)

        for iface in list_ifaces():
            if not re.match(r':|^(lo|virbr)', iface):
                Interface(self, iface)


class Interface(ConfigNode):
    _autosave = False

    def __init__(self, parent, name):
        self.obj = Nic(name)
        ConfigNode.__init__(self, parent, name=name)

        self.define_config_group_param('interface', 'proto', 'string', 'dhcp|static')

        self.define_config_group_param('interface', 'address', 'string', 'IP Address/Mask')
        #self.define_config_group_param('interface', 'ip', 'string', 'IP Address')
        #self.define_config_group_param('interface', 'netmask', 'string', 'Network mask')
        #self.define_config_group_param('interface', 'cidr', 'string', 'CIDR mask')

        self.define_config_group_param('interface', 'gateway', 'string', 'Gateway')
        self.define_config_group_param('interface', 'nameservers', 'string', 'DNS nameservers,; space separated')
        self.define_config_group_param('interface', 'search', 'string', 'DNS search domains; space separated')

    def summary(self):
        if self.obj.config:
            txt = ''
            for k in ['proto', 'address']:
                v = getattr(self.obj.config, k, None)
                if v in [None, 'None', 'None/None']:
                    continue
                if v:
                    txt += '%s=%s; ' % (k, v)
            if txt:
                txt = txt[:-2]
            return (txt, True)
        else:
            return ('Unconfigured', False)

    def ui_getgroup_interface(self, key):
        '''
        This is the backend method for getting keys.
        @param key: The key to get the value of.
        @type key: str
        @return: The key's value
        @rtype: arbitrary
        '''
        return getattr(self.obj.config, key)

    def ui_setgroup_interface(self, key, value):
        '''
        This is the backend method for setting keys.
        @param key: The key to set the value of.
        @type key: str
        @param value: The key's value
        @type value: arbitrary
        '''
        setattr(self.obj.config, key, value)
        if self._autosave:
            self.obj.config.save()

    def ui_command_save(self):
        return self.obj.config.save()

    def ui_command_apply(self):
        return self.obj.config.save(apply=True)

    def ui_command_down(self, reset=False):
        return self.obj.ifdown(reset=reset)

    def ui_command_up(self):
        return self.obj.ifup()
