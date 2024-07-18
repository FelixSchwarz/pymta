# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import smtplib
import socket
import time

import pytest
from dotmap import DotMap
from pymta.api import IMTAPolicy
from pymta.compat import b, b64encode
from pymta.test_util import DummyAuthenticator, SMTPTestHelper


rfc822_msg = 'Subject: Test\n\nJust testing...'


def _smtp_ctx(policy_class=None):
    mta_helper = SMTPTestHelper(authenticator_class=DummyAuthenticator, policy_class=policy_class)
    (hostname, listen_port) = mta_helper.start_mta()
    smtp_connection = smtplib.SMTP()
    smtp_connection.set_debuglevel(0)
    smtp_connection.connect(hostname, listen_port)

    ctx = {
        'connection': smtp_connection,
        'hostname': hostname,
        'listen_port': listen_port,
        'mta': mta_helper,
    }
    try:
        yield DotMap(_dynamic=False, **ctx)
    finally:
        # close SMTP connection so the server thread can shut down
        try:
            smtp_connection.quit()
        except Exception:
            pass
        mta_helper.stop_mta()


@pytest.fixture
def mtx_ctx():
    for item in _smtp_ctx():
        yield item


def test_helo(mtx_ctx):
    code, replytext = mtx_ctx.connection.helo('foo')
    assert code == 250

def test_send_simple_email(mtx_ctx):
    code, replytext = mtx_ctx.connection.helo('foo')
    assert code == 250
    code, replytext = mtx_ctx.connection.mail('from@example.com')
    assert code == 250
    code, replytext = mtx_ctx.connection.rcpt('to@example.com')
    assert code == 250
    code, replytext = mtx_ctx.connection.data(rfc822_msg)
    assert code == 250
    mtx_ctx.connection.quit()
    _check_received_mail(mtx_ctx.mta, ['to@example.com'], expected_helo='foo')

def _check_received_mail(mta, expected_recipients, expected_helo=None):
    queue = mta.get_received_messages()
    assert queue.qsize() == 1
    msg = queue.get()
    if expected_helo is not None:
        assert msg.smtp_helo == 'foo'
    assert msg.smtp_from == 'from@example.com'
    assert msg.smtp_to == expected_recipients
    assert msg.msg_data == rfc822_msg
    return msg

def test_send_email_via_smtplib(mtx_ctx):
    """Check that we can send a simple email via smtplib.sendmail without
    using the low-level api."""
    recipient = 'to@example.com'
    mtx_ctx.connection.sendmail('from@example.com', recipient, rfc822_msg)
    mtx_ctx.connection.quit()
    _check_received_mail(mtx_ctx.mta, [recipient])

def test_multiple_recipients(mtx_ctx):
    """Check that we can send an email to multiple recipients at once."""
    recipients = ['foo@example.com', 'bar@example.com']
    mtx_ctx.connection.sendmail('from@example.com', recipients, rfc822_msg)
    mtx_ctx.connection.quit()
    _check_received_mail(mtx_ctx.mta, recipients)

def test_send_email_with_authentication(mtx_ctx):
    """Check that we can send an email with prior authentication."""
    recipient = 'to@example.com'
    mtx_ctx.connection.login('admin', 'admin')
    mtx_ctx.connection.sendmail('from@example.com', recipient, rfc822_msg)
    mtx_ctx.connection.quit()
    msg = _check_received_mail(mtx_ctx.mta, [recipient])
    assert msg.username == 'admin'

def test_send_email_with_auth_login(mtx_ctx):
    """Check that we can send an email with using AUTH LOGIN."""
    mtx_ctx.connection.ehlo()
    login_response = mtx_ctx.connection.docmd('AUTH', 'LOGIN %s' % b64encode('foo'))
    assert login_response == (334, b(b64encode('Password:')))
    password_response = mtx_ctx.connection.docmd(b64encode('foo'))
    assert password_response == (235, b('Authentication successful'))

    recipient = 'to@example.com'
    mtx_ctx.connection.sendmail('from@example.com', recipient, rfc822_msg)
    mtx_ctx.connection.quit()
    msg = _check_received_mail(mtx_ctx.mta, [recipient])
    assert msg.username == 'foo'

