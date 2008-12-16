# -*- coding: UTF-8 -*-
# 
# The MIT License
# 
# Copyright (c) 2008 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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

import asyncore
import socket

from pymta.command_parser import SMTPCommandParser

__all__ = ['PythonMTA']


class PythonMTA(asyncore.dispatcher):
    version='0.1'

    def __init__(self, local_address, bind_port, policy_class=None, authenticator_class=None):
        asyncore.dispatcher.__init__(self)
        self._policy_class = policy_class
        self._authenticator_class = authenticator_class
        
        self._primary_hostname = socket.getfqdn()
        
        # --------------------------
        # Copied from Python's smtpd
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        # try to re-use a server port if possible
        self.set_reuse_addr()
        self.bind((local_address, bind_port))
        self.listen(5)
    
    def handle_accept(self):
        connection, remote_ip_and_port = self.accept()
        remote_ip_string, port = remote_ip_and_port
        policy = None
        if self._policy_class != None:
            policy = self._policy_class()
        authenticator = None
        if self._authenticator_class != None:
            authenticator = self._authenticator_class()
        SMTPCommandParser(self, connection, remote_ip_and_port, policy, 
                          authenticator)
    
    def primary_hostname(self):
        return self._primary_hostname
    primary_hostname = property(primary_hostname)
    
    def new_message_received(self, msg):
        """Called from the SMTPSession whenever a new message was accepted."""
        print msg
        raise NotImplementedError


