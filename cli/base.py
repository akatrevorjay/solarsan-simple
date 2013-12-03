
import configshell


class ConfigNode(configshell.node.ConfigNode):
    def __init__(self, *args, **kwargs):
        # Figure out name
        name = kwargs.pop('name', None)
        if not name:
            name = getattr(self, 'name', None)
        if not name:
            name = self.__class__.__name__.lower()

        # Create args list
        cargs = [name]
        cargs.extend(args)

        configshell.node.ConfigNode.__init__(self, *cargs, **kwargs)
