# -*- coding: UTF-8 -*-


__all__ = ['Message', 'Peer']


class Message(object):
    def __init__(self, peer, smtp_from=None, smtp_to=None, msg_data=None):
        self.peer = peer
        self.smtp_from = smtp_from
        self.smtp_to = smtp_to
        self.msg_data = msg_data


class Peer(object):
    def __init__(self, remote_ip, remote_port):
        self.remote_ip = remote_ip
        self.remote_port = remote_port
    
    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, self.remote_ip, 
                               self.remote_port)


