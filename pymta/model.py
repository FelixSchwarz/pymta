# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals


__all__ = ['Message', 'Peer']


class Message(object):
    def __init__(self, peer, smtp_helo=None, smtp_from=None, smtp_to=None,
                 msg_data=None, username=None):
        self.peer = peer
        self.smtp_helo = smtp_helo
        self.smtp_from = smtp_from
        if smtp_to is None:
            smtp_to = []
        elif not isinstance(smtp_to, (list, tuple)):
            smtp_to = [smtp_to]
        self.smtp_to = smtp_to
        self.msg_data = msg_data
        self.username = username
        self.unvalidated_input = {}



class Peer(object):
    def __init__(self, remote_ip, remote_port):
        self.remote_ip = remote_ip
        self.remote_port = remote_port

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, self.remote_ip,
                               self.remote_port)


