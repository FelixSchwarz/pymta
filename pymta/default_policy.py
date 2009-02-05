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

__all__ = ['DefaultMTAPolicy']


class DefaultMTAPolicy(object):
    """This is the default policy which just accepts everything."""
    
    def accept_new_connection(self, peer):
        """This method is called directly after a new connection is received. 
        The  policy can decide if the given peer is allowed to connect to the 
        SMTP server. If it declines, the connection will be closed 
        immediately."""
        return True
    
    def accept_helo(self, helo_string, message):
        """Decides if the HELO command with the given helo_name should be 
        accepted."""
        return True
    
    def accept_ehlo(self, ehlo_string, message):
        """Decides if the EHLO command with the given helo_name should be 
        accepted."""
        return True
    
    def accept_auth_plain(self, username, password, message):
        """Decides if AUTH plain should be allowed for this client. Please note 
        that username and password are not verified before, the authenticator 
        will check them after the policy allowed this command.
        
        The method must not return a response by itself in case it accepts the
        AUTH PLAIN command!"""
        return True
    
    def accept_from(self, sender, message):
        "Decides if the sender of this message (MAIL FROM) should be accepted."
        return True
    
    def accept_rcpt_to(self, new_recipient, message):
        """Decides if recipient of this message (RCPT TO) should be accepted. 
        If a message should be delivered to multiple recipients this method is 
        called for every recipient."""
        return True
    
    def accept_data(self, message):
        """Decides if we allow the client to start a message transfer (the 
        actual message contents will be transferred after this method allowed 
        it)."""
        return True
    
    def accept_msgdata(self, msgdata, message):
        """This method actually matches no real SMTP command. It is called 
        after a message was transferred completely and this is the last check 
        before the SMTP server takes the responsibility of transferring it to 
        the recipients."""
        return True




