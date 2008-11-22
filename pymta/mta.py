# -*- coding: UTF-8 -*-

import socket

from pymta.smtpd import SMTPServer
from pymta.command_parser import SMTPCommandParser

__all__ = ['PythonMTA']


class PythonMTA(SMTPServer):
    version='0.1'

    def __init__(self, localaddr, remoteaddr, policy_class):
        SMTPServer.__init__(self, localaddr, remoteaddr)
        self._policy_class = policy_class
        self._primary_hostname = socket.getfqdn()
    
    
    def handle_accept(self):
        connection, remote_ip_and_port = self.accept()
        remote_ip_string, port = remote_ip_and_port
        policy = self._policy_class()
        SMTPCommandParser(self, connection, remote_ip_and_port, policy)

    
    def primary_hostname(self):
        return self._primary_hostname
    primary_hostname = property(primary_hostname)
    
    
    def new_message_received(self, msg):
        """Called from the SMTPSession whenever a new message was accepted."""
        print msg
        raise NotImplementedError
    
    # Do something with the gathered message
    # TODO: Rewrite!
    def process_message(self, peer, mailfrom, rcpttos, data):
        inheaders = True
        lines = data.split('\n')
        print '---------- MESSAGE FOLLOWS ----------'
        for line in lines:
            # headers first
            if inheaders and not line:
                print 'X-Peer:', peer[0]
                inheaders = False
            print line
        print '------------ END MESSAGE ------------'


