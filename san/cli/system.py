
from .base import ConfigNode
import os


class System(ConfigNode):
    def __init__(self, parent):
        ConfigNode.__init__(self, parent)

    def ui_command_uptime(self):
        """ uptime - Tell how long the system has been running. """
        os.system("uptime")
