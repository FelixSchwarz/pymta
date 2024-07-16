# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT
"Tests that all commands can be controlled with policies."

from __future__ import print_function, unicode_literals

from pymta.api import IMTAPolicy, PolicyDecision
from pymta.compat import b64encode
from pymta.test_util import CommandParserHelper, DummyAuthenticator



def test_connection_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_new_connection(self, peer):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy())
    assert not _cp.command_parser.open
    assert len(_cp.command_parser.replies) == 1
    code, reply_text = _cp.command_parser.replies[-1]
    assert code == 554
    assert reply_text == 'SMTP service not available'


def test_helo_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            return (not helo_string.endswith('example.com'))
    _cp = CommandParserHelper(policy=FalsePolicy())
    _cp.send('HELO', 'foo.example.com', expected_first_digit=5)
    _cp.send('HELO', 'bar.example.com', expected_first_digit=5)
    _cp.send('HELO', 'localhost')


def test_ehlo_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_ehlo(self, ehlo_string, message):
            return (not ehlo_string.endswith('example.com'))
    _cp = CommandParserHelper(policy=FalsePolicy())
    _cp.send('EHLO', 'foo.example.com', expected_first_digit=5)
    _cp.send('EHLO', 'localhost')


def test_auth_plain_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_auth_plain(self, username, password, message):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy(), authenticator=DummyAuthenticator())
    _cp.send('EHLO', 'foo.example.com')
    base64_credentials = b64encode('\x00foo\x00foo')
    _cp.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)

def test_auth_login_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_auth_login(self, username, message):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy(), authenticator=DummyAuthenticator())
    _cp.send('EHLO', 'foo.example.com')
    _cp.send('AUTH LOGIN', expected_first_digit=5)

def test_from_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_from(self, sender, message):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy())
    _cp.send('HELO', 'foo.example.com')
    _cp.send('MAIL FROM', 'foo@example.com', expected_first_digit=5)


def test_rcptto_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_rcpt_to(self, new_recipient, message):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy())
    _cp.send('HELO', 'foo.example.com')
    _cp.send('MAIL FROM', 'foo@example.com')
    _cp.send('RCPT TO', 'to@example.com', expected_first_digit=5)


def test_data_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_data(self, message):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy())
    _cp.send('HELO', 'foo.example.com')
    _cp.send('MAIL FROM', 'foo@example.com')
    _cp.send('RCPT TO', 'to@example.com')
    _cp.send('DATA', expected_first_digit=5)


def test_messages_can_be_rejected():
    class FalsePolicy(IMTAPolicy):
        def accept_msgdata(self, msg_data, message):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy())
    _cp.send('HELO', 'foo.example.com')
    _cp.send('MAIL FROM', 'foo@example.com')
    _cp.send('RCPT TO', 'to@example.com')
    _cp.send('DATA', expected_first_digit=3)
    rfc822_msg = 'Subject: Test\n\nJust testing...\n'
    _cp.send('MSGDATA', rfc822_msg, expected_first_digit=5)


def test_size_limit_messages_can_be_rejected():
    class MaxSizePolicy(IMTAPolicy):
        def max_message_size(self, peer):
            return 100
    _cp = CommandParserHelper(policy=MaxSizePolicy())
    _cp.send('HELO', 'foo.example.com')
    _cp.send('MAIL FROM', 'foo@example.com')
    _cp.send('RCPT TO', 'to@example.com')
    _cp.send('DATA', expected_first_digit=3)
    big_data_chunk = ('x'*70 + '\n') * 1500
    rfc822_msg = 'Subject: Test\n\nJust testing...\n' + big_data_chunk
    (code, reply_text) = _cp.send('MSGDATA', rfc822_msg,
                                    expected_first_digit=5)
    assert code == 552
    assert reply_text == 'message exceeds fixed maximum message size'

def test_server_deals_gracefully_with_double_close_because_of_faulty_policy():
    class DoubleCloseConnectionPolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            decision = PolicyDecision(True)
            decision._close_connection_before_response = True
            decision._close_connection_after_response = True
            return decision

    _cp = CommandParserHelper(policy=DoubleCloseConnectionPolicy())
    number_replies_before = len(_cp.command_parser.replies)
    _cp.session.handle_input('HELO', 'foo.example.com')
    assert len(_cp.command_parser.replies) == number_replies_before
    assert not _cp.command_parser.open

