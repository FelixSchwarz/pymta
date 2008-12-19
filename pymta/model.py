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


__all__ = ['Message', 'Peer']


class Message(object):
    def __init__(self, peer, smtp_helo=None, smtp_from=None, smtp_to=None, 
                 msg_data=None, username=None):
        self.peer = peer
        self.smtp_helo = smtp_helo
        self.smtp_from = smtp_from
        if smtp_to == None:
            smtp_to = []
        elif not isinstance(smtp_to, (list, tuple)):
            smtp_to = [smtp_to]
        self.smtp_to = smtp_to
        self.msg_data = msg_data
        self.username = username



class Peer(object):
    def __init__(self, remote_ip, remote_port):
        self.remote_ip = remote_ip
        self.remote_port = remote_port
    
    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, self.remote_ip, 
                               self.remote_port)


