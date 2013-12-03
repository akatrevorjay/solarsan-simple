
class ReprMixIn(object):
    def __repr__(self):
        append = ''

        repr_vars = getattr(self, '_repr_vars', ['name'])
        for k in repr_vars:
            v = getattr(self, k, None)
            if v is not None:
                try:
                    append += " %s='%s'" % (k, v)
                except:
                    pass

        return '<%s%s>' % (self.__class__.__name__, append)
