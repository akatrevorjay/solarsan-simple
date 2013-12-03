#!/usr/bin/env python

import configshell
from .base import ConfigNode
from .system import System
from .storage import Storage
from .networking import Networking


class MySystemRoot(ConfigNode):
    def __init__(self, shell):
        ConfigNode.__init__(self, shell=shell, name='/')

        System(self)
        Storage(self)


def main():
    shell = configshell.shell.ConfigShell('~/.myshell')
    root_node = MySystemRoot(shell)
    shell.run_interactive()

__main__ = main

if __name__ == "__main__":
    __main__()
