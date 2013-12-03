""" System. """

from .base import ConfigNode
import os
import sh


class System(ConfigNode):

    """ System Node. """

    def __init__(self, parent):
        ConfigNode.__init__(self, parent)

        self.define_config_group_param('system', 'hostname', 'string', 'Hostname (short)')
        self.define_config_group_param('system', 'domain', 'string', 'Domain name')
        self.define_config_group_param('system', 'gateway', 'string', 'Gateway')
        self.define_config_group_param('system', 'nameservers', 'string', 'DNS resolvers')

        #Logs(self)
        #Alerts(self)
        #if conf.config.get('debug') is True:
        #    Developer(self)

    def ui_getgroup_system(self, config):
        '''
        This is the backend method for getting configs.
        @param config: The config to get the value of.
        @type config: str
        @return: The config's value
        @rtype: arbitrary
        '''
        #return conf.config.get(config)
        return None

    def ui_setgroup_system(self, config, value):
        '''
        This is the backend method for setting configs.
        @param config: The config to set the value of.
        @type config: str
        @param value: The config's value
        @type value: arbitrary
        '''
        #conf.config[config] = value
        #return conf.config.save()
        return None

    def ui_command_uptime(self):
        """ uptime - Tell how long the system has been running. """
        os.system("uptime")

    def ui_command_hostname(self):
        """ Displays the system hostname. """
        print sh.hostname('-f')

    def ui_command_uname(self):
        """ Displays the system uname information.. """
        print sh.uname('-a')

    def ui_command_lsmod(self):
        """ lsmod - program to show the status of modules in the Linux Kernel. """
        print sh.lsmod()

    def ui_command_lspci(self):
        """ lspci - list all PCI devices. """
        print sh.lspci()

    def ui_command_lsusb(self):
        """ lsusb - list USB devices. """
        print sh.lsusb()

    def ui_command_lscpu(self):
        """ lscpu - CPU architecture information helper. """
        print sh.lscpu()

    def ui_command_lshw(self):
        """ lshw - List all hardware known by HAL. """
        print sh.lshw()

    def ui_command_uptime(self):
        """ uptime - Tell how long the system has been running.. """
        print sh.uptime()

    def ui_command_shutdown(self):
        """ shutdown - Shutdown system. """
        #status.tasks.shutdown.delay()
        print sh.shutdown('-h', 'now')

    def ui_command_reboot(self):
        """ reboot - reboot system. """
        #status.tasks.reboot.delay()
        print sh.reboot()

    def ui_command_check_services(self):
        print sh.egrep(sh.initctl('list'), 'solarsan|targetcli|mongo')
