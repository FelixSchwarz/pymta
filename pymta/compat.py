# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT
"""This module provides a unified view on certain symbols that are not present
for all versions of Python."""

import sys
import base64

__all__ = []


if sys.version_info < (3, 0):
    basestring = basestring
    binary = bytes = str
    unicode = unicode
    range = xrange
    b64encode = lambda x: str(x).encode('base64')
    b64decode = lambda x: str(x).decode('base64')
    from Queue import Queue, Full, Empty
else:
    basestring = str
    binary = bytes = b = bytes
    unicode = str
    range = range
    b64encode = lambda x: base64.b64encode(b(x)).decode('ascii')
    b64decode = lambda x: base64.b64decode(b(x)).decode('ascii')
    from queue import Queue, Full, Empty


def b(x, encoding='iso-8859-1'):
    if isinstance(x, unicode):
        return x.encode(encoding)
    return bytes(x)
