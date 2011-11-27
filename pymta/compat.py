# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2009 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
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
    b = lambda x, encoding='iso-8859-1': x.encode(encoding) if isinstance(x, unicode) else str(x)
    b64encode = lambda x: base64.b64encode(x)
    b64decode = lambda x: base64.b64decode(x)
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
    b = lambda x, encoding='iso-8859-1': x.encode(encoding) if isinstance(x, unicode) else bytes(x)
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