def test_send_multiple_emails_in_one_connection(mtx_ctx):
    """Check that we can send multiple emails in the same connection (and
    the second email needs to have the same peer information/helo string
    though this information is only sent once)."""
    mtx_ctx.connection.login('admin', 'admin')
    mtx_ctx.connection.sendmail('x@example.com', 'foo@example.com', rfc822_msg)
    mtx_ctx.connection.sendmail('x@example.com', 'bar@example.com', rfc822_msg)

    queue = mtx_ctx.mta.get_received_messages()
    assert queue.qsize() == 2
    first_msg = queue.get()
    assert first_msg.smtp_helo is not None
    assert first_msg.smtp_from == 'x@example.com'

    second_msg = queue.get()
    assert second_msg.smtp_helo == first_msg.smtp_helo
    assert second_msg.username == first_msg.username

def test_transparency_support_enabled(mtx_ctx):
    """Check that there is transparency support for lines starting with a
    dot in the message body (RFC 821, section 4.5.2)."""
    msg = rfc822_msg + '\n.Bar\nFoo'
    mtx_ctx.connection.sendmail('from@example.com', 'foo@example.com', msg)
    mtx_ctx.connection.quit()

    queue = mtx_ctx.mta.get_received_messages()
    assert queue.qsize() == 1
    received_msg = queue.get()
    assert received_msg.msg_data == msg


@pytest.fixture
def mtx_ctx_restricted_size_policy():
    class RestrictedSizePolicy(IMTAPolicy):
        def max_message_size(self, peer):
            return 100

    for item in _smtp_ctx(policy_class=RestrictedSizePolicy):
        yield item

def test_big_messages_are_rejected(mtx_ctx_restricted_size_policy):
    """Check that messages which exceed the configured maximum message size
    are rejected. This tests all the code setting the maximum allowed input
    size in the transport layer."""
    _ctx = mtx_ctx_restricted_size_policy

    big_data_chunk = ('x'*70 + '\n') * 1500
    msg = rfc822_msg + big_data_chunk

    # Depending on the protocol used (ESMTP with SIZE extension or plain old SMTP)
    # and when the server checks the message size (after MAIL FROM or only when
    # the message was transmitted completely), the error message may differ.
    # Unfortunately Python's smtplib raises SMTPSenderRefused even if the
    # message was rejected due to size restrictions after issuing MAIL FROM
    # with size verb.
    with pytest.raises((smtplib.SMTPDataError, smtplib.SMTPSenderRefused)) as exc_info:
        _ctx.connection.sendmail('from@example.com', 'foo@example.com', msg)

    e = exc_info.value
    assert e.smtp_code == 552
    assert e.smtp_error == b('message exceeds fixed maximum message size')



def service_is_available(mtx_ctx, timeout=2):
    # On a normal system we should be able to reconnect after a dropped
    # connection within two seconds under all circumstances.
    old_default = socket.getdefaulttimeout()
    socket.setdefaulttimeout(2)
    try:
        try:
            mtx_ctx.connection.connect(mtx_ctx.hostname, mtx_ctx.listen_port)
            return True
        finally:
            socket.setdefaulttimeout(old_default)
    except socket.timeout:
        return False

def test_workerprocess_detects_closed_connections_when_reading(mtx_ctx):
    """Check that the WorkerProcess gracefully handles connections which are
    closed without QUIT. This can happen due to network problems or
    unfriendly clients."""
    mtx_ctx.connection.helo('foo')
    mtx_ctx.connection.close()

    # In 0.3 the WorkerProcess would hang and start to eat up the whole CPU
    # so we need to set a sensible timeout so that this test will fail with
    # an appropriate exception.
    assert service_is_available(mtx_ctx)



@pytest.fixture
def mtx_ctx_waiting_policy():
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

    for item in _smtp_ctx(policy_class=WaitingPolicy):
        yield item


def test_workerprocess_detects_closed_connections_when_writing(mtx_ctx_waiting_policy):
    """Check that the WorkerProcess gracefully handles connections which are
    closed without QUIT - remaining output is suppressed. This can happen
    due to network problems or unfriendly clients."""

    _ctx = mtx_ctx_waiting_policy
    # don't wait for an answer as .helo() does
    _ctx.connection.putcmd('helo', 'foo')
    _ctx.connection.close()

    for _ in range(10):
        time.sleep(0.05)
        if service_is_available(_ctx, timeout=0.01):
            break
    else:
        raise AssertionError('Service is not available after 0.5s')
