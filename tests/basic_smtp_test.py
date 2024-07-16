# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import socket
import smtplib
import time

import pytest

from pymta.api import IMTAPolicy
from pymta.compat import b, b64encode
from pymta.test_util import DebuggingMTA, DummyAuthenticator, SMTPTestCase


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
        assert code == 250

    def _check_received_mail(self, expected_recipients, expected_helo=None):
        queue = self.get_received_messages()
        assert queue.qsize() == 1
        msg = queue.get()
        if expected_helo is not None:
            assert msg.smtp_helo == 'foo'
        assert msg.smtp_from == 'from@example.com'
        assert msg.smtp_to == expected_recipients
        assert msg.msg_data == rfc822_msg
        return msg

    def test_send_simple_email(self):
        code, replytext = self.connection.helo('foo')
        assert code == 250
        code, replytext = self.connection.mail('from@example.com')
        assert code == 250
        code, replytext = self.connection.rcpt('to@example.com')
        assert code == 250
        code, replytext = self.connection.data(rfc822_msg)
        assert code == 250
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
        assert msg.username == 'admin'

    def test_send_email_with_auth_login(self):
        """Check that we can send an email with using AUTH LOGIN."""
        self.connection.ehlo()
        login_response = self.connection.docmd('AUTH', 'LOGIN %s' % b64encode('foo'))
        assert login_response == (334, b(b64encode('Password:')))
        password_response = self.connection.docmd(b64encode('foo'))
        assert password_response == (235, b('Authentication successful'))

        recipient = 'to@example.com'
        self.connection.sendmail('from@example.com', recipient, rfc822_msg)
        self.connection.quit()
        msg = self._check_received_mail([recipient])
        assert msg.username == 'foo'

    def test_send_multiple_emails_in_one_connection(self):
        """Check that we can send multiple emails in the same connection (and
        the second email needs to have the same peer information/helo string
        though this information is only sent once)."""
        self.connection.login('admin', 'admin')
        self.connection.sendmail('x@example.com', 'foo@example.com', rfc822_msg)
        self.connection.sendmail('x@example.com', 'bar@example.com', rfc822_msg)

        queue = self.get_received_messages()
        assert queue.qsize() == 2
        first_msg = queue.get()
        assert first_msg.smtp_helo is not None
        assert first_msg.smtp_from == 'x@example.com'

        second_msg = queue.get()
        assert second_msg.smtp_helo == first_msg.smtp_helo
        assert second_msg.username == first_msg.username

    def test_transparency_support_enabled(self):
        """Check that there is transparency support for lines starting with a
        dot in the message body (RFC 821, section 4.5.2)."""
        msg = rfc822_msg + '\n.Bar\nFoo'
        self.connection.sendmail('from@example.com', 'foo@example.com', msg)
        self.connection.quit()

        queue = self.get_received_messages()
        assert queue.qsize() == 1
        received_msg = queue.get()
        assert received_msg.msg_data == msg

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

        # Depending on when the protocol used (ESMTP with SIZE extension or
        # plain old SMTP) and when the server checks the message size (after
        # MAIL FROM or only when the message was transmitted completely),
        # the error message may differ.
        # Unfortunately Python's smtplib raises SMTPSenderRefused even if the
        # message was rejected due to size restrictions after issuing MAIL FROM
        # with size verb
        with pytest.raises((smtplib.SMTPDataError, smtplib.SMTPSenderRefused)) as exc_info:
            self.connection.sendmail('from@example.com', 'foo@example.com', msg)

        e = exc_info.value
        assert e.smtp_code == 552
        assert e.smtp_error == b('message exceeds fixed maximum message size')

    def service_is_available(self):
        # On a normal system we should be able to reconnect after a dropped
        # connection within two seconds under all circumstances.
        old_default = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2)
        try:
            try:
                self.connection.connect(self.hostname, self.listen_port)
                return True
            finally:
                socket.setdefaulttimeout(old_default)
        except socket.timeout:
            return False

    def test_workerprocess_detects_closed_connections_when_reading(self):
        """Check that the WorkerProcess gracefully handles connections which are
        closed without QUIT. This can happen due to network problems or
        unfriendly clients."""
        self.connection.helo('foo')
        self.connection.close()

        # In 0.3 the WorkerProcess would hang and start to eat up the whole CPU
        # so we need to set a sensible timeout so that this test will fail with
        # an appropriate exception.
        assert self.service_is_available()

    def test_workerprocess_detects_closed_connections_when_writing(self):
        """Check that the WorkerProcess gracefully handles connections which are
        closed without QUIT - remaining output is suppressed. This can happen
        due to network problems or unfriendly clients."""
        # Basically the problem also occurs without waiting - however sleeping a
        # bit increases the likelyhood to trigger to problem. We need to make
        # sure that the server writes to a already closed TCP connection.
        class WaitingPolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                is_first_time = getattr(self, 'is_first_time', False)
                if is_first_time:
                    time.sleep(1)
                # Also the socket will buffer some data - make sure the system
                # actually writes data to the socket so we get an exception.
                return (False, (552, ('Go away',)*10))
        self.init_mta(policy_class=WaitingPolicy)

        # don't wait for an answer as .helo() does
        self.connection.putcmd('helo', 'foo')
        self.connection.close()

        time.sleep(0.5)
        assert self.service_is_available()
