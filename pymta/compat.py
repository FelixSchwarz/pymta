# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT
"""This module provides a unified view on certain symbols that are not present
for all versions of Python."""

from __future__ import print_function, unicode_literals

try:
    import queue
except ImportError:
    # Python 2
    import Queue as queue
import sys
import base64

__all__ = ['queue']


if sys.version_info < (3, 0):
    basestring = basestring
    binary = bytes = str
    unicode = unicode
    range = xrange
    b64encode = lambda x: str(x).encode('base64').strip()
    b64decode = lambda x: str(x).decode('base64')
else:
    basestring = str
    binary = bytes = b = bytes
    unicode = str
    range = range
    b64encode = lambda x: base64.b64encode(b(x)).decode('ascii').strip()
    b64decode = lambda x: base64.b64decode(b(x)).decode('ascii')


def b(x, encoding='iso-8859-1'):
    if isinstance(x, unicode):
        return x.encode(encoding)
    return bytes(x)
