#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""This module contains an equivalent of Python's DebuggingServer which just
prints all received messages to STDOUT and discards them afterwards."""
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

import os
import sys

from pymta import PythonMTA, IMessageDeliverer


class STDOUTDeliverer(IMessageDeliverer):
    def new_message_accepted(self, msg):
        print '---------- MESSAGE FOLLOWS ----------'
        print msg.msg_data
        print '------------ END MESSAGE ------------'


def list_get(data, index, default=None):
    if len(data) <= index:
        return default
    return data[index]


def print_usage():
    cmd_name = list_get(sys.argv, 0, default=os.path.basename(__file__))
    print 'Usage: %s [host] [port]' % cmd_name


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)
    
    host = list_get(sys.argv, 1, default='localhost')
    port = int(list_get(sys.argv, 2, default=8025))
    
    server = PythonMTA(host, port, STDOUTDeliverer)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

