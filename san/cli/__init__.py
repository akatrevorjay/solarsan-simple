#!/usr/bin/env python

import configshell
from .base import ConfigNode
from .system import System
from .storage import Pools
from .networking import Networking


class CLIRoot(ConfigNode):
    def __init__(self, shell):
        ConfigNode.__init__(self, shell=shell, name='/')

        System(self)
        Pools(self)
        Networking(self)


def main():
    shell = configshell.shell.ConfigShell('~/.myshell')
    root_node = CLIRoot(shell)
    shell.run_interactive()


if __name__ == "__main__":
    __main__()
