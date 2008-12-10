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
        return True
    
    def accept_helo(self, helo_string, message):
        return True
    
    def accept_ehlo(self, helo_string, message):
        return True
    
    def accept_auth_plain(self, username, password, message):
        """The username and password are not verified by the time this method
        is called, they were just supplied by the user.
        
        The method must not return a response by itself in case it accepts the
        AUTH PLAIN command!"""
        return True
    
    def accept_from(self, sender, message):
        return True
    
    def accept_rcpt_to(self, new_recipient, message):
        return True
    
    def accept_data(self, message):
        return True
    
    def accept_msgdata(self, msgdata, message):
        return True




