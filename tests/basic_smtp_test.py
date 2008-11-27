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

import smtplib
from unittest import TestCase

from pymta import DefaultMTAPolicy, MTAThread, PythonMTA


class DebuggingMTA(PythonMTA):
    def new_message_received(self, msg):
        """Called from the SMTPSession whenever a new message was accepted."""
        print msg


class BasicSMTPTest(TestCase):
    """This test uses the SMTP protocol to check the whole server."""

    def setUp(self):
        hostname = 'localhost'
        smtpd_listen_port = 8025
        
        self.mta = DebuggingMTA(hostname, smtpd_listen_port, policy_class=DefaultMTAPolicy)
        self.mtathread = MTAThread(self.mta)
        self.mtathread.start()
        
        self.connection = smtplib.SMTP()
        self.connection.set_debuglevel(0)
        self.connection.connect(hostname, smtpd_listen_port)
    
    def tearDown(self):
        self.connection.quit()
        self.mtathread.stop()
    
    def test_helo(self):
        code, replytext = self.connection.helo('foo')
        self.assertEqual(250, code)
        
    def test_send_simple_email(self):
        code, replytext = self.connection.helo('foo')
        self.assertEqual(250, code)
        code, replytext = self.connection.mail('from@example.com')
        self.assertEqual(250, code)
        code, replytext = self.connection.rcpt('from@example.com')
        self.assertEqual(250, code)
        rfc822_msg = 'Subject: Test\r\n\r\nJust testing...\r\n'
        code, replytext = self.connection.data(rfc822_msg)
        self.assertEqual(250, code)
        
        # Retrieve message
        # TODO: graceful exit of server when all threads are gone!


