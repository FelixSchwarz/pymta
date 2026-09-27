# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import socket

from pymta.command_parser import WorkerProcess
from pymta.test_util import BlackholeDeliverer


class BrokenConnection(object):
    """Simulates a TCP connection which was closed by the client."""
    def __init__(self):
        self.nr_writes = 0
        self.closed = False

    def sendall(self, data):
        self.nr_writes += 1
        raise socket.error('Broken pipe')

    def close(self):
        self.closed = True


def test_ignores_further_writes_after_write_error():
    """Check that the WorkerProcess gracefully handles connections which are
    closed without QUIT - remaining output is suppressed. This can happen
    due to network problems or unfriendly clients."""
    worker = WorkerProcess(None, None, deliverer_class=BlackholeDeliverer)
    connection = BrokenConnection()
    # sends the SMTP greeting
    worker._setup_new_connection((connection, ('127.0.0.1', 12345)))
    assert connection.nr_writes == 1
    assert connection.closed
    assert not worker.is_connected()

    worker.write('250 OK\r\n')
    assert connection.nr_writes == 1
