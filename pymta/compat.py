# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT
"""This module provides a unified view on certain symbols that are not present 
for all versions of Python."""

import sys
import base64

__all__ = ['set']


if sys.version_info < (3, 0):  
    basestring = basestring
    binary = bytes = str
    unicode = unicode
    range = xrange
    b64encode = lambda x: str(x).encode('base64')
    b64decode = lambda x: str(x).decode('base64')
    func_code = lambda func: func.im_func.func_code
    dict_items = lambda dct: dct.items()
    dict_keys = lambda dct: dct.keys()
    dict_values = lambda dct: dct.values()
    dict_iteritems = lambda dct: dct.iteritems()
    dict_iterkeys = lambda dct: dct.iterkeys()
    dict_itervalues = lambda dct: dct.itervalues()
    from Queue import Queue, Full, Empty
else:
    basestring = str
    binary = bytes = b = bytes
    unicode = str
    range = range
    b64encode = lambda x: base64.b64encode(b(x)).decode('ascii')
    b64decode = lambda x: base64.b64decode(b(x)).decode('ascii')
    func_code = lambda func: func.__func__.__code__
    dict_items = lambda dct: list(dct.items())
    dict_keys = lambda dct: list(dct.keys())
    dict_values = lambda dct: list(dct.values())
    dict_iteritems = lambda dct: dct.items()
    dict_iterkeys = lambda dct: dct.keys()
    dict_itervalues = lambda dct: dct.values()
    from queue import Queue, Full, Empty

if sys.version_info < (2, 4):
    from sets import Set as set
else:
    set = set


def b(x, encoding='iso-8859-1'):
    if isinstance(x, unicode):
        return x.encode(encoding)
    return bytes(x)
