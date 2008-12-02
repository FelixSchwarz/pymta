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

from Queue import Queue
import smtplib
from unittest import TestCase

from pymta import DefaultMTAPolicy, MTAThread, PythonMTA


class DebuggingMTA(PythonMTA):
    def __init__(self, *args, **kwargs):
        PythonMTA.__init__(self, *args, **kwargs)
        self.queue = Queue()

    def new_message_received(self, msg):
        """Called from the SMTPSession whenever a new message was accepted."""
        self.queue.put(msg)


class BasicSMTPTest(TestCase):
    """This test uses the SMTP protocol to check the whole server."""

    def setUp(self):
        hostname = 'localhost'
        smtpd_listen_port = 8025
        
        self.mta = DebuggingMTA(hostname, smtpd_listen_port, policy_class=DefaultMTAPolicy)
        self.mta_thread = MTAThread(self.mta)
        self.mta_thread.start()
        
        self.connection = smtplib.SMTP()
        self.connection.set_debuglevel(0)
        self.connection.connect(hostname, smtpd_listen_port)
    
    def tearDown(self):
        try:
            self.connection.quit()
        except smtplib.SMTPServerDisconnected:
            pass
        self.mta_thread.stop()
    
    def test_helo(self):
        code, replytext = self.connection.helo('foo')
        self.assertEqual(250, code)
    
    def test_send_simple_email(self):
        code, replytext = self.connection.helo('foo')
        self.assertEqual(250, code)
        code, replytext = self.connection.mail('from@example.com')
        self.assertEqual(250, code)
        code, replytext = self.connection.rcpt('to@example.com')
        self.assertEqual(250, code)
        rfc822_msg = 'Subject: Test\n\nJust testing...'
        code, replytext = self.connection.data(rfc822_msg)
        self.assertEqual(250, code)
        self.connection.quit()
        
        queue = self.mta.queue
        self.assertEqual(1, queue.qsize())
        msg = queue.get()
        self.assertEqual('foo', msg.smtp_helo)
        self.assertEqual('<from@example.com>', msg.smtp_from)
        self.assertEqual('<to@example.com>', msg.smtp_to)
        self.assertEqual(rfc822_msg, msg.msg_data)
    
    def test_send_email_via_smtplib(self):
        """Check that we can send a simple email via smtplib.sendmail without
        using the low-level api."""
        rfc822_msg = 'Subject: Test\n\nJust testing...'
        self.connection.sendmail('from@example.com', 'to@example.com', rfc822_msg)
        self.connection.quit()
        
        queue = self.mta.queue
        self.assertEqual(1, queue.qsize())
        msg = queue.get()
        self.assertEqual('<from@example.com>', msg.smtp_from)
        self.assertEqual('<to@example.com>', msg.smtp_to)
        self.assertEqual(rfc822_msg, msg.msg_data)

