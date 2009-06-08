# -*- coding: UTF-8 -*-
# 
# The MIT License
# 
# Copyright (c) 2008-2009 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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
import socket

from pymta.api import IMTAPolicy
from pymta.test_util import DebuggingMTA, SMTPTestCase

from tests.util import DummyAuthenticator


rfc822_msg = 'Subject: Test\n\nJust testing...'



class BasicSMTPTest(SMTPTestCase):
    """This test uses the SMTP protocol to check the whole server."""
    
    def build_mta(self, hostname, listen_port, deliverer, policy_class=None):
        return DebuggingMTA(hostname, listen_port, deliverer,
                            authenticator_class=DummyAuthenticator,
                            policy_class=policy_class)
    
    def init_mta(self, policy_class=IMTAPolicy):
        super(BasicSMTPTest, self).init_mta(policy_class)
        self.connection = smtplib.SMTP()
        self.connection.set_debuglevel(0)
        self.connection.connect(self.hostname, self.listen_port)
    
    def stop_mta(self):
        if getattr(self, 'connection', None) is not None:
            try:
                self.connection.quit()
            except smtplib.SMTPServerDisconnected:
                pass
        super(BasicSMTPTest, self).stop_mta()
    
    def test_helo(self):
        code, replytext = self.connection.helo('foo')
        self.assertEqual(250, code)
    
    def _check_received_mail(self, expected_recipients, expected_helo=None):
        queue = self.get_received_messages()
        self.assertEqual(1, queue.qsize())
        msg = queue.get()
        if expected_helo != None:
            self.assertEqual('foo', msg.smtp_helo)
        self.assertEqual('from@example.com', msg.smtp_from)
        self.assertEqual(expected_recipients, msg.smtp_to)
        self.assertEqual(rfc822_msg, msg.msg_data)
        return msg
    
    def test_send_simple_email(self):
        code, replytext = self.connection.helo('foo')
        self.assertEqual(250, code)
        code, replytext = self.connection.mail('from@example.com')
        self.assertEqual(250, code)
        code, replytext = self.connection.rcpt('to@example.com')
        self.assertEqual(250, code)
        code, replytext = self.connection.data(rfc822_msg)
        self.assertEqual(250, code)
        self.connection.quit()
        self._check_received_mail(['to@example.com'], expected_helo='foo')
    
    def test_send_email_via_smtplib(self):
        """Check that we can send a simple email via smtplib.sendmail without
        using the low-level api."""
        recipient = 'to@example.com'
        self.connection.sendmail('from@example.com', recipient, rfc822_msg)
        self.connection.quit()
        self._check_received_mail([recipient])
    
    def test_multiple_recipients(self):
        """Check that we can send an email to multiple recipients at once."""
        recipients = ['foo@example.com', 'bar@example.com']
        self.connection.sendmail('from@example.com', recipients, rfc822_msg)
        self.connection.quit()
        self._check_received_mail(recipients)
    
    def test_send_email_with_authentication(self):
        """Check that we can send an email with prior authentication."""
        recipient = 'to@example.com'
        self.connection.login('admin', 'admin')
        self.connection.sendmail('from@example.com', recipient, rfc822_msg)
        self.connection.quit()
        msg = self._check_received_mail([recipient])
        self.assertEqual('admin', msg.username)
    
    def test_send_multiple_emails_in_one_connection(self):
        """Check that we can send multiple emails in the same connection (and
        the second email needs to have the same peer information/helo string 
        though this information is only sent once)."""
        self.connection.login('admin', 'admin')
        self.connection.sendmail('x@example.com', 'foo@example.com', rfc822_msg)
        self.connection.sendmail('x@example.com', 'bar@example.com', rfc822_msg)
        
        queue = self.get_received_messages()
        self.assertEqual(2, queue.qsize())
        first_msg = queue.get()
        self.assertNotEqual(None, first_msg.smtp_helo)
        self.assertEqual('x@example.com', first_msg.smtp_from)
        
        second_msg = queue.get()
        self.assertEqual(first_msg.smtp_helo, second_msg.smtp_helo)
        self.assertEqual(first_msg.username, second_msg.username)
    
    def test_transparency_support_enabled(self):
        """Check that there is transparency support for lines starting with a 
        dot in the message body (RFC 821, section 4.5.2)."""
        msg = rfc822_msg + '\n.Bar\nFoo'
        self.connection.sendmail('from@example.com', 'foo@example.com', msg)
        self.connection.quit()
        
        queue = self.get_received_messages()
        self.assertEqual(1, queue.qsize())
        received_msg = queue.get()
        self.assertEqual(msg, received_msg.msg_data)
    
    def test_big_messages_are_rejected(self):
        """Check that messages which exceed the configured maximum message size
        are rejected. This tests all the code setting the maximum allowed input
        size in the transport layer."""
        class RestrictedSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        
        self.stop_mta()
        self.init_mta(RestrictedSizePolicy)
        
        big_data_chunk = ('x'*70 + '\n') * 1500
        msg = rfc822_msg + big_data_chunk
        try:
            self.connection.sendmail('from@example.com', 'foo@example.com', msg)
            self.fail('SMTPDataError not thrown')
        except (smtplib.SMTPDataError, smtplib.SMTPSenderRefused), e:
            # Depending on when the protocol used (ESMTP with SIZE extension or
            # plain old SMTP) and when the server checks the message size (after
            # MAIL FROM or only when the message was transmitted completely), 
            # the error message may differ.
            # Unfortunately Python's smtplib raises SMTPSenderRefused even if 
            # the message was rejected due to size restrictions after issuing 
            # MAIL FROM with size verb
            self.assertEqual(552, e.smtp_code)
            self.assertEqual('message exceeds fixed maximum message size', 
                             e.smtp_error)
    
    def test_workerprocess_detects_closed_connections(self):
        """Check that the WorkerProcess gracefully handles connections which are
        closed without QUIT. This can happen due to network problems or 
        unfriendly clients."""
        self.connection.helo('foo')
        self.connection.close()
        
        # In 0.3 the WorkerProcess would hang and start to eat up the whole CPU
        # so we need to set a sensible timeout so that this test will fail with
        # an appropriate exception.
        # On a normal system we should be able to reconnect after a dropped
        # connection within two seconds under all circumstances.
        old_default = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2)
        try:
            self.connection.connect(self.hostname, self.listen_port)
        finally:
            socket.setdefaulttimeout(old_default)



