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
    """Create a new MTA which listens for new connections afterwards.
    local_address is a string containing either the IP oder the DNS 
    hostname of the interface on which PythonMTA should listen. policy_class
    and authenticator_class are callables which can be used to add custom 
    behavior.
    Every new connection gets their own instance of policy_class and     
    authenticator_class so these classes don't have to be thread-safe. If 
    you ommit the policy, all syntactically valid SMTP commands are 
    accepted. If there is no authenticator specified, authentication will 
    not be available."""

    def __init__(self, local_address, bind_port, policy_class=None, 
                 authenticator_class=None):
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
    
    def _get_authenticator(self):
        authenticator = None
        if self._authenticator_class != None:
            authenticator = self._authenticator_class()
        return authenticator
    
    def _get_policy(self):
        policy = None
        if self._policy_class != None:
            policy = self._policy_class()
        return policy
    
    def handle_accept(self):
        connection, remote_ip_and_port = self.accept()
        remote_ip_string, port = remote_ip_and_port
        policy = self._get_policy()
        authenticator = self._get_authenticator()
        SMTPCommandParser(self, connection, remote_ip_string, port, policy, 
                          authenticator)
    
    def primary_hostname(self):
        return self._primary_hostname
    primary_hostname = property(primary_hostname)
    
    def new_message_received(self, msg):
        """This method is called when a new message was submitted successfully.
        The MTA is then in charge of delivering the message to the specified 
        recipients.
        Please note that you can not reject the message anymore at this stage (if
        there are problems you must generate a non-delivery report aka bounce). 
        Because there can be multiple active connections at the same time it is 
        a good idea to make the method thread-safe and protect queue access.
        
        Attention: This method will probably be removed when we switch to a 
        process-based interface (scheduled for 0.3).
        """
        print msg
        raise NotImplementedError


