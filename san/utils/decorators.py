
"""
Decorators
"""

from decorator import decorator, FunctionMaker
import logging
#from django.core.cache import cache


@decorator
def trace(f, *args, **kw):
    print "calling %s with args %s, %s" % (f.func_name, args, kw)
    return f(*args, **kw)


'''
@decorator
def args_list(f, *args, **kwargs):
    if not isinstance(args, list):
        if isinstance(args, basestring):
            args = [args]
        elif isinstance(args, tuple):
            args = list(args)
    return f(*args, **kwargs)
'''


def decorator_apply(dec, func):
    """
    Decorate a function by preserving the signature even if dec
    is not a signature-preserving decorator.
    """
    return FunctionMaker.create(
        func, 'return decorated(%(signature)s)',
        dict(decorated=dec(func)), __wrapped__=func)


class conditional_decorator(object):
    """ Applies decorator dec if conditional condition is met """
    def __init__(self, condition, dec, *args, **kwargs):
        self.decorator = dec
        self.decorator_args = (args, kwargs)
        self.condition = condition

    def __call__(self, func):
        if not self.condition:
            # Return the function unchanged, not decorated.
            return func
        return self.decorator(func,
                              *self.decorator_args[0],
                              **self.decorator_args[1])


def statelazyproperty(func):
    """A decorator for state-based lazy evaluation of properties"""
    cache = {}

    def _get(self):
        state = self.__getstate__()
        try:
            v = cache[state]
            logging.debug("Cache hit %s", state)
            return v
        except KeyError:
            logging.debug("Cache miss %s", state)
            cache[state] = value = func(self)
            return value
    return property(_get)


'''
import sys


def propget(func):
    locals = sys._getframe(1).f_locals
    name = func.__name__
    prop = locals.get(name)
    if not isinstance(prop, property):
        prop = property(func, doc=func.__doc__)
    else:
        doc = prop.__doc__ or func.__doc__
        prop = property(func, prop.fset, prop.fdel, doc)
    return prop


def propset(func):
    locals = sys._getframe(1).f_locals
    name = func.__name__
    prop = locals.get(name)
    if not isinstance(prop, property):
        prop = property(None, func, doc=func.__doc__)
    else:
        doc = prop.__doc__ or func.__doc__
        prop = property(prop.fget, func, prop.fdel, doc)
    return prop


def propdel(func):
    locals = sys._getframe(1).f_locals
    name = func.__name__
    prop = locals.get(name)
    if not isinstance(prop, property):
        prop = property(None, None, func, doc=func.__doc__)
    else:
        prop = property(prop.fget, prop.fset, func, prop.__doc__)
    return prop
'''

""" Better example than above using no decorators:
class Example(object):
    @apply
    def myattr():
        doc = '''This is the doc string.'''

        def fget(self):
            return self._half * 2

        def fset(self, value):
            self._half = value / 2

        def fdel(self):
            del self._half

        return property(**locals())
"""
